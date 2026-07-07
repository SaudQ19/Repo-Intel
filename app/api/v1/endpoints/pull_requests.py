"""Pull request review endpoints powered by GitHub MCP + LLM analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import logger
from app.langgraph.agents.pr_reviewer import PRReviewerAgent

router = APIRouter()
pr_agent = PRReviewerAgent()


class PRReviewResponse(BaseModel):
    """AI-generated pull request review."""

    pr_number: int
    title: str
    summary: str
    what_changed: str
    architectural_impact: str
    potential_risks: str
    possible_bugs: str
    testing_recommendations: str
    review_verdict: str


class PRListItem(BaseModel):
    """Summary of an open pull request."""

    number: int
    title: str
    state: str
    user: str
    created_at: str
    body: str = ""


@router.get("/{owner}/{repo}", response_model=list[PRListItem])
async def list_pull_requests(owner: str, repo: str, state: str = "open"):
    """List pull requests for a repository via GitHub MCP.

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: PR state filter (open, closed, all).

    Returns:
        List of pull request summaries.
    """
    try:
        prs = await pr_agent.list_prs(owner, repo, state)
        return prs
    except Exception as e:
        logger.exception("list_pull_requests_failed", owner=owner, repo=repo, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch pull requests: {str(e)}")


@router.get("/{owner}/{repo}/{pr_number}/review", response_model=PRReviewResponse)
async def review_pull_request(owner: str, repo: str, pr_number: int):
    """Fetch a PR via GitHub MCP and generate an AI review.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        AI-generated review with architectural analysis and recommendations.
    """
    try:
        review = await pr_agent.review_pr(owner, repo, pr_number)
        return review
    except Exception as e:
        logger.exception("review_pull_request_failed", owner=owner, repo=repo, pr_number=pr_number, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to review PR #{pr_number}: {str(e)}")
