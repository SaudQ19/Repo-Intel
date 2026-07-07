"""API v1 router configuration with all endpoint groups."""

from fastapi import APIRouter

from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.endpoints.repositories import router as repositories_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.pull_requests import router as pull_requests_router
from app.api.v1.endpoints.issues import router as issues_router
from app.api.v1.endpoints.docs import router as docs_router
from app.core.logging import logger

api_router = APIRouter()

# Core routes
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["Chat"])
api_router.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])

# GitHub MCP-powered routes
api_router.include_router(pull_requests_router, prefix="/pull-requests", tags=["Pull Requests"])
api_router.include_router(issues_router, prefix="/issues", tags=["Issues"])
api_router.include_router(docs_router, prefix="/docs", tags=["Documentation"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
