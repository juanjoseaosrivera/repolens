# RepoLens — Project Overview

**Version:** 1.1.0
**Status:** Definition / In Development
**Owner:** Juan Jose Aos Rivera (AI Engineer)

## What it is

RepoLens is a second-generation code analysis system that helps developers navigate massive repositories with less cognitive load. It goes beyond generic chat assistants by combining three layers of understanding:

1. **Syntactic analysis** via Abstract Syntax Trees (`tree-sitter`).
2. **Semantic retrieval** via Retrieval-Augmented Generation (RAG) over code embeddings.
3. **Agentic reasoning** that can plan multi-step lookups across vector, lexical, and graph stores.

The result is an assistant that understands not just "what this file says" but "how this codebase works" — its architecture, dependencies, and business logic.

## The problem

Developers lose up to 30% of their time trying to understand existing codebases. RepoLens targets the three pain points that drive that waste:

- **Slow onboarding** — figuring out where the core logic actually lives.
- **Hidden dependencies** — making changes without seeing the non-obvious side effects.
- **Stale documentation** — written docs rarely match the real state of the code.

## Strategic objectives

- **Contextual understanding.** Answers consider the current file *plus* its imports and the global data flow.
- **Efficient navigation.** Cut feature-discovery time by ~50%.
- **Maintainability.** A modular architecture where LLMs and vector stores can be swapped with minimal effort.

## How it works (architecture in brief)

**Ingestion pipeline.** `tree-sitter` parses each repo into an AST. Code is chunked at the function/class level (semantic chunking, not by character count) and each chunk is enriched with metadata: `file_path`, `symbols_defined`, `imports`, `language`, line ranges.

**Hybrid storage.** A single PostgreSQL 16 instance plays three roles: application data (users, repos, sessions, eval runs), code-chunk metadata, and vector embeddings (`pgvector`, `vector(1536)`, HNSW index, cosine distance). Lexical search lives in the same Postgres via `tsvector` + `pg_trgm`. A separate Neo4j graph database arrives in Phase 3 for "who calls X / what imports Y" queries that don't model well in SQL.

**Retrieval.** Hybrid retrieval fuses `pgvector` semantic search, SQL metadata filters, and Postgres full-text/`pg_trgm` lexical search via Reciprocal Rank Fusion. A cross-encoder (e.g., BGE-Reranker) refines the top results before they reach the LLM.

**Agent loop.** LangGraph drives a cyclic agent that can choose to search the vector index, query the dependency graph, or read a full file when macro context is required.

**End-to-end shape.** An Angular 18+ frontend (standalone components, Signals, SSE streaming) talks to a FastAPI backend (async, Pydantic, OpenAPI). The backend orchestrates the agent and fans out to PostgreSQL, Neo4j (Phase 3+), and Anthropic/OpenAI APIs.

## Technology stack at a glance

- **Backend:** Python 3.12+, FastAPI, LangGraph, SQLAlchemy 2.x async + `psycopg` v3, Alembic, `arq`/`dramatiq` for ingestion jobs.
- **LLMs:** Claude Sonnet 4.6 for routine agent steps, Claude Opus 4.7 for the hardest reasoning. OpenAI `text-embedding-3-small` (1536 dims) for embeddings.
- **Frontend:** Angular 18+, Angular Material or PrimeNG, Tailwind CSS, `HttpClient` + `EventSource` (SSE) for streaming.
- **Data:** PostgreSQL 16 + `pgvector` + `pg_trgm`; Neo4j 5 in Phase 3+; Redis for cache, sessions, rate limiting, and the background-job queue.
- **Platform:** LangSmith for agent traces, `structlog` + OpenTelemetry-ready logging, RAGAS + pytest for evaluation, multi-stage Docker builds with `docker-compose` for local dev and Fly.io/Railway/VPS for hosted demos.

## Primary user stories

- **US.1 (High)** — A developer asks where authentication is managed and gets the exact files.
- **US.2 (Medium)** — An architect generates a flow diagram of how data travels from controller to DB.
- **US.3 (High)** — A lead engineer asks: if I change the signature of `process_payment`, what other modules are affected?
- **US.4 (Low)** — A DevOps engineer requests a summary of environment variables the project needs.

## Evaluation framework

RepoLens is measured under RAGAS:

- **Faithfulness** — does the answer actually come from the source code?
- **Answer relevance** — how useful is the answer to the developer's question?
- **Context precision** — are the retrieved snippets the ones actually needed?

## Roadmap

- **Phase 0 — Foundations.** Project skeleton, LLM + embeddings wrappers, tooling.
- **Phase 1 — MVP.** Naive ingestion → Postgres + `pgvector`; FastAPI endpoints; minimal Angular chat shell on a streaming endpoint.
- **Phase 2 — Advanced RAG.** AST chunking, hybrid retrieval (`pgvector` + Postgres FTS, RRF), cross-encoder reranking. Retrieved-chunks side panel in the UI.
- **Phase 3 — Agent + Graph.** Neo4j added; LangGraph agent gains `search_code` / `query_graph` / `read_file` tools; streaming tool calls in the UI.
- **Phase 4 — Productionize.** Eval harness, observability, prompt-injection defenses, prompt caching, polished UX, deployment.

## Security posture

- **Privacy.** Designed to run locally or in private cloud; repo content never leaves the user's deployment.
- **Prompt-injection defense.** Retrieved code is wrapped in delimiters and the system prompt declares it as untrusted data.
- **Auth.** OAuth2 / OIDC at FastAPI; JWT to Angular; CORS locked to the frontend origin.
- **Secrets.** `.env` for local; managed secret store (Doppler, AWS Secrets Manager, Fly secrets) in production. API keys never reach the browser.
- **Rate limiting.** Per-user and per-IP throttling on public endpoints, backed by Redis.

## Source

This overview is distilled from `REPOLENS-PRD.md` (v1.1.0). Refer to the PRD for the authoritative specification.
