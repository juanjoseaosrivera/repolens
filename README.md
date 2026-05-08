# RepoLens

A code analysis system that helps developers navigate massive repositories with less cognitive load. Combines semantic retrieval (RAG over code embeddings), syntactic analysis (AST parsing), and agentic reasoning to answer questions about how a codebase actually works.

## Table of contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Running the full stack](#running-the-full-stack)
- [API reference](#api-reference)
- [Environment variables](#environment-variables)
- [Development](#development)
- [Project structure](#project-structure)
- [Tech stack](#tech-stack)
- [Roadmap](#roadmap)

## Architecture

```
┌──────────────────────┐         ┌─────────────────────────────┐
│   Angular Frontend   │ <─────> │   FastAPI Backend (Python)  │
│  - Chat UI           │  HTTP   │  - REST + SSE streaming     │
│  - Repo selector     │  JSON   │  - Retrieve-then-generate   │
│  - Sources panel     │         │  - arq background workers   │
└──────────────────────┘         └──────────┬──────────────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                  ┌───────────────┐  ┌───────────────┐ ┌──────────────┐
                  │  PostgreSQL   │  │     Redis      │ │  Anthropic / │
                  │  + pgvector   │  │  Job queue +   │ │   OpenAI     │
                  │  HNSW index   │  │  cache         │ │   APIs       │
                  └───────────────┘  └───────────────┘ └──────────────┘
```

**How it works:**

1. **Ingest** — A user submits a Git URL. The backend clones the repo, walks the file tree, splits each file into overlapping line-based chunks, embeds them via OpenAI, and stores everything in Postgres with a pgvector HNSW index.
2. **Retrieve** — When the user asks a question, the query is embedded and a cosine-similarity search returns the top-K most relevant chunks.
3. **Generate** — The retrieved chunks are injected into a system prompt and streamed to Claude via SSE. The user sees tokens appear in real time, plus a sources bar showing which files were used.

For the full architectural rationale, see [`context/architecture-context.md`](context/architecture-context.md).

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Backend runtime |
| **[uv](https://docs.astral.sh/uv/)** | latest | Python package manager |
| **Node.js** | 22+ | Frontend runtime |
| **npm** | 10+ | Frontend package manager |
| **Docker** | 24+ | Infrastructure (Postgres, Redis) |
| **Docker Compose** | v2+ | Container orchestration |
| **Git** | 2.30+ | Cloning repositories for ingestion |

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/juanjoseaosrivera/repolens.git
cd repolens
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
REPOLENS_ANTHROPIC_API_KEY=sk-ant-...   # Required — Claude for generation
REPOLENS_OPENAI_API_KEY=sk-...          # Required — OpenAI for embeddings
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts:
- **PostgreSQL 16** with `pgvector` and `pg_trgm` extensions (port 5432)
- **Redis 7** for the background job queue (port 6379)

Verify both are healthy:

```bash
docker compose ps
```

### 3. Start the backend

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head          # create database tables + HNSW index
uv run uvicorn repolens.api.app:app --reload
```

The API is live at **http://localhost:8000**. Verify: `curl http://localhost:8000/health`

### 4. Start the background worker

In a second terminal:

```bash
cd backend
uv run arq repolens.worker.WorkerSettings
```

The arq worker processes ingestion jobs (clone, chunk, embed, store). Without it, repositories will stay in `pending` status after creation.

### 5. Start the frontend

In a third terminal:

```bash
cd frontend
npm install
npx ng serve
```

The UI is live at **http://localhost:4200**.

## Running the full stack

Once everything is running (Postgres, Redis, backend, worker, frontend):

1. Open **http://localhost:4200**
2. In the left rail, paste a Git clone URL (e.g. `https://github.com/pallets/flask.git`) and click **Add & Ingest**
3. Wait for the status to change from `pending` → `ingesting` → `ready` (refresh the page or re-click the repo)
4. Select the repository and ask a question in the chat (e.g. "Where is routing handled?")
5. Watch the streamed answer appear with source citations

## API reference

All endpoints are served from `http://localhost:8000`. Interactive docs are available at `/docs` when `REPOLENS_DEBUG=true`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — always returns `{"status": "ok"}` |
| `GET` | `/ready` | Readiness probe — returns `{"status": "ready"}` |

### Repositories

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/repos` | Register and ingest a repository |
| `GET` | `/repos` | List all repositories |
| `GET` | `/repos/{id}` | Get a single repository by ID |

**Create a repository:**

```bash
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/pallets/flask.git"}'
```

Response (201):

```json
{
  "id": "a1b2c3d4-...",
  "name": "flask",
  "url": "https://github.com/pallets/flask.git",
  "status": "pending",
  "created_at": "2026-05-08T...",
  "updated_at": "2026-05-08T..."
}
```

Status values: `pending` → `ingesting` → `ready` | `failed`

### Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Ask a question — returns an SSE stream |

**Send a question:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"repository_id": "a1b2c3d4-...", "question": "Where is routing handled?"}'
```

Response is an SSE stream (`Content-Type: text/event-stream`) with three event types:

```
data: {"type": "sources", "data": [{"file_path": "src/flask/app.py", "start_line": 1, "end_line": 60, "score": 0.8742}]}

data: {"type": "token", "data": "Routing"}

data: {"type": "token", "data": " is handled"}

data: [DONE]
```

- **`sources`** — emitted once at the start with retrieved chunk metadata
- **`token`** — emitted per token as the LLM generates
- **`[DONE]`** — signals end of stream

## Environment variables

All variables are prefixed with `REPOLENS_` and loaded from `.env` in the project root. See [`.env.example`](.env.example) for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `REPOLENS_DEBUG` | `false` | Enable debug mode (verbose logging, Swagger docs) |
| `REPOLENS_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `REPOLENS_DATABASE_URL` | `postgresql+psycopg://repolens:repolens@localhost:5432/repolens` | Async PostgreSQL DSN |
| `REPOLENS_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REPOLENS_ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key for Claude |
| `REPOLENS_DEFAULT_MODEL` | `claude-sonnet-4-6` | Default LLM model for generation |
| `REPOLENS_HARD_REASONING_MODEL` | `claude-opus-4-7` | Model for complex reasoning (future) |
| `REPOLENS_LLM_MAX_TOKENS` | `4096` | Max output tokens per completion |
| `REPOLENS_LLM_TEMPERATURE` | `0.0` | LLM sampling temperature |
| `REPOLENS_OPENAI_API_KEY` | — | **Required.** OpenAI API key for embeddings |
| `REPOLENS_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `REPOLENS_EMBEDDING_DIMENSIONS` | `1536` | Embedding vector dimensions |
| `REPOLENS_CLONE_BASE_DIR` | `/tmp/repolens/repos` | Directory for cloned repositories |
| `REPOLENS_CHUNK_SIZE` | `60` | Lines per chunk |
| `REPOLENS_CHUNK_OVERLAP` | `20` | Overlap lines between chunks |
| `REPOLENS_EMBEDDING_BATCH_SIZE` | `100` | Texts per embedding API call |
| `REPOLENS_HOST` | `0.0.0.0` | Server bind address |
| `REPOLENS_PORT` | `8000` | Server port |
| `REPOLENS_CORS_ORIGINS` | `["http://localhost:4200"]` | Allowed CORS origins (JSON array) |

## Development

### Backend

```bash
cd backend

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type-check (strict mode)
uv run mypy src/

# Run unit tests
uv run pytest tests/unit/ -v

# Run all tests with coverage
uv run pytest --cov=repolens --cov-report=term-missing
```

### Frontend

```bash
cd frontend

# Type-check
npx tsc --noEmit

# Build (production)
npx ng build

# Development server (with hot reload)
npx ng serve

# Run unit tests
npx ng test
```

### Database migrations

```bash
cd backend

# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration (after modifying models.py)
uv run alembic revision --autogenerate -m "description of change"

# Downgrade one step
uv run alembic downgrade -1

# View current migration state
uv run alembic current
```

### Pre-commit hooks

Pre-commit hooks run automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

### CI pipeline

GitHub Actions runs on every push and PR:
- **Backend:** ruff lint, ruff format check, mypy strict, pytest
- **Frontend:** TypeScript type-check, Angular build, Angular test

## Project structure

```
repolens/
├── backend/
│   ├── src/repolens/
│   │   ├── api/                 # FastAPI routers and schemas
│   │   │   ├── app.py           # Application factory + lifespan
│   │   │   ├── health.py        # Health/readiness endpoints
│   │   │   ├── repos.py         # POST/GET /repos — CRUD + ingestion trigger
│   │   │   ├── chat.py          # POST /chat — retrieve-then-generate SSE
│   │   │   ├── deps.py          # Dependency injection (DB session, clients)
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   ├── agent/
│   │   │   └── prompts/
│   │   │       └── system_v1.py # System prompt with untrusted-data delimiters
│   │   ├── ingestion/
│   │   │   ├── clone.py         # Async git clone/pull via subprocess
│   │   │   ├── walker.py        # Directory walker (skip binaries, detect language)
│   │   │   ├── chunker.py       # Naive line-based chunker (60 lines, 20 overlap)
│   │   │   └── pipeline.py      # Orchestrator: clone → walk → chunk → embed → store
│   │   ├── retrieval/
│   │   │   └── vector.py        # pgvector cosine similarity search (top-K)
│   │   ├── storage/
│   │   │   ├── models.py        # ORM: Repository, File, Chunk + pgvector column
│   │   │   ├── engine.py        # Async SQLAlchemy engine factory
│   │   │   └── repositories/    # Repository pattern (future CRUD layer)
│   │   ├── llm/
│   │   │   ├── completions.py   # Anthropic Claude wrapper (complete + stream)
│   │   │   └── embeddings.py    # OpenAI embedding wrapper (batch + single)
│   │   ├── config/
│   │   │   └── settings.py      # Pydantic BaseSettings (REPOLENS_ prefix)
│   │   ├── errors/
│   │   │   └── exceptions.py    # Domain exception hierarchy
│   │   ├── observability/
│   │   │   └── logging.py       # structlog configuration
│   │   └── worker.py            # arq background worker for ingestion jobs
│   ├── alembic/
│   │   └── versions/
│   │       └── 0001_initial_schema.py  # Tables + HNSW index
│   ├── tests/
│   │   ├── unit/                # Unit tests (config, errors, health)
│   │   ├── integration/         # Integration tests (future)
│   │   └── eval/                # RAG evaluation tests (future)
│   └── pyproject.toml           # Dependencies, ruff, mypy, pytest config
│
├── frontend/
│   └── src/app/
│       ├── core/
│       │   ├── api.service.ts        # Central HTTP client wrapper
│       │   ├── streaming.service.ts  # SSE via EventSource + fetch ReadableStream
│       │   ├── app-state.service.ts  # Shared signals (selected repo ID)
│       │   └── error.interceptor.ts  # Global HTTP error handler
│       ├── features/
│       │   ├── chat/
│       │   │   ├── chat-shell.component.ts   # Chat UI + SSE streaming wiring
│       │   │   └── chat-shell.component.html # Message list, sources bar, composer
│       │   └── repos/
│       │       └── repo-selector.component.ts # Left-rail repo list + add form
│       ├── app.ts               # Root component
│       ├── app.html             # Layout shell (header, left rail, chat, trace panel)
│       ├── app.routes.ts        # Lazy-loaded routes
│       └── app.config.ts        # DI providers
│
├── context/                     # Project documentation (PRD-derived)
│   ├── project-overview.md      # What RepoLens is, problem, strategy
│   ├── architecture-context.md  # Full architecture and design rationale
│   ├── code-standards.md        # Coding conventions (Python, TypeScript, SQL)
│   ├── progress-tracker.md      # Phase-by-phase checklist and status
│   ├── ai-workflow-rules.md     # AI assistant interaction guidelines
│   └── ui-context.md            # Frontend design system and patterns
│
├── docker/
│   └── initdb/
│       └── 01-extensions.sql    # CREATE EXTENSION vector, pg_trgm
├── docker-compose.yml           # Postgres (pgvector) + Redis
├── .env.example                 # Environment variable template
├── .pre-commit-config.yaml      # Pre-commit hook configuration
└── .github/
    └── workflows/
        └── ci.yml               # GitHub Actions: lint, type-check, test, build
```

## Tech stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic | API, ORM, migrations |
| **LLM** | Claude Sonnet 4.6 (Anthropic) | Chat generation and reasoning |
| **Embeddings** | text-embedding-3-small (OpenAI) | Code chunk embeddings (1536 dims) |
| **Vector search** | PostgreSQL 16 + pgvector | HNSW cosine similarity index |
| **Background jobs** | arq + Redis | Async ingestion pipeline |
| **Frontend** | Angular 21, Tailwind CSS, Signals | Chat UI, repo selector, SSE streaming |
| **Observability** | structlog | Structured JSON logging |
| **CI** | GitHub Actions | ruff, mypy, pytest, tsc, ng build |
| **Infrastructure** | Docker Compose | Local dev: Postgres + Redis |

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** — Foundations | ~80% | Project skeleton, LLM wrappers, tooling |
| **Phase 1** — MVP | ~85% | Naive ingestion, pgvector search, streaming chat, Angular UI |
| **Phase 2** — Advanced RAG | Not started | AST chunking, hybrid retrieval, cross-encoder reranking |
| **Phase 3** — Agent + Graph | Not started | Neo4j, LangGraph agent with tools |
| **Phase 4** — Productionize | Not started | Eval harness, observability, deployment |

See [`context/progress-tracker.md`](context/progress-tracker.md) for the detailed checklist.

## License

Private project. All rights reserved.
