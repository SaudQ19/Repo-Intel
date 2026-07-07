# Repo-Intel: Repository Intelligence Platform

Repo-Intel is a production-grade, high-fidelity Repository Intelligence Platform designed to index, explore, search, and analyze codebase architectures semantically. It features a stateful **FastAPI + LangGraph** multi-agent backend framework and a modern, glassmorphic **React + Vite** SPA console.

Using **Tree-sitter AST parsing**, **pgvector** similarity search, and native **GitHub MCP tool servers**, Repo-Intel enables developers (and recruiters) to interact with repositories in real-time—chatting with codebases, auto-reviewing pull requests, inspecting code issues, and generating system specification blueprints.

---

## 🚀 Live Demo & Visual Walkthrough

- **⚡ Live Demo App**: [https://repo-intel-frontend.vercel.app](https://repo-intel-frontend.vercel.app)
- **📹 Video Demonstration**: [Watch the Walkthrough](https://vimeo.com/your-demo-video-link) (Shows AST indexing, chatting, and GitHub MCP reviews)

---

## 🌟 Dual-Experience Design

Repo-Intel is designed with two distinct operational experiences in mind:

### 1. Hosted Demo (Recruiter Experience)
*   **Zero Setup**: Recruiter-friendly demo pre-populated with:
    - **Denoising Diffusion PyTorch** (`lucidrains/denoising-diffusion-pytorch`)
    - **Starlette** (`encode/starlette`)
*   **Strict Security Guardrails**: Indexing, deletion, and write API paths are disabled (`DEMO_MODE=true`) to block arbitrary resource abuse.
*   **Predictable Performance**: Cached similarity lookups and structured mock fallbacks ensure instant responses.

### 2. Self-Hosted Full Version (Developer Experience)
*   **Arbitrary Indexing**: Scan and index any public GitHub repository or local directory path.
*   **AST Code Parser**: Extracts symbols (classes, methods, and functions) for language-aware code understanding.
*   **Dockerized Stack**: Launch FastAPI, React, and PostgreSQL + pgvector locally with a single command.

---

## Key Features

### 💻 Modern Frontend Console (React + Vite)
- **Direct Workspace Navigation**: Replaced old dropdowns with a Slack-style sidebar listing codebases directly.
- **Pulsing Status Indicators**: Displays real-time mini status dots (active, pending, failed) or loading spinners (indexing) as your repositories are processed.
- **Inline Drawer Registration**: A minimalist "+ Register Repository" form slides out at the bottom-left corner of the sidebar, initiating backend tasks instantly.
- **One-Click Specification Generator**: The documentation tab lets you trigger the AST builder to write a unified system architecture blueprint guide with a single click.
- **Dynamic Deletion**: Hovering over any repository exposes a delete button to clean up vectors and databases dynamically.

### 🤖 Stateful Multi-Agent Orchestration (LangGraph + MCP)
- **PR Reviewer Agent**: Inspects Git diffs using GitHub MCP tools to generate reviews (Architectural Impact, Potential Risks, Verdict).
- **Issue Diagnostics Agent**: Retrieves open issues and performs AI root cause analyses and code fixes.
- **AST parser & pgvector**: Walks code trees to generate vector embeddings using `BAAI/bge-small-en-v1.5` and performs cosine distance queries inside PostgreSQL.

---

## Tech Stack
*   **Backend:** FastAPI, LangGraph, SQLModel (SQLAlchemy + Pydantic v2), Alembic, Pyright.
*   **Inference:** 100% Groq API (LLaMA 3.3 / LLaMA 3.1) and HuggingFace Hub.
*   **Frontend:** React 19, Vite, React Router v7, React Markdown, Lucide icons.

---

## Directory Structure

```
├── app/
│   ├── api/v1/                   # REST Route Handlers
│   │   ├── endpoints/
│   │   │   ├── pull_requests.py  # GitHub MCP PR review endpoints
│   │   │   ├── issues.py         # GitHub MCP bug diagnostics endpoints
│   │   │   ├── docs.py           # AST blueprint docs generator
│   │   │   └── repositories.py   # Workspace scanning, indexing, and deletion
│   ├── core/
│   │   ├── langgraph/            # LangGraph agent definitions & tools
│   │   ├── logging.py            # Structured logging (structlog)
│   │   └── database.py           # Async DB engine & session builders
│   ├── indexer/
│   │   ├── parser.py             # Tree-sitter AST & fallback chunker
│   │   └── pipeline.py           # Extracts symbols & writes embeddings
│   ├── models/                   # SQLModel DB Models (Repository, CodeChunk)
│   └── main.py                   # FastAPI Entrypoint & Database Seeder
├── frontend/
│   ├── src/
│   │   ├── components/           # Sidebar & Layout elements
│   │   ├── pages/                # ChatPage, PullRequestsPage, DocsPage, IssuesPage
│   │   └── index.css             # Dark glassmorphic design system
│   └── vercel.json               # Vercel SPA routing configurations
├── docker-compose.yml            # Local DB + API + Frontend orchestrator
└── Makefile                      # Build, test, and dev runners
```

---

## Quick Start (Self-Hosted)

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 18+**
- **PostgreSQL** with the `pgvector` extension (or Docker).

### 2. Environment Setup
Copy the example environment file and populate your credentials:

```bash
cp .env.example .env.development
```

Key variables:
- `GROQ_API_KEY`: Required for LLaMA 3.3 inference.
- `HF_TOKEN`: Required for HuggingFace embeddings extraction.
- `GITHUB_PERSONAL_ACCESS_TOKEN`: Required to fetch PRs/Issues via GitHub MCP.
- `DEMO_MODE`: Set to `true` to enable hosted demo protection.

### 3. Run via Docker Compose (Recommended)
Launch the entire stack (Database, API Backend, Frontend Client) with one command:

```bash
docker compose up --build
```
- Backend API runs on `http://localhost:8000`
- Frontend Console runs on `http://localhost:5173`

---

## Available Make Targets

- `make install` - Installs dependencies using `uv` and pre-commit hooks.
- `make dev` - Starts the FastAPI backend with `--reload-dir app` configuration.
- `make frontend-dev` - Starts the Vite development server.
- `make check` - Runs `ruff` checks and `pyright` typechecking.
- `make migrate` - Performs database migrations.
