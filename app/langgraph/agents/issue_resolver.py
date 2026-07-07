"""Issue Resolver Agent implementation."""

from sqlmodel import Session, select
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.core.config import settings
from app.core.logging import logger
from app.models.chunk import CodeChunk
from app.services.database import database_service
from app.services.llm import llm_service
from app.utils.graph import extract_text_content

ISSUE_RESOLVER_PROMPT = """You are a Senior Debugging Specialist.
Analyze the user's issue report or stacktrace below, alongside the semantic code context matches extracted from the database.
Diagnose the root cause of the bug and write a detailed patch recommendations guide.
Include code diff snippets indicating exactly what lines to delete or add.
"""


class IssueResolverAgent:
    """Agent that resolves issues, diagnoses stack traces, and compiles patch updates."""

    def __init__(self):
        """Initialize the IssueResolverAgent."""
        self.llm = llm_service
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model=settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
            huggingfacehub_api_token=settings.HF_TOKEN,
        )

    async def resolve_issue(self, repository_id: str, issue_text: str) -> dict:
        """Scan active codes matching the issue details, diagnose, and construct patches."""
        try:
            logger.info("issue_resolution_started", repo_id=repository_id)

            # 1. Embed the issue text to find semantically relevant code files
            query_vector = self.embeddings.embed_query(issue_text)

            # 2. Get top 5 matches
            with Session(database_service.engine) as session:
                from typing import Any
                embedding_col: Any = CodeChunk.embedding
                distance_expr = embedding_col.cosine_distance(query_vector)
                statement = (
                    select(CodeChunk, distance_expr.label("distance"))
                    .where(CodeChunk.repository_id == repository_id)
                    .order_by("distance")
                    .limit(5)
                )
                results = session.exec(statement).all()

            code_context_lines = []
            for chunk, _ in results:
                code_context_lines.append(
                    f"File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line})\n"
                    f"```\n{chunk.content}\n```\n"
                )
            code_context = "\n".join(code_context_lines)

            # 3. LLM Diagnostic Call
            response = await self.llm.call(
                [
                    SystemMessage(content=ISSUE_RESOLVER_PROMPT),
                    HumanMessage(
                        content=(
                            f"### ISSUE REPORT:\n{issue_text}\n\n"
                            f"### RELEVANT CODE BLOCKS:\n{code_context}"
                        )
                    )
                ],
                model_name=settings.DEFAULT_LLM_MODEL
            )

            logger.info("issue_resolution_completed", repo_id=repository_id)
            return {
                "diagnosis": extract_text_content(response.content).strip(),
                "relevant_files": list(set([c.file_path for c, _ in results]))
            }

        except Exception as e:
            logger.exception("issue_resolver_agent_failed", repo_id=repository_id, error=str(e))
            return {
                "diagnosis": f"Failed to diagnose issue: {str(e)}",
                "relevant_files": []
            }
