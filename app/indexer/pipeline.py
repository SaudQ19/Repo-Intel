"""Indexing pipeline module for code scanning and embedding."""

import os
import uuid
from typing import List, Dict, Any
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlmodel import Session

from app.core.config import settings
from app.core.logging import logger
from app.indexer.parser import ASTParser
from app.models.repository import Repository
from app.services.database import database_service

# Define folders to ignore during directory walking
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "egg-info",
    ".idea",
    ".vscode",
    ".gemini",
    "logs",
}

# File extensions to parse
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".java",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".sql",
}


class IndexingPipeline:
    """Manages the full pipeline of cloning/scanning, parsing, embedding, and indexing a repository."""

    def __init__(self):
        """Initialize parsing and embedding engines."""
        self.parser = ASTParser()
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model=settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
            huggingfacehub_api_token=settings.HF_TOKEN,
        )

    def scan_and_index(self, repo_id: str, local_path: str) -> None:
        """Scan files in the local directory, parse them, batch embed, and insert into PostgreSQL."""
        try:
            logger.info("indexing_started", repo_id=repo_id, path=local_path)
            
            # 1. Update Repository status in DB
            with Session(database_service.engine) as session:
                repo = session.get(Repository, repo_id)
                if not repo:
                    logger.error("repo_not_found", repo_id=repo_id)
                    return
                repo.status = "indexing"
                session.add(repo)
                session.commit()

            # 2. Walk directory and collect valid text chunks
            all_chunks: List[Dict[str, Any]] = []
            
            for root, dirs, files in os.walk(local_path):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                
                for file in files:
                    _, ext = os.path.splitext(file)
                    if ext.lower() not in ALLOWED_EXTENSIONS:
                        continue
                        
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, local_path)
                    
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        if not content.strip():
                            continue
                            
                        file_symbols = self.parser.parse_file(rel_path, content)
                        for sym in file_symbols:
                            sym["file_path"] = rel_path
                            all_chunks.append(sym)
                            
                    except Exception as fe:
                        logger.warning("failed_to_parse_file", file=rel_path, error=str(fe))

            if not all_chunks:
                logger.warning("no_chunks_found_in_repository", repo_id=repo_id)
                with Session(database_service.engine) as session:
                    repo = session.get(Repository, repo_id)
                    if repo:
                        repo.status = "active"
                        session.add(repo)
                        session.commit()
                return

            logger.info("code_symbols_extracted", repo_id=repo_id, count=len(all_chunks))

            # 3. Batch Embed chunks
            # Extract content strings
            contents = [c["content"] for c in all_chunks]
            
            logger.info("generating_embeddings", repo_id=repo_id, count=len(contents))
            # Batch embedding requests in blocks of 100
            embeddings_list: List[List[float]] = []
            batch_size = 100
            for i in range(0, len(contents), batch_size):
                batch = contents[i : i + batch_size]
                batch_embeddings = self.embeddings.embed_documents(batch)
                embeddings_list.extend(batch_embeddings)

            # 4. Save to Database
            logger.info("saving_chunks_to_db", repo_id=repo_id)
            with Session(database_service.engine) as session:
                # Remove existing chunks for this repository (clean update support)
                from sqlmodel import select
                from app.models.chunk import CodeChunk
                
                stmt = select(CodeChunk).where(CodeChunk.repository_id == repo_id)
                existing = session.exec(stmt).all()
                for e in existing:
                    session.delete(e)
                session.commit()

                # Add new chunks
                for chunk_data, emb in zip(all_chunks, embeddings_list, strict=False):
                    db_chunk = CodeChunk(
                        id=str(uuid.uuid4()),
                        repository_id=repo_id,
                        file_path=chunk_data["file_path"],
                        symbol_name=chunk_data.get("symbol_name"),
                        symbol_type=chunk_data.get("symbol_type"),
                        start_line=chunk_data["start_line"],
                        end_line=chunk_data["end_line"],
                        content=chunk_data["content"],
                        embedding=emb,
                        chunk_metadata=chunk_data.get("metadata", {}),
                    )
                    session.add(db_chunk)

                # Set Repository status as active
                from datetime import datetime, UTC
                repo = session.get(Repository, repo_id)
                if repo:
                    repo.status = "active"
                    repo.last_indexed_at = datetime.now(UTC).isoformat()
                    session.add(repo)
                
                session.commit()
                
            logger.info("indexing_completed", repo_id=repo_id)
            
        except Exception as e:
            logger.exception("indexing_failed", repo_id=repo_id, error=str(e))
            with Session(database_service.engine) as session:
                repo = session.get(Repository, repo_id)
                if repo:
                    repo.status = "failed"
                    session.add(repo)
                    session.commit()
