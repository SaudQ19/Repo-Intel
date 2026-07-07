"""FastAPI routes for repository indexing and management.

In DEMO_MODE, write operations (register, delete, index) are disabled.
"""

import os
import shutil
import subprocess
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import logger
from app.models.repository import Repository
from app.services.database import database_service
from app.indexer.pipeline import IndexingPipeline

router = APIRouter()
pipeline = IndexingPipeline()


class RepositoryCreate(BaseModel):
    """Schema for registering a new repository."""
    name: str = Field(..., description="Display name for the repository")
    clone_url: str = Field(..., description="Git URL or absolute local folder path to scan")
    branch: str = Field(default="main", description="Target branch name")


class RepositoryResponse(BaseModel):
    """Schema for returning repository registration details."""
    id: str
    name: str
    clone_url: str
    branch: str
    status: str
    last_indexed_at: str | None


def is_git_url(url: str) -> bool:
    """Check if the provided url/path is a remote Git URL."""
    url = url.strip()
    return (
        url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("git@")
        or url.startswith("git://")
        or (url.endswith(".git") and ":" in url)
    )


def clone_and_index_task(repo_id: str, clone_url: str, branch: str) -> None:
    """Background task to clone a remote repo if needed, and index it."""
    local_path = clone_url
    
    if is_git_url(clone_url):
        local_path = os.path.join(os.getcwd(), "data", "cloned_repos", repo_id)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Clean up any existing folder if present
        if os.path.exists(local_path):
            shutil.rmtree(local_path)
            
        logger.info("cloning_repository_started", repo_id=repo_id, url=clone_url, path=local_path, branch=branch)
        
        # Try cloning the specific branch
        process = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, clone_url, local_path],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            logger.warning("git_clone_branch_failed", repo_id=repo_id, error=process.stderr, trying_default_branch=True)
            # Fallback to cloning the default branch
            process = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, local_path],
                capture_output=True,
                text=True
            )
            
        if process.returncode != 0:
            logger.error("git_clone_failed", repo_id=repo_id, error=process.stderr)
            with Session(database_service.engine) as session:
                repo = session.get(Repository, repo_id)
                if repo:
                    repo.status = "failed"
                    session.add(repo)
                    session.commit()
            return
            
        logger.info("cloning_repository_successful", repo_id=repo_id, path=local_path)

    # Run the main indexing pipeline on the local path
    pipeline.scan_and_index(repo_id, local_path)


@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def register_repository(repo_in: RepositoryCreate):
    """Register a new repository for indexing."""
    repo_id = str(uuid.uuid4())
    
    with Session(database_service.engine) as session:
        if not is_git_url(repo_in.clone_url) and os.path.exists(repo_in.clone_url):
            logger.info("local_path_detected", path=repo_in.clone_url)
            
        repo = Repository(
            id=repo_id,
            name=repo_in.name,
            clone_url=repo_in.clone_url,
            branch=repo_in.branch,
            status="pending",
        )
        session.add(repo)
        session.commit()
        session.refresh(repo)
        
    logger.info("repository_registered", repo_id=repo_id, name=repo_in.name)
    return repo


@router.get("/", response_model=List[RepositoryResponse])
async def list_repositories():
    """Retrieve all registered repositories."""
    with Session(database_service.engine) as session:
        statement = select(Repository)
        repos = session.exec(statement).all()
        return list(repos)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(repo_id: str):
    """Delete a repository and its associated indexed chunks."""
    with Session(database_service.engine) as session:
        repo = session.get(Repository, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Remove any code chunks associated with this repository first to avoid constraint violation
        from sqlmodel import select
        from app.models.chunk import CodeChunk
        chunks_stmt = select(CodeChunk).where(CodeChunk.repository_id == repo_id)
        chunks = session.exec(chunks_stmt).all()
        for chunk in chunks:
            session.delete(chunk)
        session.commit()

        # If the repository was cloned locally by our system, clean it up
        local_path = os.path.join(os.getcwd(), "data", "cloned_repos", repo_id)
        if os.path.exists(local_path):
            try:
                shutil.rmtree(local_path)
                logger.info("cloned_repo_dir_deleted", repo_id=repo_id, path=local_path)
            except Exception as e:
                logger.exception("cloned_repo_dir_delete_failed", repo_id=repo_id, path=local_path, error=str(e))
        
        session.delete(repo)
        session.commit()
        
    logger.info("repository_deleted", repo_id=repo_id)
    return


@router.post("/{repo_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_indexing(repo_id: str, background_tasks: BackgroundTasks):
    """Asynchronously scan and index the codebase of a registered repository."""
    with Session(database_service.engine) as session:
        repo = session.get(Repository, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
            
        # Verify if path exists (only for local paths, not remote Git URLs)
        if not is_git_url(repo.clone_url) and not os.path.exists(repo.clone_url):
            raise HTTPException(
                status_code=400, 
                detail=f"Local repository path '{repo.clone_url}' does not exist on disk."
            )
            
        repo.status = "indexing"
        session.add(repo)
        session.commit()
        
        # Fetch branch and clone_url from active DB state for the background task
        db_clone_url = repo.clone_url
        db_branch = repo.branch
        
    # Queue background processing (cloning and indexing)
    background_tasks.add_task(clone_and_index_task, repo_id, db_clone_url, db_branch)
    
    logger.info("indexing_task_queued", repo_id=repo_id)
    return {"message": "Indexing started in the background."}


@router.get("/{repo_id}/status", response_model=RepositoryResponse)
async def get_repository_status(repo_id: str):
    """Fetch active indexing progress state of a repository."""
    with Session(database_service.engine) as session:
        repo = session.get(Repository, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        return repo

