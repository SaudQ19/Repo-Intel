"""pgvector search tool for LangGraph."""

from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import logger
from app.models.chunk import CodeChunk
from app.services.database import database_service


@tool
def pgvector_search_tool(query: str, config: RunnableConfig, limit: int = 5) -> str:
    """Perform a semantic search across code chunks in the active repository.

    Args:
        query: The search query text or code symbol name.
        config: The RunnableConfig dict containing request metadata.
        limit: Number of matching chunks to return.

    Returns:
        str: Formatted markdown string containing matches and file locations.
    """
    repository_id = config.get("metadata", {}).get("repository_id")
    if not repository_id:
        return "Error: No active repository context. Please supply a repository_id in your request."

    try:
        # 1. Generate query embedding
        embeddings = HuggingFaceEndpointEmbeddings(
            model=settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
            huggingfacehub_api_token=settings.HF_TOKEN,
        )
        query_vector = embeddings.embed_query(query)

        # 2. Run cosine similarity query using SQLModel & pgvector operators
        with Session(database_service.engine) as session:
            # We use pgvector's cosine distance operator (<=>)
            from typing import Any
            embedding_col: Any = CodeChunk.embedding
            distance_expr = embedding_col.cosine_distance(query_vector)
            statement = (
                select(CodeChunk, distance_expr.label("distance"))
                .where(CodeChunk.repository_id == repository_id)
                .order_by("distance")
                .limit(limit)
            )
            
            results = session.exec(statement).all()
            
            if not results:
                return f"No code results found matching '{query}' in repository."

            formatted_results = []
            for chunk, dist in results:
                score = 1.0 - float(dist) if dist is not None else 0.0
                formatted_results.append(
                    f"### File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line})\n"
                    f"**Symbol**: {chunk.symbol_name or 'None'} | **Type**: {chunk.symbol_type or 'None'} | **Relevance**: {score:.2f}\n"
                    f"```\n{chunk.content}\n```\n"
                )
                
            return "\n".join(formatted_results)
            
    except Exception as e:
        logger.exception("pgvector_search_tool_failed", query=query, repo_id=repository_id, error=str(e))
        return f"Error executing semantic search: {str(e)}"
