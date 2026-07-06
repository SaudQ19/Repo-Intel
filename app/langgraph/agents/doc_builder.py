"""Documentation Builder Agent implementation."""

from sqlmodel import Session, select
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.logging import logger
from app.models.chunk import CodeChunk
from app.services.database import database_service
from app.services.llm import llm_service

DOC_BUILDER_PROMPT = """You are a Technical Architect.
Based on the following list of file paths, classes, and function symbols extracted from the codebase, generate a comprehensive architectural markdown document.
Describe the system flow, component boundaries, modules, and API interfaces. Include a Mermaid diagram representing relationships between files or layers if appropriate.
"""


class DocBuilderAgent:
    """Agent that compiles AST code symbol layouts into unified architectural documentation guides."""

    def __init__(self):
        """Initialize the DocBuilderAgent."""
        self.llm = llm_service

    async def generate_docs(self, repository_id: str) -> dict:
        """Scan repository symbol mappings and generate markdown guides."""
        try:
            logger.info("documentation_generation_started", repo_id=repository_id)

            # Retrieve symbol list from DB to feed the context window
            with Session(database_service.engine) as session:
                stmt = select(CodeChunk.file_path, CodeChunk.symbol_name, CodeChunk.symbol_type).where(
                    CodeChunk.repository_id == repository_id
                )
                results = session.exec(stmt).all()

            if not results:
                return {"documentation": "No code symbols indexed. Please index the repository first."}

            # Deduplicate and build a summary list of code files & symbols
            symbol_map = {}
            for file_path, sym_name, sym_type in results:
                if file_path not in symbol_map:
                    symbol_map[file_path] = []
                if sym_name:
                    symbol_map[file_path].append(f"{sym_type or 'symbol'}: {sym_name}")

            summary_lines = []
            for path, syms in symbol_map.items():
                summary_lines.append(f"- **File**: {path}")
                for s in syms[:15]:  # Cap symbols per file to avoid overloading context
                    summary_lines.append(f"  - {s}")

            summary_text = "\n".join(summary_lines)

            # Generate the architectural description
            from app.core.config import settings
            response = await self.llm.call(
                [
                    SystemMessage(content=DOC_BUILDER_PROMPT),
                    HumanMessage(content=f"Codebase Outline:\n\n{summary_text}")
                ],
                model_name=settings.DEFAULT_LLM_MODEL
            )

            logger.info("documentation_generation_completed", repo_id=repository_id)
            return {
                "documentation": response.content.strip()
            }

        except Exception as e:
            logger.exception("doc_builder_agent_failed", repo_id=repository_id, error=str(e))
            return {
                "documentation": f"Failed to generate documentation: {str(e)}"
            }
