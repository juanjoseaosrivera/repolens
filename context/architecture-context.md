# RepoLens — Architecture Context

This document captures the architectural shape of RepoLens: the components, how they fit together, what each layer is responsible for, and the design decisions (and trade-offs) that drive them. It is the technical companion to `project-overview.md` and is derived from `REPOLENS-PRD.md` v1.1.0.

## 1. Architectural principles

The architecture is shaped by four guiding principles:

- **One database when possible, multiple when necessary.** PostgreSQL holds application data, code-chunk metadata, vector embeddings, and full-text indexes in a single instance. Neo4j is only introduced in Phase 3 when graph queries become a first-class need. The default is fewer moving parts.
- **Hybrid retrieval over pure vector search.** Code is structured. Symbol names matter. RepoLens fuses semantic similarity with lexical (keyword) search and SQL metadata filters before reranking — every retrieval channel earns its place.
- **Agentic, not autocompletive.** A LangGraph state machine drives the answer loop, not a single retrieval-then-generation pass. The agent can choose to search the index, query the graph, read a whole file, or stop and answer.
- **Pluggable cores.** The LLM, the embedding model, the vector store, and the graph store are wrapped behind interfaces so they can be swapped without rewriting the agent or the pipeline.

## 2. System topology

```
┌──────────────────────┐         ┌─────────────────────────────┐
│   Angular Frontend   │ <─────> │   FastAPI Backend (Python)  │
│  - Chat UI           │  HTTPS  │  - REST + SSE/WebSocket     │
│  - Repo selector     │  JSON   │  - LangGraph agent loop     │
│  - Trace side panel  │         │  - Ingestion workers        │
└──────────────────────┘         └──────────┬──────────────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                  ┌───────────────┐  ┌───────────────┐ ┌──────────────┐
                  │  PostgreSQL   │  │     Neo4j     │ │  Anthropic / │
                  │  + pgvector   │  │  (Phase 3+)   │ │   OpenAI     │
                  │  + tsvector   │  │  Graph queries│ │   APIs       │
                  └───────────────┘  └───────────────┘ └──────────────┘
```

Three external services anchor the system: PostgreSQL (always present), Neo4j (Phase 3+), and the LLM/embedding APIs (Anthropic + OpenAI). Redis sits alongside the backend as cache, queue broker, and rate-limit store but is not on the request hot path for retrieval.

## 3. Layered architecture

### 3.1 Frontend layer (Angular 18+)

**Responsibility.** Present the chat UI, the repository selector, and the trace side panel. Stream agent tokens and tool-call events to the user in real time.

**Key choices.**
- Standalone components, Signals, and the new control-flow syntax — no NgModules ceremony.
- `HttpClient` for REST. `EventSource` (SSE) for streaming agent tokens and tool-call updates so the user sees the agent's reasoning as it unfolds.
- State starts as pure Signals; `@ngrx/signals` is held in reserve if state grows.
- Angular Material or PrimeNG for the chat shell, Tailwind CSS for layout. `@angular/cli` with esbuild for builds. SSR is optional and reserved for a marketing surface.

**Boundary.** The frontend never sees API keys. It calls only the FastAPI backend, with CORS locked to the frontend origin.

### 3.2 API layer (FastAPI)

**Responsibility.** Expose REST endpoints and the SSE stream. Validate requests with Pydantic. Authenticate users (OAuth2/OIDC). Hand work off to the agent or to the ingestion queue.

**Key choices.**
- Async-first — FastAPI + `psycopg` v3 async + SQLAlchemy 2.x async — so the agent can fan out to retrieval, graph, and LLM calls without blocking workers.
- OpenAPI auto-spec drives the Angular client's typed models.
- JWT issued to the Angular client; OAuth2/OIDC at the API edge.
- Per-user and per-IP rate limiting, backed by Redis.

### 3.3 Orchestration layer (LangGraph agent)

**Responsibility.** Decide what to do next: retrieve, query the graph, read a file, or answer. Maintain the conversation state. Stream tokens and tool calls back to the API layer.

**Tools available to the agent.**
- `search_code` — hybrid retrieval (vector + lexical + metadata) with reranking.
- `query_graph` — Cypher queries against Neo4j (Phase 3+).
- `read_file` — pulls a full file when macro context is required.

**Key choices.**
- LangGraph for the state machine; LangChain only where it earns its place. Direct Anthropic SDK calls elsewhere.
- Claude Sonnet 4.6 (`claude-sonnet-4-6`) is the default model for agent steps — balanced speed and intelligence. Claude Opus 4.7 (`claude-opus-4-7`) is reserved for the hardest reasoning.
- Retrieved code is wrapped in delimiters and the system prompt declares its content as untrusted data — defense against prompt injection embedded in repository content.

### 3.4 Retrieval layer

**Responsibility.** Given a query, return the snippets the LLM should reason over.

**Pipeline.**
1. **Hybrid candidate generation.** Three channels run in parallel:
   - `pgvector` semantic search (cosine distance, HNSW index).
   - PostgreSQL full-text search (`tsvector`) for symbol/keyword lookup, with `pg_trgm` for fuzzy matches.
   - SQL metadata filters (e.g., `WHERE language = 'python' AND path LIKE 'src/%'`).
2. **Reciprocal Rank Fusion (RRF).** Application-layer fusion combines the rankings without needing a learned model.
3. **Cross-encoder reranking.** A model like BGE-Reranker scores the top candidates; only the top 5 reach the LLM.

**Why this shape.** Pure vector search loses on exact symbol names. Pure keyword search loses on conceptual queries ("where is auth handled"). RRF picks up both winners cheaply, and the cross-encoder pays its compute cost only on a small candidate set.

### 3.5 Storage layer

#### PostgreSQL 16 + `pgvector` + `tsvector` + `pg_trgm`

A single Postgres instance plays three roles:

- **Application data.** Users, ingested repositories, sessions, evaluation runs. Standard relational tables.
- **Code-chunk metadata.** `file_path`, `language`, `symbols_defined`, `imports`, `start_line`, `end_line`, content hash, etc.
- **Vector embeddings.** A `vector(1536)` column with an HNSW index (cosine distance). Embedding dimensions are pinned to OpenAI's `text-embedding-3-small`.

**Why one Postgres instead of a dedicated vector DB.**
- Hybrid filtering is one SQL query: vector similarity joined with `WHERE language = 'python' AND path LIKE 'src/%'`. No cross-store fan-out.
- Operational story is mature: backups, migrations (Alembic), observability, replication.
- Fewer moving parts than running a separate Pinecone/Weaviate/Qdrant alongside.

**Lexical search lives in the same instance.** `tsvector` for ranked keyword search; `pg_trgm` for fuzzy/substring matches on symbol names. `rank_bm25` in-memory remains an option for early prototypes.

#### Neo4j 5 (Phase 3+)

**Responsibility.** Model the structural graph: file-imports-file, function-calls-function, class-extends-class. Answer "who calls X / what imports Y / what does this transitively depend on" — questions that are awkward and slow in SQL.

**Why a separate graph DB.** Cypher's pattern matching is dramatically more expressive for multi-hop queries than recursive CTEs. The cost is a second store to operate, which is why Neo4j is deferred until Phase 3 when the agent actually needs it.

#### Redis

Cache (LLM responses, embeddings), session store, rate-limit counters, and the broker for the background-job queue (`arq` or `dramatiq`).

### 3.6 Ingestion layer (background workers)

**Responsibility.** Turn a repository into searchable, embedded, indexed chunks.

**Stages.**
1. **Clone / fetch.** The source repository is pulled to a working directory.
2. **Parse.** `tree-sitter` produces an AST per file.
3. **Chunk.** Function-level / class-level semantic chunking — never blind character splits. Logical units only.
4. **Enrich.** Each chunk is tagged with `file_path`, `language`, `symbols_defined`, `imports`, line ranges.
5. **Embed.** Chunks are sent to OpenAI's `text-embedding-3-small` in batches.
6. **Index.** Embeddings, metadata, and content land in Postgres. The HNSW index and `tsvector` column are kept up to date.
7. **Graph build (Phase 3+).** A second pass populates Neo4j with the import and call graph.

**Execution model.** `arq` or `dramatiq` workers, Redis-backed. Ingestion is async and idempotent — re-running on the same commit must not duplicate chunks.

## 4. Cross-cutting concerns

### 4.1 Observability

- **Agent traces.** LangSmith captures every agent step, tool call, and prompt — essential for debugging non-deterministic flows.
- **Application logs.** `structlog` for structured JSON logs.
- **Metrics & tracing.** OpenTelemetry-ready, so traces and metrics can be exported to whichever backend the deployment uses.

### 4.2 Evaluation

- **RAG quality** — RAGAS metrics: faithfulness, answer relevance, context precision.
- **Code paths** — pytest for unit and integration tests.
- **Eval runs** are first-class data: stored in Postgres alongside application data, so regressions are queryable.

### 4.3 Security

- **Privacy.** RepoLens is designed to run locally or in private cloud. Repository content never leaves the user's deployment.
- **Prompt injection.** Retrieved code is wrapped in delimiters; the system prompt declares retrieved content as untrusted. Tool-call arguments are validated, not blindly executed.
- **Auth.** OAuth2/OIDC at the API edge; JWTs to the Angular client; CORS locked to the frontend origin.
- **Secrets.** `.env` for local development; a managed secret store (Doppler, AWS Secrets Manager, Fly secrets) in production. API keys never reach the browser.
- **Rate limiting.** Per-user and per-IP throttles on public endpoints, backed by Redis.

### 4.4 Deployment

- Multi-stage Dockerfile per service.
- `docker-compose.yml` for local development: Postgres, Redis, optionally Neo4j.
- Hosted demo targets: Fly.io, Railway, or a VPS.

## 5. Phased build-out (architecture view)

The architecture is intentionally additive — each phase introduces components without forcing a rewrite of earlier ones.

- **Phase 0 — Foundations.** Project skeleton, LLM + embeddings wrappers, tooling. Wraps the swap-points so later phases plug in cleanly.
- **Phase 1 — MVP.** Naive (line-based) ingestion → Postgres + `pgvector`. FastAPI endpoints. A minimal Angular chat shell wired to a streaming endpoint. No agent loop yet — just retrieval-then-generation.
- **Phase 2 — Advanced RAG.** AST-driven chunking. Hybrid retrieval (`pgvector` + Postgres FTS, fused with RRF). Cross-encoder reranking. The Angular UI gains the retrieved-chunks side panel.
- **Phase 3 — Agent + Graph.** Neo4j is introduced. The LangGraph agent gains `search_code`, `query_graph`, and `read_file` tools. Tool calls stream to the Angular UI.
- **Phase 4 — Productionize.** Eval harness, observability wiring, prompt-injection defenses hardened, prompt caching, polished UX, deployment automation.

## 6. Key trade-offs (read this before changing the architecture)

- **Single Postgres vs. dedicated vector DB.** Chosen for operational simplicity and cheap hybrid filtering. The trade-off is that at very large scale (tens of millions of chunks), a dedicated vector DB may outperform `pgvector`. Acceptable today; revisit at scale.
- **Neo4j deferred to Phase 3.** Earlier phases lean on SQL recursive CTEs and metadata filtering. The trade-off is some structural questions are harder to answer pre-Phase-3, but it keeps the early stack lean.
- **LangGraph + selective LangChain.** The agent loop is explicit and inspectable. The trade-off is more code than a "wrap everything in LangChain" approach, but it pays back in debuggability and the freedom to drop LangChain wherever it isn't earning its place.
- **OpenAI embeddings + Claude generation.** Best-in-class on each axis. The trade-off is two API providers to manage; mitigated by the wrapper interfaces from Phase 0.
- **Function-level chunking.** Aligns chunk boundaries with how developers think about code. The trade-off is that very large functions become very large chunks; mitigated by an upper-bound chunk size with overlap.

## 7. Component-to-phase map (quick reference)

| Component | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| FastAPI backend | scaffold | core endpoints | + reranker | + tool-call streaming | hardened |
| Angular frontend | scaffold | chat shell | + chunks panel | + tool-call view | polished |
| PostgreSQL + `pgvector` | schema | populated | + `tsvector` / `pg_trgm` | — | tuned |
| Ingestion workers | wrappers | naive chunking | AST chunking | + graph build | productionized |
| LangGraph agent | — | retrieval-then-gen | — | full agent loop | + caching |
| Neo4j | — | — | — | introduced | tuned |
| Redis | — | sessions / rate limit | + cache | + queue broker | tuned |
| Eval (RAGAS + pytest) | scaffold | smoke tests | RAG metrics | agent metrics | full harness |
| Observability | — | structlog | + traces | + LangSmith | OTEL exporters |

## 8. Source

Architecture context distilled from `REPOLENS-PRD.md` v1.1.0. The PRD remains the authoritative source; this document focuses on the architectural shape and the reasoning behind it.
