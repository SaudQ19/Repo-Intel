"""Repository documentation endpoints powered by GitHub MCP."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.core.langgraph.tools import github_mcp
from app.services.llm import llm_service
from app.langgraph.agents.doc_builder import DocBuilderAgent
from app.utils.graph import extract_text_content
from langchain_core.messages import SystemMessage, HumanMessage
from mcp.types import TextContent


router = APIRouter()
doc_agent = DocBuilderAgent()


class DocFile(BaseModel):
    """A documentation file from the repository."""

    path: str
    content: str


class DocOverview(BaseModel):
    """Repository documentation overview."""

    readme: str
    doc_files: list[DocFile]
    generated_summary: str


async def _call_mcp_tool(tool_name: str, **kwargs) -> str:
    """Call a GitHub MCP tool by name."""
    if not github_mcp._mcp_session:
        await github_mcp.get_github_mcp_tools()

    if not github_mcp._mcp_session:
        raise RuntimeError("GitHub MCP session not available. Check GITHUB_PERSONAL_ACCESS_TOKEN.")

    result = await github_mcp._mcp_session.call_tool(tool_name, arguments=kwargs)
    text_contents = [c.text for c in result.content if isinstance(c, TextContent)]
    return "\n".join(text_contents)


@router.get("/{owner}/{repo}")
async def get_repository_docs(owner: str, repo: str):
    """Fetch repository documentation via GitHub MCP.

    Retrieves the README and other markdown files from the repo root.

    Args:
        owner: Repository owner.
        repo: Repository name.

    Returns:
        Repository documentation overview with README content.
    """
    try:
        # Fetch README
        readme_content = ""
        try:
            raw = await _call_mcp_tool("get_file_contents", owner=owner, repo=repo, path="README.md")
            # MCP returns file content, may be base64 or plain text
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "content" in data:
                    import base64

                    readme_content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
                else:
                    readme_content = raw
            except json.JSONDecodeError:
                readme_content = raw
        except Exception as e:
            logger.warning("readme_fetch_failed", owner=owner, repo=repo, error=str(e))
            readme_content = "*README not found or not accessible.*"

        # Fetch repo tree to find other doc files
        doc_files = []
        try:
            raw_tree = await _call_mcp_tool("get_file_contents", owner=owner, repo=repo, path="")
            tree_data = json.loads(raw_tree)

            # Look for markdown files in root
            if isinstance(tree_data, list):
                md_files = [f for f in tree_data if isinstance(f, dict) and f.get("name", "").endswith(".md") and f.get("name") != "README.md"]
                for md_file in md_files[:5]:
                    try:
                        file_raw = await _call_mcp_tool(
                            "get_file_contents", owner=owner, repo=repo, path=md_file["name"]
                        )
                        try:
                            file_data = json.loads(file_raw)
                            if isinstance(file_data, dict) and "content" in file_data:
                                import base64

                                content = base64.b64decode(file_data["content"]).decode("utf-8", errors="ignore")
                            else:
                                content = file_raw
                        except json.JSONDecodeError:
                            content = file_raw
                        doc_files.append(DocFile(path=md_file["name"], content=content[:3000]))
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("doc_tree_fetch_failed", owner=owner, repo=repo, error=str(e))

        # Generate AI summary of the documentation
        summary = ""
        if readme_content and len(readme_content) > 50:
            try:
                response = await llm_service.call(
                    [
                        SystemMessage(
                            content="Summarize this repository's README in 2-3 concise paragraphs. Focus on what the project does, its key features, and how to get started."
                        ),
                        HumanMessage(content=readme_content[:4000]),
                    ],
                    model_name=settings.DEFAULT_LLM_MODEL,
                )
                summary = extract_text_content(response.content).strip()
            except Exception as e:
                logger.warning("doc_summary_generation_failed", error=str(e))
                summary = "Summary generation unavailable."

        return DocOverview(
            readme=readme_content,
            doc_files=doc_files,
            generated_summary=summary,
        )
    except Exception as e:
        logger.exception("get_repository_docs_failed", owner=owner, repo=repo, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch documentation: {str(e)}")


class GenerateDocsRequest(BaseModel):
    """Request payload for generating architectural documentation."""

    repository_id: str | None = None


@router.post("/{owner}/{repo}/generate")
async def generate_documentation(owner: str, repo: str, request_data: GenerateDocsRequest):
    """Generate architectural documentation for an indexed repository.

    Args:
        owner: Repository owner (for display).
        repo: Repository name (for display).
        request_data: Request body containing optional indexed repository ID.

    Returns:
        Generated architectural documentation.
    """
    repository_id = request_data.repository_id
    if repository_id:
        try:
            result = await doc_agent.generate_docs(repository_id)
            return result
        except Exception as e:
            logger.exception("generate_docs_failed", repository_id=repository_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate documentation: {str(e)}")

    return {"documentation": "Please provide a repository_id of an indexed repository to generate architectural docs."}

