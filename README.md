# RepoLens

Code analysis system that helps developers navigate massive repositories. Combines AST parsing, RAG over code embeddings, and agentic reasoning.

## Prerequisites

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/)
- **Node.js 22+** and npm
- **Docker** and Docker Compose

## Quick start

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL 16 (with pgvector + pg_trgm) and Redis.

### 2. Backend

```bash
cd backend
cp ../.env.example .env          # edit with real API keys
uv sync --all-extras
uv run uvicorn repolens.api.app:app --reload
```

The API is at http://localhost:8000. Health check: `GET /health`.

### 3. Frontend

```bash
cd frontend
npm install
npx ng serve
```

The UI is at http://localhost:4200.

## Development

### Backend

```bash
cd backend
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run mypy src/repolens/        # type-check
uv run pytest tests/unit/ -v     # test
```

### Frontend

```bash
cd frontend
npx tsc --noEmit                 # type-check
npx ng build                     # build
npx ng test                      # test
```

### Migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

## Project structure

```
backend/
  src/repolens/
    api/            # FastAPI routers, request/response models
    agent/          # LangGraph state machine, tools, prompts
    ingestion/      # parsers, chunkers, embedding pipeline
    retrieval/      # hybrid search, reranking, RRF fusion
    storage/        # SQLAlchemy models, repositories, migrations
    llm/            # Anthropic / OpenAI wrappers
    config/         # settings, env loading
    errors/         # domain exception hierarchy
    observability/  # structured logging
  tests/
  alembic/

frontend/
  src/app/
    core/           # API client, auth, config
    shared/         # reusable components
    features/
      chat/         # chat UI
      repos/        # repo selector
      traces/       # agent trace panel

context/            # project docs (PRD, architecture, standards)
```

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy 2.x async, Alembic, structlog
- **LLMs:** Claude Sonnet 4.6 (agent), OpenAI text-embedding-3-small (embeddings)
- **Frontend:** Angular 18+, Tailwind CSS, SSE streaming
- **Data:** PostgreSQL 16 + pgvector + pg_trgm, Redis
- **CI:** GitHub Actions (ruff, mypy, pytest, tsc, ng build, ng test)

## Roadmap

See `context/progress-tracker.md` for current status.
