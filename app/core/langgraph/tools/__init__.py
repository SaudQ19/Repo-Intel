"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. The chat agent uses only the pgvector
semantic search tool to query the indexed repository data.
"""

from langchain_core.tools.base import BaseTool

from .pgvector_search import pgvector_search_tool

tools: list[BaseTool] = [
    pgvector_search_tool,
]
