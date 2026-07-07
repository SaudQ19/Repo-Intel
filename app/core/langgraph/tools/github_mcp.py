"""GitHub MCP tool wrapper for LangGraph."""

import asyncio
import os
from typing import List, Any, Optional, cast
from mcp import ClientSession, StdioServerParameters
from mcp.types import TextContent
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.core.config import settings
from app.core.logging import logger

# Global client reference to keep the connection alive
_mcp_client_context = None
_mcp_session: Optional[ClientSession] = None
_mcp_tools: List[StructuredTool] = []
_lock = asyncio.Lock()


async def close_github_mcp():
    """Close the active GitHub MCP server connection."""
    global _mcp_client_context, _mcp_session, _mcp_tools
    async with _lock:
        if _mcp_client_context is not None:
            logger.info("closing_github_mcp_server_connection")
            try:
                # Exit the async context manager
                await _mcp_client_context.__aexit__(None, None, None)
            except Exception as e:
                logger.debug("mcp_context_cleanup_info", error=str(e))
            _mcp_client_context = None
            _mcp_session = None
            _mcp_tools = []


async def get_github_mcp_tools() -> List[StructuredTool]:
    """Retrieve and initialize the GitHub MCP tools.

    Spawns the @modelcontextprotocol/server-github process via npx
    and wraps all exposed tools into LangChain StructuredTool instances.
    """
    global _mcp_client_context, _mcp_session, _mcp_tools

    # If GITHUB_PERSONAL_ACCESS_TOKEN is not configured, do not load these tools
    if not settings.GITHUB_PERSONAL_ACCESS_TOKEN:
        logger.warning("github_mcp_token_not_set_skipping_tools")
        return []

    async with _lock:
        if _mcp_tools:
            return _mcp_tools

        logger.info("starting_github_mcp_server_connection")

        # Config parameter for MCP server
        # Explicitly pass GITHUB_PERSONAL_ACCESS_TOKEN and copy PATH to locate node/npx
        env = {
            "GITHUB_PERSONAL_ACCESS_TOKEN": settings.GITHUB_PERSONAL_ACCESS_TOKEN,
            "PATH": os.environ.get("PATH", ""),
        }
        
        # Inherit standard system environment variables if any
        for key in ["SYSTEMROOT", "TEMP", "TMP"]:
            if key in os.environ:
                env[key] = os.environ[key]

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env=env,
        )

        async def _init_mcp() -> List[StructuredTool]:
            """Inner coroutine so we can apply a timeout to the entire npx startup."""
            # Start client stdio context
            client_ctx = stdio_client(server_params)
            read_stream, write_stream = await client_ctx.__aenter__()

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            mcp_tools_list = await session.list_tools()

            wrapped: List[StructuredTool] = []
            for tool_info in mcp_tools_list.tools:
                tool_name = tool_info.name
                tool_desc = tool_info.description or f"GitHub MCP tool: {tool_name}"

                def make_call(name: str = tool_name) -> Any:
                    async def call_mcp_tool(**kwargs: Any) -> str:
                        if not _mcp_session:
                            return "Error: GitHub MCP session is not active."
                        try:
                            result = await _mcp_session.call_tool(name, arguments=kwargs)
                            text_contents = [c.text for c in result.content if isinstance(c, TextContent)]
                            return "\n".join(text_contents)
                        except Exception as exc:
                            logger.exception("github_mcp_tool_execution_failed", tool=name, error=str(exc))
                            return f"Error executing tool {name}: {str(exc)}"
                    return call_mcp_tool

                input_schema = tool_info.inputSchema
                properties = input_schema.get("properties", {})
                required_fields = input_schema.get("required", [])

                fields: dict[str, Any] = {}
                for prop_name, prop_data in properties.items():
                    prop_type = prop_data.get("type")
                    py_type: Any = Any
                    if prop_type == "string":
                        py_type = str
                    elif prop_type == "integer":
                        py_type = int
                    elif prop_type == "boolean":
                        py_type = bool
                    elif prop_type == "array":
                        py_type = list

                    if prop_name in required_fields:
                        fields[prop_name] = (py_type, ...)
                    else:
                        fields[prop_name] = (Optional[py_type], None)

                args_schema = None
                if fields:
                    args_schema = create_model(f"GitHubTool_{tool_name}_Args", **fields)

                wrapped.append(
                    StructuredTool(
                        name=f"github_{tool_name}",
                        description=tool_desc,
                        func=None,
                        coroutine=make_call(tool_name),
                        args_schema=cast(Any, args_schema),
                    )
                )

            # Store globals only after successful init
            global _mcp_client_context, _mcp_session
            _mcp_client_context = client_ctx
            _mcp_session = session
            return wrapped

        try:
            # 20-second hard timeout — if npx hangs (e.g. slow npm download on Render),
            # give up and continue without GitHub MCP tools rather than blocking the port.
            tools = await asyncio.wait_for(_init_mcp(), timeout=20.0)
            _mcp_tools = tools
            logger.info("github_mcp_tools_initialized_successfully", count=len(tools))
            return _mcp_tools

        except asyncio.TimeoutError:
            logger.warning("github_mcp_initialization_timed_out_skipping_tools")
            _mcp_tools = []
            _mcp_session = None
            _mcp_client_context = None
            return []
        except Exception as e:
            logger.exception("github_mcp_initialization_failed", error=str(e))
            _mcp_tools = []
            _mcp_session = None
            _mcp_client_context = None
            return []

