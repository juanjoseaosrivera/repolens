# Product Requirements Document (PRD): RepoLens

**Project Name:** RepoLens
**Version:** 1.1.0
**Status:** Definition / In Development
**Author:** Juan Jose Aos Rivera
**Role:** AI Engineer

---

## 1. Product Vision

RepoLens is a "second-generation" code analysis system designed to reduce the cognitive load of developers when navigating massive repositories. Unlike generic chat assistants, RepoLens combines syntactic analysis (AST) with semantic retrieval (RAG) and agentic reasoning to provide a deep understanding of a software project's architecture, dependencies, and business logic.

## 2. The Problem

Developers lose up to 30% of their time trying to understand existing codebases. Common issues include:

*   **Slow Onboarding:** Difficulty understanding where the core logic resides.
*   **Hidden Dependencies:** Risk when making changes due to non-obvious side effects.
*   **Obsolete Documentation:** Written documentation rarely reflects the actual state of the code.

## 3. Strategic Objectives (Core Goals)

*   **Contextual Understanding:** Provide precise answers that consider not only the current file but also its imports and the global data flow.
*   **Efficient Navigation:** Reduce the time spent searching for specific features by 50%.
*   **Maintainability:** Offer a modular architecture that allows swapping models (LLMs) or vector databases with minimal effort.

## 4. Technical AI Architecture

### 4.1 Data Ingestion and Processing (Pipeline)

*   **Code Parser:** Uses `tree-sitter` to generate an Abstract Syntax Tree (AST). This allows identifying functions, classes, and methods before chunking.
*   **Chunking Strategy:** Semantic Function-Level Chunking. We don't cut by character count, but by logical code units.
*   **Enrichment:** Each chunk is tagged with metadata: `file_path`, `symbols_defined`, `imports`, `language`.

### 4.2 Hybrid Storage (Knowledge Base)

*   **Primary Store — PostgreSQL + `pgvector`:** Single relational database serving three roles:
    *   **Application data:** users, ingested repositories, sessions, evaluation runs.
    *   **Code chunk metadata:** `file_path`, `language`, `symbols_defined`, `start_line`, `end_line`, etc.
    *   **Vector embeddings:** chunk embeddings stored in a `vector(1536)` column with an HNSW index (cosine distance) for semantic search.
    *   *Rationale:* one database for transactional + vector workloads. Hybrid filtering (vector similarity + SQL `WHERE language = 'python' AND path LIKE 'src/%'`) is a single query — no cross-store fan-out. Battle-tested operational story (backups, migrations, observability) and fewer moving parts than running a separate vector DB.
*   **Lexical Search — PostgreSQL Full-Text Search (`tsvector`) + `pg_trgm`:** keyword/symbol search lives in the same Postgres instance, fused with vector results via Reciprocal Rank Fusion (RRF) at the application layer. (`rank_bm25` in-memory remains an option for early phases.)
*   **Graph Database — Neo4j:** Maps relationships between files (imports) and function calls to enable structural reasoning. Introduced in Phase 3, when the agentic layer needs "who calls X / what does Y import" queries that don't model well in SQL.

### 4.3 Orchestration and Retrieval (Agentic RAG)

*   **Hybrid Retrieval:** Combination of `pgvector` semantic search + SQL metadata filters + Postgres full-text/`pg_trgm` lexical search, fused with RRF.
*   **Reranking:** Use of a Cross-Encoder model (e.g., BGE-Reranker) to refine the top 5 results before sending them to the LLM.
*   **Multi-step Agent (LangGraph):** A cyclic flow where the agent can decide to:
    *   Search the vector index.
    *   Query the dependency graph.
    *   Read a full file if the answer requires macro context.

### 4.4 System Architecture (End-to-End)

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

## 5. Functional Requirements (User Stories)

| ID | User | Requirement | Priority |
| :--- | :--- | :--- | :--- |
| **US.1** | Developer | "I want to ask where authentication is managed and get the exact files." | High |
| **US.2** | Architect | "I want to generate a flow diagram of how data travels from the controller to the DB." | Medium |
| **US.3** | Lead Engineer | "If I change the signature of the `process_payment` function, what other modules will be affected?" | High |
| **US.4** | DevOps | "I want a summary of the environment variables the project needs to run." | Low |

## 6. Technology Stack

### Backend (Python)
*   **Language:** Python 3.12+
*   **Web framework:** FastAPI (async-first, OpenAPI auto-spec for the Angular client, Pydantic models).
*   **LLM:** Claude Sonnet 4.6 (`claude-sonnet-4-6`) — balanced speed/intelligence for agent steps. Opus 4.7 (`claude-opus-4-7`) reserved for the hardest reasoning tasks.
*   **Embeddings:** `text-embedding-3-small` (OpenAI), 1536 dims.
*   **Orchestrator:** LangGraph for the agent state machine; LangChain only where it adds value (otherwise direct Anthropic SDK).
*   **DB access:** SQLAlchemy 2.x (async) + `psycopg` v3, with Alembic for migrations. `pgvector` Python bindings for the embedding column type.
*   **Graph access (Phase 3+):** official `neo4j` driver.
*   **Background work:** `arq` or `dramatiq` (Redis-backed) for ingestion jobs.

### Frontend (Angular)
*   **Framework:** Angular 18+ (standalone components, Signals, the new control-flow syntax).
*   **HTTP / streaming:** `HttpClient` for REST, `EventSource`/SSE for streaming agent tokens and tool-call updates.
*   **State:** Angular Signals + `@ngrx/signals` if state grows; otherwise pure Signals.
*   **UI kit:** Angular Material or PrimeNG for the chat shell; Tailwind CSS for layout.
*   **Build:** `@angular/cli` with esbuild; SSR optional for the marketing/landing surface.

### Data
*   **Primary DB:** PostgreSQL 16 + `pgvector` (HNSW index, cosine distance) + `pg_trgm`.
*   **Graph DB (Phase 3+):** Neo4j 5.
*   **Cache / queue broker:** Redis (sessions, rate limiting, background-job queue).

### Platform
*   **Observability:** LangSmith (agent traces), `structlog` (app logs), OpenTelemetry-ready.
*   **Eval:** RAGAS for RAG metrics; pytest for unit/integration.
*   **Deployment:** Multi-stage Dockerfile per service; `docker-compose.yml` for local dev (Postgres, Redis, optional Neo4j); Fly.io / Railway / VPS for hosted demo.

## 7. Evaluation and Success Metrics (AI Quality)

As an AI engineering project, RepoLens is evaluated under the **RAGAS** framework:

*   **Faithfulness:** Does the bot's response actually come from the source code?
*   **Answer Relevance:** How useful is the answer to the developer's question?
*   **Context Precision:** Are the retrieved snippets actually the ones needed to answer?

## 8. Development Roadmap

*   **Phase 0 (Foundations):** Project skeleton, LLM + embeddings wrappers, tooling.
*   **Phase 1 (MVP):** Naive ingestion pipeline → Postgres + `pgvector`; FastAPI endpoints; minimal Angular chat shell wired to a streaming endpoint.
*   **Phase 2 (Advanced RAG):** AST chunking, hybrid retrieval (`pgvector` + Postgres FTS, RRF), cross-encoder reranking. Frontend gains the retrieved-chunks side panel.
*   **Phase 3 (Agent + Graph):** Add Neo4j; LangGraph agent with `search_code` / `query_graph` / `read_file` tools; streaming tool calls to the Angular UI.
*   **Phase 4 (Productionize):** Eval harness, observability, prompt-injection defenses, prompt caching, polished Angular UX, deployment.

## 9. Security Considerations

*   **Privacy:** The system is designed to run locally or in private cloud environments. Repository content never leaves the user's deployment.
*   **Sanitization:** Prevention of Prompt Injection — retrieved code is wrapped in delimiters and the system prompt declares its content as untrusted data.
*   **Auth:** OAuth2 / OIDC at the FastAPI layer; JWT to the Angular client. CORS locked to the frontend origin.
*   **Secrets:** `.env` for local; managed secret store (e.g. Doppler, AWS Secrets Manager, Fly secrets) in production. API keys never reach the browser.
*   **Rate limiting:** Per-user and per-IP throttles on the public endpoints, backed by Redis.
