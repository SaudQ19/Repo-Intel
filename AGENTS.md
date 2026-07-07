# AI Agent Development Guide

This document provides essential guidelines for AI agents working on this Repo-Intel Repository Intelligence Platform.

## Quick Commands

```bash
make install              # Install dependencies (uv sync) + pre-commit hooks
make dev                  # Start FastAPI backend server with hot reload (port 8000)
make frontend-dev         # Start React/Vite development server (port 5173)
make check                # Run linting + typechecking (Ruff + Pyright)
make migrate              # Run database migrations to latest schema version (Alembic)
```

## Project Structure

```
app/
  api/v1/          # REST Endpoint handlers (chatbot, repositories, pull_requests, etc.)
  core/
    config.py      # Pydantic-based configuration management
    database.py    # Async DB pooling and helper engines
    langgraph/     # Multi-agent graphs and search tools
    logging.py     # structlog configuration
    metrics.py     # Prometheus business metrics
    middleware.py  # starlette request processing middlewares
  models/          # SQLModel database tables (CodeChunk, Repository, AgentRun, Session)
  schemas/         # Pydantic schemas (chat messages, API response structures)
  utils/           # Text helper methods (graph node parsing, token count)
frontend/          # React Vite SPA console
```

## Key Development Rules

### Import Rules
- **All imports MUST be at the top of the file** — never add imports inside functions or classes.

### Logging Rules
- Use **structlog** for all logging.
- Log messages must be **lowercase_with_underscores** (e.g. `"index_started_successfully"`).
- **NO f-strings in structlog events** — pass variables as kwargs.
- Use `logger.exception()` instead of `logger.error()` to preserve tracebacks.
- Example: `logger.info("repository_registered", repo_id=repo.id)`

### Python Style
- Use `async def` for all I/O bound operations.
- All function signatures must have complete type hints.
- Prefer Pydantic models over raw dict objects.
- File naming: lowercase with underscores (e.g. `pull_requests.py`).

### Database Operations
- All database operations must be executed asynchronously using async engines and transactions.

### Key Commandments
1. All logs must follow structured logging formats.
2. All caching should only store successful responses.
3. All imports must be at the top of files.
4. All database operations must be async.
5. All code must pass `make check` (`ruff` + `pyright`).
