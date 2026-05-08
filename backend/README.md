# RepoLens — Backend

FastAPI backend for the RepoLens code analysis system. Handles repository ingestion, semantic search, and LLM-powered Q&A over code.

## Setup

```bash
# Install dependencies
uv sync --all-extras

# Configure environment
cp ../.env.example ../.env   # edit with real API keys

# Start infrastructure (from project root)
docker compose up -d

# Apply database migrations
uv run alembic upgrade head

# Start the API server
uv run uvicorn repolens.api.app:app --reload
```

The API is available at **http://localhost:8000**. Swagger docs at `/docs` (when `REPOLENS_DEBUG=true`).

## Background worker

Ingestion jobs run asynchronously via arq (Redis-backed). Start the worker in a separate terminal:

```bash
uv run arq repolens.worker.WorkerSettings
```

Without the worker, repositories created via `POST /repos` will remain in `pending` status.

## Module reference

### `repolens.api` — HTTP layer

| File | Description |
|------|-------------|
| `app.py` | FastAPI application factory with CORS middleware and lifespan handler |
| `health.py` | `GET /health` (liveness) and `GET /ready` (readiness) probes |
| `repos.py` | `POST /repos` (create + enqueue ingestion), `GET /repos`, `GET /repos/{id}` |
| `chat.py` | `POST /chat` — retrieve-then-generate with SSE streaming response |
| `deps.py` | Dependency injection providers: DB session, CompletionClient, EmbeddingClient |
| `schemas.py` | Pydantic models: `RepoCreate`, `RepoOut`, `ChatRequest`, `ChunkContext` |

### `repolens.ingestion` — Code ingestion pipeline

| File | Description |
|------|-------------|
| `clone.py` | Async git clone/pull via subprocess. Returns `(local_path, commit_hash)`. Derives safe directory names from URLs. |
| `walker.py` | Recursive directory walker. Skips binary files, hidden directories, `node_modules`, `__pycache__`, etc. Detects language from file extension. Skips files > 512 KiB. |
| `chunker.py` | Naive line-based chunker. Default: 60 lines per chunk with 20-line overlap. Returns `RawChunk(content, start_line, end_line)`. Phase 2 replaces this with AST-aware chunking. |
| `pipeline.py` | Orchestrates the full pipeline: set status → clone → walk → chunk → batch embed → store → set ready. Supports idempotent re-ingestion via content-hash (commit SHA) comparison. Clears old data before re-ingesting. |

**Ingestion flow:**

```
POST /repos (url) → create Repository (pending)
                   → enqueue arq job

arq worker picks up job:
  1. Set status = "ingesting"
  2. git clone --depth=1 (or git pull if exists)
  3. Compare HEAD SHA with stored content_hash → skip if unchanged
  4. Walk files → chunk each file → collect all texts
  5. Batch embed via OpenAI (100 texts per API call)
  6. Store File + Chunk rows in Postgres (with pgvector embedding)
  7. Set status = "ready"
```

### `repolens.retrieval` — Semantic search

| File | Description |
|------|-------------|
| `vector.py` | pgvector cosine distance search. Embeds the query, runs `1 - cosine_distance` as similarity score, returns top-K `ChunkResult` objects with file path, line range, content, language, and score. |

### `repolens.llm` — LLM and embedding wrappers

| File | Description |
|------|-------------|
| `completions.py` | `CompletionClient` — async wrapper around Anthropic Messages API. Supports `complete()` (full response) and `stream()` (token-by-token `AsyncIterator[str]`). Logs token usage via structlog. |
| `embeddings.py` | `EmbeddingClient` — async wrapper around OpenAI Embeddings API. `embed(texts)` for batches, `embed_single(text)` for convenience. Logs batch size and token usage. |

All business logic calls these wrappers, never the SDKs directly.

### `repolens.storage` — Database layer

| File | Description |
|------|-------------|
| `models.py` | SQLAlchemy ORM models: `Repository`, `File`, `Chunk`. Includes `UUIDPrimaryKeyMixin`, `TimestampMixin`, pgvector `Vector(1536)` column, HNSW index definition. |
| `engine.py` | `build_engine()` — creates async SQLAlchemy engine + session factory from settings. |
| `repositories/` | Placeholder for the repository pattern (CRUD abstraction over raw queries). |

### `repolens.agent` — Agent and prompts

| File | Description |
|------|-------------|
| `prompts/system_v1.py` | System prompt for retrieve-then-generate. Instructs the LLM to answer from retrieved context only, cite file paths, and treat code context as untrusted data. |

### `repolens.config` — Configuration

| File | Description |
|------|-------------|
| `settings.py` | Pydantic `BaseSettings` with `REPOLENS_` prefix. Single source of truth for all config: DB, Redis, LLM, embeddings, ingestion, server. Loaded from `.env`. Cached singleton via `get_settings()`. |

### `repolens.errors` — Exception hierarchy

```
RepoLensError (base)
├── IngestionError     — clone, parse, chunk, embed, index failures
├── RetrievalError     — search failures
├── AgentError         — agent loop failures
├── ConfigurationError — missing/invalid config
├── StorageError       — database operation failures
├── CompletionError    — LLM API failures (in llm.completions)
└── EmbeddingError     — embedding API failures (in llm.embeddings)
```

### `repolens.observability` — Logging

| File | Description |
|------|-------------|
| `logging.py` | `setup_logging()` configures structlog: JSON in production, pretty console in dev. Suppresses noisy third-party loggers (uvicorn.access, httpx). |

### `repolens.worker` — Background jobs

| File | Description |
|------|-------------|
| `worker.py` | arq `WorkerSettings`: defines `ingest_repo` task, startup (creates DB engine), and Redis settings from config. Start with `arq repolens.worker.WorkerSettings`. |

## Database schema

Three tables, created by migration `0001_initial_schema`:

```sql
repositories
├── id          UUID PK
├── name        VARCHAR(255)
├── url         VARCHAR(2048) UNIQUE
├── clone_path  VARCHAR(2048) NULL
├── content_hash VARCHAR(64) NULL    -- HEAD commit SHA for dedup
├── status      VARCHAR(20)          -- pending | ingesting | ready | failed
├── created_at  TIMESTAMPTZ
└── updated_at  TIMESTAMPTZ

files
├── id              UUID PK
├── repository_id   UUID FK → repositories.id ON DELETE CASCADE
├── path            VARCHAR(2048)
├── content_hash    VARCHAR(64)     -- SHA-256 of file content
├── language        VARCHAR(50) NULL
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ
    Indexes: repository_id, content_hash

chunks
├── id            UUID PK
├── file_id       UUID FK → files.id ON DELETE CASCADE
├── content       TEXT
├── content_hash  VARCHAR(64)       -- SHA-256 of chunk content
├── start_line    INTEGER
├── end_line      INTEGER
├── token_count   INTEGER NULL
├── embedding     VECTOR(1536) NULL -- pgvector
├── created_at    TIMESTAMPTZ
└── updated_at    TIMESTAMPTZ
    Indexes: file_id, content_hash,
             embedding (HNSW, vector_cosine_ops, m=16, ef_construction=64)
```

## Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Create a new auto-generated migration
uv run alembic revision --autogenerate -m "description"

# Downgrade one step
uv run alembic downgrade -1

# View migration history
uv run alembic history

# View current state
uv run alembic current
```

Alembic reads the database URL from `repolens.config.get_settings()` (not from `alembic.ini`), so the `.env` file is the single source of truth.

## Testing

```bash
# Unit tests
uv run pytest tests/unit/ -v

# All tests with coverage
uv run pytest --cov=repolens --cov-report=term-missing

# Single test file
uv run pytest tests/unit/test_health.py -v
```

Test tiers:
- `tests/unit/` — fast, no external dependencies
- `tests/integration/` — requires Postgres (future)
- `tests/eval/` — RAG quality evaluation (future, Phase 2+)

## Linting and type-checking

```bash
# Lint
uv run ruff check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/

# Type-check (strict mode)
uv run mypy src/
```

Ruff is configured in `pyproject.toml` with rules for pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, bugbear, builtins, bandit, print detection, and ruff-specific rules.
