# Repository Intelligence Platform (RepoIntel)

RepoIntel is a production-ready, state-of-the-art Repository Intelligence Platform. It combines a stateful **FastAPI + LangGraph** backend agent framework with a modern **React + Vite** frontend console, designed to index, explore, search, and analyze codebases semantically. 

Using **Tree-sitter AST parsing**, **pgvector** similarity search, and multi-agent workflows, RepoIntel enables developers to query code bases, perform automated Pull Request (PR) reviews, generate rich architectural documentation, and investigate issue resolutions.

---

## Key Features

### 💻 Smart Frontend Console (React + Vite)
- **Workspace Repository Management:** Add remote Git URLs (automatically cloned via a shallow clone depth) or point directly to absolute local folders.
- **Repository-specific Chat:** Switch contexts fluidly; session-based history is persisted uniquely per repository workspace.
- **Background Jobs Interface:** Trigger, monitor, and inspect the results of long-running agent workflows (PR Reviews, Documentation builds, Issue Resolution).

### ⚙️ Semantic Code Chunker & AST Indexer (Tree-sitter)
- **Language-Aware AST Parser:** Uses Tree-sitter to parse `.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`, `.rs`, `.cpp`, `.c`, and `.java` files, extracting semantic symbol scopes (classes, functions, and methods).
- **Linear Fallback Chunker:** Grabs clean, configurable line ranges for unsupported extensions, ensuring full repository coverage.
- **Vector Search Cache:** Generates embeddings and upserts code chunks directly into PostgreSQL via `pgvector` for semantic search queries.

### 🤖 Stateful Multi-Agent Orchestration (LangGraph)
- **PR Reviewer Agent:** Analyzes raw Git diff payloads to pinpoint potential bugs, architectural deviations, and optimization patterns.
- **Doc Builder Agent:** Iterates over the repository symbols to compile holistic, markdown-formatted system documentation.
- **Issue Resolver Agent:** Resolves bugs and stack traces by querying relevant files and proposing code repairs.
- **State Checkpointing:** Employs SQLAlchemy checkpoint savers to store agent trace/graph state over long-running processes.

---

## Architecture & Tech Stack

```
                     ┌──────────────────┐
                     │   React Frontend │
                     └────────┬─────────┘
                              │ REST API
                              ▼
 ┌───────────────────────────────────────────────────────────┐
 │                   FastAPI Backend Server                  │
 │                                                           │
 │  ┌──────────────────┐ ┌────────────────┐ ┌─────────────┐  │
 │  │ Indexing Pipeline│ │ LangGraph      │ │ Background  │  │
 │  │ (Tree-sitter AST)│ │ Agent Workflows│ │ Task Runner │  │
 │  └────────┬─────────┘ └───────┬────────┘ └──────┬──────┘  │
 └───────────┼───────────────────┼─────────────────┼─────────┘
             │ Vector Embeddings │ State/Runs      │ DB Read/Write
             ▼                   ▼                 ▼
 ┌───────────────────────────────────────────────────────────┐
 │                  PostgreSQL DB (pgvector)                 │
 └───────────────────────────────────────────────────────────┘
```

- **Backend:** FastAPI, LangGraph, SQLModel (SQLAlchemy + Pydantic v2), Alembic, Pyright.
- **LLM/Embeddings:** Groq (primary inference e.g. LLaMA 3.3) & OpenAI (embeddings fallback e.g. text-embedding-3-small).
- **Frontend:** Vite, React, Vanilla CSS.

---

## Directory Structure

```
├── app/
│   ├── api/v1/                   # REST Route Handlers
│   │   ├── endpoints/
│   │   │   ├── jobs.py           # Background agent execution (PR reviews, docs, issues)
│   │   │   └── repositories.py   # Workspace registration, scanning, and indexing
│   │   ├── chatbot.py            # Conversational agent chat endpoint
│   │   └── api.py                # Main API router setup
│   ├── core/
│   │   ├── langgraph/            # LangGraph agent definitions & tools
│   │   ├── prompts/              # Core agent prompts
│   │   ├── logging.py            # Structured logging (structlog)
│   │   └── database.py           # Async DB engine & session builders
│   ├── indexer/
│   │   ├── parser.py             # Tree-sitter AST & fallback chunker
│   │   └── pipeline.py           # Scans directories, extracts symbols, writes embeddings
│   ├── models/                   # SQLModel DB Models (Repository, CodeChunk, AgentRun)
│   ├── schemas/                  # Pydantic schemas (Graph state, API payloads)
│   └── main.py                   # FastAPI Application Entrypoint
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Console Interface (Workspace + Chat + Jobs Panels)
│   │   ├── index.css             # Main styling system
│   │   └── main.jsx              # React Entrypoint
├── alembic/                      # Database migrations
└── Makefile                      # Build, test, migration, and runner commands
```

---

## Getting Started

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 18+**
- **PostgreSQL** with the `pgvector` extension enabled.

### 2. Environment Setup
Copy the example environment file and populate your credentials:

```bash
cp .env.example .env.development
```

Key variables in `.env.development`:
- `GROQ_API_KEY`: Required for LLM execution.
- `OPENAI_API_KEY`: Required for generating semantic embeddings.
- `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`: Your database credentials.

### 3. Installation & Database Migration
Set up your virtual environment, install dependencies, and run the Alembic migrations:

```bash
# Install pip dependencies (using uv) and dev tools
make install

# Apply database migrations to head
make migrate
```

### 4. Running the Applications

#### Start Backend Server
Run the FastAPI developer server (runs on `http://localhost:8000`):

```bash
make dev
```

#### Start Frontend Client
Navigate to the frontend directory, install web dependencies, and start the development server (runs on `http://localhost:5173`):

```bash
cd frontend
npm install
npm run dev
```

---

## Available Make Targets

The following targets are available in the root `Makefile`:

- `make install` - Installs Python dependencies using `uv` and initializes pre-commit hooks.
- `make dev` - Starts the FastAPI reload server on port 8000.
- `make migrate` - Upgrades the DB schema to the latest migration version.
- `make migration MSG="description"` - Generates a new autogenerated Alembic database migration.
- `make check` - Lints and runs typechecking (`ruff check` + `pyright`).
- `make docker-up` - Spins up API and PostgreSQL databases in background containers.
- `make stack-up` - Launches full deployment stack (API, DB, Prometheus, Grafana).

---

## Coding Guidelines

When contributing, ensure all rules in [AGENTS.md](AGENTS.md) are strictly adhered to:
1. **Imports:** Always at the top of the file; never inside functions or classes.
2. **Logging:** Use `structlog` exclusively. Messages must be `lowercase_with_underscores`. Pass parameters as `kwargs` instead of using f-strings inside the event message.
3. **Database Operations:** Always perform database reads, writes, and transactions asynchronously.
4. **Retry Logic:** Use the `tenacity` library for exponential backoff on flaky operations.
5. **Linting & Formatting:** Ensure code passes `make check` before opening a pull request.

