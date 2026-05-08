# RepoLens — Progress Tracker

A living document tracking RepoLens development against the roadmap defined in `REPOLENS-PRD.md`. Update this file as work progresses — it is the single source of truth for "where are we?" questions.

**Last updated:** 2026-05-08
**Current phase:** Phase 0 — Foundations
**Overall status:** 🟡 In Definition / Early Foundations

---

## 1. Snapshot

| Phase | Status | Progress | Target |
| :--- | :--- | :--- | :--- |
| Phase 0 — Foundations | 🟡 In progress | ~80% | — |
| Phase 1 — MVP | 🟡 In progress | ~85% | — |
| Phase 2 — Advanced RAG | ⚪ Not started | 0% | — |
| Phase 3 — Agent + Graph | ⚪ Not started | 0% | — |
| Phase 4 — Productionize | ⚪ Not started | 0% | — |

**Status legend:** 🟢 Done · 🟡 In progress · 🔵 Blocked · ⚪ Not started · 🔴 At risk

---

## 2. Phase 0 — Foundations

> **Goal:** Project skeleton, LLM + embeddings wrappers, tooling.

### 2.1 Repository scaffolding
- [x] PRD authored (`REPOLENS-PRD.md` v1.1.0)
- [x] Context folder bootstrapped (`context/project-overview.md`, `context/architecture-context.md`, `context/code-standards.md`, `context/ai-workflow-rules.md`, `context/ui-context.md`, `context/progress-tracker.md`)
- [x] Backend skeleton — `backend/` with `pyproject.toml`, `ruff`, `mypy`, `pytest`
- [x] Frontend skeleton — `frontend/` with `@angular/cli` 18+, Tailwind, ESLint, Prettier
- [x] Pre-commit hooks (ruff, mypy, eslint, prettier)
- [x] CI pipeline scaffold (lint + test + type-check)
- [x] `docker-compose.yml` for local dev (Postgres, Redis)
- [x] `.env.example` with documented variables
- [x] Top-level `README.md` covering setup, run, test

### 2.2 Backend foundations
- [x] FastAPI app skeleton (`repolens.api`)
- [x] Settings via Pydantic `BaseSettings` (`repolens.config`)
- [x] Structured logging (`structlog`) wired
- [x] Domain exception hierarchy (`repolens.errors`)
- [x] LLM wrapper interface (`repolens.llm`) with Anthropic client
- [x] Embedding wrapper interface (`repolens.llm`) with OpenAI client
- [x] Health and readiness endpoints
- [x] Initial Alembic setup

### 2.3 Frontend foundations
- [x] Angular 18+ standalone bootstrap
- [x] Tailwind + design token scaffolding (`styles.scss` design tokens)
- [x] Routing skeleton (`app.routes.ts`)
- [x] Core HTTP client and error interceptor
- [x] Streaming service (SSE) skeleton
- [x] Layout shell (top bar / left rail / chat surface / trace panel placeholders)

### 2.4 Quality gates
- [x] `ruff check`, `ruff format` enforced in CI
- [x] `mypy --strict` enforced for new code
- [x] `eslint`, `tsc --noEmit` enforced in CI
- [x] Test runner wired (pytest, Jest or Karma)
- [ ] Conventional Commits enforced via commitlint or equivalent

**Phase 0 exit criteria:** A contributor can clone the repo, run `docker-compose up`, hit a health endpoint from FastAPI, and load an empty Angular shell. CI runs green on a no-op PR.

---

## 3. Phase 1 — MVP

> **Goal:** Naive ingestion pipeline → Postgres + `pgvector`; FastAPI endpoints; minimal Angular chat shell wired to a streaming endpoint.

### 3.1 Ingestion (naive)
- [x] Repository fetch / clone utility
- [x] Naive line/character-based chunker
- [x] Embedding pipeline (batched calls to OpenAI)
- [x] Postgres schema for repositories, files, chunks
- [x] `pgvector` HNSW index on chunk embeddings
- [x] Background worker (`arq` or `dramatiq`) for ingestion jobs
- [x] Idempotent re-ingestion (content-hash dedup)

### 3.2 Retrieval (naive)
- [x] Semantic search endpoint over `pgvector`
- [x] Top-K returned with metadata (`file_path`, line range)

### 3.3 Generation (retrieve-then-generate)
- [x] System prompt v1 (versioned in `agent/prompts/`)
- [x] Single-pass retrieve-then-generate flow
- [x] SSE streaming endpoint for answers

### 3.4 Frontend MVP
- [x] Chat surface — message list, composer
- [x] Streaming integration (SSE → message bubble)
- [x] Repository selector (basic dropdown)
- [x] Empty / loading / error states
- [ ] Auth-gate placeholder (mock auth acceptable in Phase 1)

### 3.5 Auth
- [ ] OAuth2/OIDC at API edge
- [ ] JWT to Angular client
- [x] CORS policy locked to frontend origin

**Phase 1 exit criteria:** A user can sign in, ingest a small public repo, and receive a streamed answer to a basic question with a file-path citation.

---

## 4. Phase 2 — Advanced RAG

> **Goal:** AST chunking, hybrid retrieval (`pgvector` + Postgres FTS, RRF), cross-encoder reranking. Frontend gains the retrieved-chunks side panel.

### 4.1 AST-based ingestion
- [ ] `tree-sitter` integration for target languages (start with Python + TypeScript)
- [ ] Function / class-level chunker
- [ ] Chunk metadata enrichment: `symbols_defined`, `imports`, `start_line`, `end_line`
- [ ] Sensitive-content filter at ingestion (`.env`, key patterns)

### 4.2 Hybrid retrieval
- [ ] Postgres FTS (`tsvector`) + `pg_trgm` indexes
- [ ] SQL metadata filter layer
- [ ] Reciprocal Rank Fusion (RRF) at the application layer
- [ ] Configurable retrieval top-K and weights

### 4.3 Reranking
- [ ] Cross-encoder integration (e.g., BGE-Reranker)
- [ ] Reranker behind a wrapper for swappability
- [ ] Top 5 final chunks to LLM (configurable)

### 4.4 Frontend — trace panel v1
- [ ] Retrieved-chunks side panel
- [ ] Chunk view: file path, line range, language, syntax-highlighted content
- [ ] Citation linking (click citation → focus chunk)
- [ ] Collapsible side panel

### 4.5 Eval
- [ ] Curated eval set of real questions on real repos (≥30 cases to start)
- [ ] RAGAS metric runners: faithfulness, answer relevance, context precision
- [ ] Eval runs persisted in Postgres
- [ ] CI eval gate with regression tolerance

**Phase 2 exit criteria:** Hybrid retrieval and reranking deliver measurable improvements on the eval set vs. Phase 1 baseline. The trace panel surfaces every chunk used.

---

## 5. Phase 3 — Agent + Graph

> **Goal:** Add Neo4j; LangGraph agent with `search_code` / `query_graph` / `read_file` tools; streaming tool calls to the Angular UI.

### 5.1 Graph database
- [ ] Neo4j 5 added to `docker-compose.yml`
- [ ] Graph schema: `:File`, `:Function`, `:Class`, `:IMPORTS`, `:CALLS`, `:DEFINES`
- [ ] Graph-build pass during ingestion
- [ ] Cypher query layer behind a wrapper

### 5.2 LangGraph agent
- [ ] State machine definition (typed state, named nodes/edges)
- [ ] Tool: `search_code` (hybrid retrieval + rerank)
- [ ] Tool: `query_graph` (Cypher queries)
- [ ] Tool: `read_file` (bounded full-file read)
- [ ] Loop guards (max steps, max token budget)
- [ ] Prompt-injection delimiters and untrusted-content policy

### 5.3 Streaming tool calls
- [ ] Backend emits tool-call events on the SSE stream
- [ ] Frontend renders tool calls in the trace panel in order
- [ ] Tool-call entries update in place when results arrive

### 5.4 Eval
- [ ] Agent-specific eval cases (multi-hop, refactor-impact)
- [ ] Prompt-injection regression tests
- [ ] Latency / cost dashboards per agent run

**Phase 3 exit criteria:** Multi-hop questions ("if I change `process_payment`, what breaks?") return correct, cited answers. The trace panel shows the agent's tool sequence in real time.

---

## 6. Phase 4 — Productionize

> **Goal:** Eval harness, observability, prompt-injection defenses, prompt caching, polished Angular UX, deployment.

### 6.1 Observability
- [ ] LangSmith traces for all agent runs
- [ ] OpenTelemetry exporters for app metrics + traces
- [ ] Frontend error reporting with trace-ID propagation

### 6.2 Performance and cost
- [ ] Embedding cache by content hash (Redis)
- [ ] LLM response cache by prompt hash (Redis)
- [ ] Prompt caching enabled where supported by Anthropic

### 6.3 Security hardening
- [ ] Prompt-injection eval suite enforced in CI
- [ ] Secrets via managed store in production
- [ ] Per-user / per-IP rate limiting (Redis-backed)
- [ ] Security review checklist completed

### 6.4 Frontend polish
- [ ] Keyboard shortcut surface complete (`?` cheatsheet)
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Performance budgets enforced in CI
- [ ] Dark/light theme finalized

### 6.5 Deployment
- [ ] Multi-stage Dockerfile per service
- [ ] Hosted demo on Fly.io / Railway / VPS
- [ ] Production runbook (`docs/runbook.md`)
- [ ] Backup / restore documented and tested

**Phase 4 exit criteria:** A new user can sign up to the hosted demo, ingest a public repo, and use RepoLens with predictable latency, observability, and cost.

---

## 7. User story tracking

| ID | User | Requirement | Priority | Phase | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| US.1 | Developer | "Where is authentication managed?" → exact files | High | 1–2 | ⚪ Not started |
| US.2 | Architect | Generate a flow diagram from controller to DB | Medium | 3 | ⚪ Not started |
| US.3 | Lead Engineer | Impact analysis if `process_payment` signature changes | High | 3 | ⚪ Not started |
| US.4 | DevOps | Summary of required environment variables | Low | 2 | ⚪ Not started |

---

## 8. Evaluation metrics (latest run)

To be populated when the eval harness lands in Phase 2.

| Metric | Phase 1 baseline | Phase 2 target | Latest | Δ |
| :--- | :---: | :---: | :---: | :---: |
| Faithfulness | — | ≥ 0.85 | — | — |
| Answer Relevance | — | ≥ 0.80 | — | — |
| Context Precision | — | ≥ 0.75 | — | — |

Eval run history lives in Postgres; this table mirrors the most recent CI run.

---

## 9. Decision log (ADRs)

Significant architectural decisions are captured as ADRs in `docs/adr/`. This section is the index.

| # | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| 0001 | Use Postgres + `pgvector` over a dedicated vector DB | Accepted | — |
| 0002 | Defer Neo4j to Phase 3 | Accepted | — |
| 0003 | Default agent model: Claude Sonnet 4.6, escalate to Opus 4.7 | Accepted | — |
| 0004 | Embedding model pinned to OpenAI `text-embedding-3-small` (1536) | Accepted | — |

ADR templates and full text live under `docs/adr/`.

---

## 10. Open questions

Track unresolved questions here. Move to ADRs when decided.

- [ ] Final choice between Angular Material and PrimeNG for the component library
- [ ] Final choice between `arq` and `dramatiq` for background workers
- [ ] Initial set of supported languages for AST chunking (beyond Python + TypeScript)
- [ ] Hosting target for the public demo (Fly.io vs. Railway vs. VPS)
- [ ] Auth provider choice for the hosted demo (Auth0 vs. Clerk vs. self-hosted Keycloak)

---

## 11. Blockers and risks

Active blockers and risks that could affect the timeline.

| ID | Item | Impact | Owner | Status |
| :--- | :--- | :--- | :--- | :--- |
| — | — | — | — | — |

---

## 12. Recent updates

Append-only log. Newest first.

- **2026-05-08** — Phase 1 MVP implemented: ingestion pipeline (clone, walker, naive line-based chunker, batched embedding, content-hash dedup), arq background worker, Alembic migration (repositories/files/chunks + HNSW index), pgvector semantic search with cosine distance, system prompt v1, retrieve-then-generate SSE streaming endpoint, repos CRUD API, Angular chat surface wired to POST-based SSE, repo selector component, sources bar, error/loading states. Auth deferred (mock acceptable per spec). All quality gates pass: ruff, mypy strict, pytest, tsc, ng build.
- **2026-05-08** — Phase 0 implemented: backend skeleton (FastAPI, config, structlog, errors, LLM/embedding wrappers, health endpoints, Alembic), frontend skeleton (Angular 18+ standalone, Tailwind, SSE service, layout shell, chat stub), infrastructure (docker-compose, .env.example, pre-commit, CI pipeline, README). All quality gates wired except commitlint.
- **2026-05-08** — Context folder bootstrapped: project overview, architecture, code standards, AI workflow rules, UI context, progress tracker.
- **2026-05-08** — PRD v1.1.0 finalized (consolidated AI architecture and security sections).

---

## 13. How to update this document

- After completing a checklist item, mark it `[x]` and append a one-liner to **Recent updates**.
- When a phase's exit criteria are met, flip its status to 🟢 in the snapshot table.
- When a question is decided, remove it from **Open questions**, add an ADR under `docs/adr/`, and reference it in the **Decision log**.
- Eval table is regenerated by the CI eval gate; do not hand-edit Latest / Δ columns.
- Keep this file under version control. Do not branch private copies.
