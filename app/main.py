"""This file contains the main application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Request,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from asgi_correlation_id import CorrelationIdMiddleware

from app.api.v1.api import api_router
from app.api.v1.chatbot import agent
from app.core.cache import cache_service
from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import setup_metrics
from app.core.middleware import (
    LoggingContextMiddleware,
    MetricsMiddleware,
    ProfilingMiddleware,
)
from app.core.observability import langfuse_init
from app.services.database import database_service

# Load environment variables
load_dotenv()
langfuse_init()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    logger.info(
        "application_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        api_prefix=settings.API_V1_STR,
    )

    # Initialize cache service
    try:
        await cache_service.initialize()
    except Exception as e:
        logger.exception("cache_initialization_failed", error=str(e))

    # Programmatically run Alembic migrations to ensure schema is up-to-date
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        # Run upgrade head synchronously
        command.upgrade(alembic_cfg, "head")
        logger.info("alembic_migrations_completed_successfully")
    except Exception as e:
        logger.exception("alembic_migrations_failed_at_startup", error=str(e))
        # Fall back to metadata creation if Alembic fails
        try:
            from sqlmodel import SQLModel
            SQLModel.metadata.create_all(database_service.engine)
            logger.info("fallback_metadata_creation_successful")
        except Exception as fallback_err:
            logger.exception("fallback_metadata_creation_failed", error=str(fallback_err))

    # Pre-warm the LangGraph agent: create graph + connection pool at startup
    try:
        await agent.create_graph()
        logger.info("graph_pre_warmed")
    except Exception as e:
        logger.exception("graph_pre_warm_failed", error=str(e))

    # Seed default repositories if not already present
    try:
        from sqlmodel import select, Session
        from app.models.repository import Repository
        with Session(database_service.engine) as session:
            # Denoising Diffusion PyTorch
            stmt = select(Repository).where(Repository.clone_url == "https://github.com/lucidrains/denoising-diffusion-pytorch.git")
            res = session.exec(stmt)
            diffusion_repo = res.first()
            if not diffusion_repo:
                diffusion_repo = Repository(
                    id="dd4568a2-0445-4df7-b8ad-22bafbd2dc8a",
                    name="Denoising Diffusion PyTorch",
                    clone_url="https://github.com/lucidrains/denoising-diffusion-pytorch.git",
                    branch="main",
                    status="pending"
                )
                session.add(diffusion_repo)
                logger.info("seeded_denoising_diffusion_pytorch_repo")
                
            # Starlette
            stmt = select(Repository).where(Repository.clone_url == "https://github.com/encode/starlette.git")
            res = session.exec(stmt)
            starlette_repo = res.first()
            if not starlette_repo:
                starlette_repo = Repository(
                    id="312055a3-c58c-438e-aefe-c60e28319d12",
                    name="Starlette",
                    clone_url="https://github.com/encode/starlette.git",
                    branch="master",
                    status="pending"
                )
                session.add(starlette_repo)
                logger.info("seeded_starlette_repo")
                
            session.commit()
    except Exception as e:
        logger.exception("default_repos_seeding_failed", error=str(e))

    yield

    # Cleanup on shutdown
    await cache_service.close()
    if agent._connection_pool:
        await agent._connection_pool.close()
        logger.info("connection_pool_closed")
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up Prometheus metrics
setup_metrics(app)

# Add logging context middleware (must be added before other middleware to capture context)
app.add_middleware(LoggingContextMiddleware)

# Add custom metrics middleware
app.add_middleware(MetricsMiddleware)

# Add profiling middleware (DEBUG only)
if settings.DEBUG:
    app.add_middleware(ProfilingMiddleware)

# Add correlation ID middleware — must be outermost so request_id is set before all others
app.add_middleware(CorrelationIdMiddleware)


# Add validation exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors from request data.

    Args:
        request: The request that caused the validation error
        exc: The validation error

    Returns:
        JSONResponse: A formatted error response
    """
    # Log the validation error
    logger.error(
        "validation_error",
        client_host=request.client.host if request.client else "unknown",
        path=request.url.path,
        errors=str(exc.errors()),
    )

    # Format the errors to be more user-friendly
    formatted_errors = []
    for error in exc.errors():
        loc = " -> ".join([str(loc_part) for loc_part in error["loc"] if loc_part != "body"])
        formatted_errors.append({"field": loc, "message": error["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": formatted_errors},
    )


# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root(request: Request):
    """Root endpoint returning basic API information."""
    logger.info("root_endpoint_called")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "environment": settings.ENVIRONMENT.value,
        "swagger_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health")
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint with environment-specific information.

    Returns:
        JSONResponse: Health status payload, with HTTP 503 when the
        database is unreachable so load balancers can drop the instance.
    """
    logger.info("health_check_called")

    # Check database connectivity
    db_healthy = await database_service.health_check()

    response = {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "components": {"api": "healthy", "database": "healthy" if db_healthy else "unhealthy"},
        "timestamp": datetime.now().isoformat(),
    }

    # If DB is unhealthy, set the appropriate status code
    status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=response, status_code=status_code)
