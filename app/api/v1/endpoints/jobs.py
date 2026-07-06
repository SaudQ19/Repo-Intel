"""FastAPI routes for agent execution jobs."""

import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.logging import logger
from app.models.agent_run import AgentRun
from app.services.database import database_service
from app.langgraph.agents.pr_reviewer import PRReviewerAgent
from app.langgraph.agents.doc_builder import DocBuilderAgent
from app.langgraph.agents.issue_resolver import IssueResolverAgent

router = APIRouter()

pr_agent = PRReviewerAgent()
doc_agent = DocBuilderAgent()
issue_agent = IssueResolverAgent()


class PRReviewRequest(BaseModel):
    """Schema for pull request review request payload."""
    repository_id: str = Field(..., description="ID of the repository to review")
    diff: str = Field(..., description="Git diff payload to review")


class DocumentationRequest(BaseModel):
    """Schema for codebase documentation generation request payload."""
    repository_id: str = Field(..., description="ID of the repository to generate docs for")


class IssueRequest(BaseModel):
    """Schema for issue investigation request payload."""
    repository_id: str = Field(..., description="ID of the repository containing the issue")
    issue_text: str = Field(..., description="Description of the bug or traceback details")


class JobResponse(BaseModel):
    """Schema representing background agent execution status response."""
    job_id: str
    agent_type: str
    status: str
    result: dict | None
    error: str | None


# Background executor tasks
async def _execute_pr_review(job_id: str, diff: str):
    try:
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "running"
                session.add(job)
                session.commit()

        result = await pr_agent.review(diff)

        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "completed"
                job.result = result
                session.add(job)
                session.commit()
    except Exception as e:
        logger.exception("background_pr_review_failed", job_id=job_id, error=str(e))
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "failed"
                job.error = str(e)
                session.add(job)
                session.commit()


async def _execute_doc_generation(job_id: str, repository_id: str):
    try:
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "running"
                session.add(job)
                session.commit()

        result = await doc_agent.generate_docs(repository_id)

        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "completed"
                job.result = result
                session.add(job)
                session.commit()
    except Exception as e:
        logger.exception("background_doc_gen_failed", job_id=job_id, error=str(e))
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "failed"
                job.error = str(e)
                session.add(job)
                session.commit()


async def _execute_issue_resolution(job_id: str, repository_id: str, issue_text: str):
    try:
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "running"
                session.add(job)
                session.commit()

        result = await issue_agent.resolve_issue(repository_id, issue_text)

        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "completed"
                job.result = result
                session.add(job)
                session.commit()
    except Exception as e:
        logger.exception("background_issue_res_failed", job_id=job_id, error=str(e))
        with Session(database_service.engine) as session:
            job = session.get(AgentRun, job_id)
            if job:
                job.status = "failed"
                job.error = str(e)
                session.add(job)
                session.commit()


@router.post("/pr-review", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_pr_review(req: PRReviewRequest, background_tasks: BackgroundTasks):
    """Queue a Pull Request code diff review job."""
    job_id = str(uuid.uuid4())
    with Session(database_service.engine) as session:
        job = AgentRun(
            id=job_id,
            agent_type="pr_review",
            status="pending",
            payload={"repository_id": req.repository_id},
        )
        session.add(job)
        session.commit()
        response = JobResponse(
            job_id=job.id,
            agent_type=job.agent_type,
            status=job.status,
            result=job.result,
            error=job.error,
        )
        
    background_tasks.add_task(_execute_pr_review, job_id, req.diff)
    return response


@router.post("/documentation", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_documentation(req: DocumentationRequest, background_tasks: BackgroundTasks):
    """Queue an architectural documentation generation job."""
    job_id = str(uuid.uuid4())
    with Session(database_service.engine) as session:
        job = AgentRun(
            id=job_id,
            agent_type="documentation",
            status="pending",
            payload={"repository_id": req.repository_id},
        )
        session.add(job)
        session.commit()
        response = JobResponse(
            job_id=job.id,
            agent_type=job.agent_type,
            status=job.status,
            result=job.result,
            error=job.error,
        )
        
    background_tasks.add_task(_execute_doc_generation, job_id, req.repository_id)
    return response


@router.post("/issues", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_issue_resolver(req: IssueRequest, background_tasks: BackgroundTasks):
    """Queue an issue traceback investigation and patch suggestion job."""
    job_id = str(uuid.uuid4())
    with Session(database_service.engine) as session:
        job = AgentRun(
            id=job_id,
            agent_type="issue_resolver",
            status="pending",
            payload={"repository_id": req.repository_id, "issue_text": req.issue_text},
        )
        session.add(job)
        session.commit()
        response = JobResponse(
            job_id=job.id,
            agent_type=job.agent_type,
            status=job.status,
            result=job.result,
            error=job.error,
        )
        
    background_tasks.add_task(_execute_issue_resolution, job_id, req.repository_id, req.issue_text)
    return response


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Retrieve execution status and outcome of an agent job."""
    with Session(database_service.engine) as session:
        job = session.get(AgentRun, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobResponse(
            job_id=job.id,
            agent_type=job.agent_type,
            status=job.status,
            result=job.result,
            error=job.error,
        )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str):
    """Cancel or remove an execution job from the active tracking list."""
    with Session(database_service.engine) as session:
        job = session.get(AgentRun, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        session.delete(job)
        session.commit()
    return None
