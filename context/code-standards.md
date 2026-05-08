# RepoLens — Code Standards

This document defines the coding standards for RepoLens. It is the rulebook that complements `project-overview.md` and `architecture-context.md`. Standards exist so the codebase reads like one mind wrote it — the goal is consistency, readability, and long-term maintainability, not personal preference.

When in doubt, prefer **clarity over cleverness**, **explicit over implicit**, and **boring over novel**.

## 1. General principles

- **Optimize for the next reader.** Code is written once and read hundreds of times. Make the next person's job easier.
- **Keep functions small and named for what they do.** If a function needs a comment to explain what it does, it probably needs a better name or to be split.
- **Fail loudly.** Errors should bubble up with context, not be silently swallowed. Use typed exceptions, not bare `except:` or empty `catch` blocks.
- **No dead code.** Delete commented-out code. Git remembers. If you need it back, find it in history.
- **No magic numbers or strings.** Pull them into named constants or configuration.
- **Composition over inheritance.** Prefer small, focused classes/functions wired together over deep hierarchies.
- **Pure functions where possible.** Side effects should live at the edges (I/O, DB, API) — the core logic should be deterministic and testable.

## 2. Python (backend)

### 2.1 Language and tooling

- **Python 3.12+.** Use modern features: `match` statements, `from __future__ import annotations` if needed, PEP 695 generic syntax where it improves clarity.
- **Type hints are mandatory** on every public function, method, and module-level variable. Use `typing` (or `collections.abc` for ABCs) — no untyped public surface.
- **Formatter:** `ruff format` (Black-compatible). Line length 100.
- **Linter:** `ruff check`. The full ruleset is in `pyproject.toml`. CI fails on lint errors; do not commit code with lint warnings.
- **Type checker:** `mypy` in strict mode (`--strict`). New code must pass strict mypy. Existing code is migrated incrementally.
- **Imports:** sorted by `ruff` (isort-compatible). Three groups: standard library, third party, first party — separated by a blank line. Absolute imports only.

### 2.2 Project layout

```
backend/
  src/repolens/
    api/          # FastAPI routers, request/response models
    agent/        # LangGraph state machine, tools, prompts
    ingestion/    # parsers, chunkers, embedding pipeline, workers
    retrieval/    # hybrid search, reranking, RRF fusion
    storage/      # SQLAlchemy models, repositories, migrations entry points
    llm/          # Anthropic / OpenAI wrappers, embedding clients
    graph/        # Neo4j client and Cypher queries (Phase 3+)
    config/       # settings, feature flags, env loading
    observability/# logging, tracing, metrics
  tests/
    unit/
    integration/
    eval/         # RAGAS evaluation runs
  alembic/        # migrations
  pyproject.toml
```

One concept per module. If a module exceeds ~400 lines, split it.

### 2.3 Naming conventions

- `snake_case` for functions, methods, variables, modules.
- `PascalCase` for classes and Pydantic/SQLAlchemy models.
- `UPPER_SNAKE_CASE` for module-level constants.
- `_leading_underscore` for module-private symbols. No double-underscore name mangling unless you have a specific reason.
- Names are descriptive: `chunk_by_function` not `cbf`. Boolean variables read as predicates: `is_indexed`, `has_embedding`, `should_rerank`.

### 2.4 Pydantic and data shapes

- All API request/response shapes are Pydantic v2 models. No raw dicts crossing the API boundary.
- Pydantic models for **wire format** (API I/O). SQLAlchemy models for **storage**. Domain logic uses dataclasses or plain classes — never the ORM model directly inside business logic.
- Use `model_config` for strict validation: `extra='forbid'` on inputs, `frozen=True` on value objects.
- Field validators only when validation cannot be expressed by the type. Prefer `Annotated[...]` with `Field(...)`.

### 2.5 Async and concurrency

- The backend is async-first. Use `async def` for any function that does I/O.
- Never call blocking code from an async context. If you must call a blocking library, wrap it in `asyncio.to_thread`.
- Use `psycopg` v3 in async mode. Use SQLAlchemy 2.x async sessions.
- `asyncio.gather` for fan-out. `asyncio.TaskGroup` (Python 3.11+) when failures should propagate cleanly.
- No mixing of `asyncio` and `threading` without an explicit reason documented in code.

### 2.6 Errors and exceptions

- Define a domain exception hierarchy in `repolens.errors`: `RepoLensError` as the base, then `IngestionError`, `RetrievalError`, `AgentError`, etc.
- Catch only what you can handle. Re-raise with context using `raise ... from err`.
- Never use bare `except:`. `except Exception:` only at process boundaries (request handlers, worker entrypoints) where the exception is logged and converted to a structured error response.
- Validation errors return HTTP 422 (FastAPI does this automatically). Domain errors map to specific HTTP codes via exception handlers.

### 2.7 Logging

- Use `structlog` only — no `print`, no `logging` module directly.
- Logs are structured key-value pairs, not free-form strings. `log.info("ingestion.chunk_indexed", repo_id=..., file_path=..., chunk_count=...)`.
- Log levels: `debug` for internal trace, `info` for normal events, `warning` for degraded behavior, `error` for failures requiring attention. No `critical` unless the process is about to die.
- Never log secrets, API keys, JWTs, or full prompt/response bodies. Log identifiers and shapes; sample full content behind a debug flag.

### 2.8 Configuration

- All configuration via Pydantic `BaseSettings` in `repolens.config`. No scattered `os.environ.get` calls.
- Secrets come from environment variables; defaults are for local development only and never include real credentials.
- Feature flags live in config too. They are typed booleans, not stringly-typed.

### 2.9 Database and migrations

- All schema changes go through Alembic migrations. No manual `ALTER TABLE` in the running database.
- Migrations are reversible where possible. Irreversible migrations are flagged in their docstring.
- Indexes are created `CONCURRENTLY` in production migrations — never block writes during a deploy.
- Vector columns use `pgvector.sqlalchemy.Vector(1536)`. Embedding dimensions are pinned to a constant in `repolens.config`.
- Repository pattern: SQLAlchemy queries live in `storage/repositories/`. Business logic never writes raw SQL or queries models directly.

### 2.10 LLM and embedding calls

- All LLM and embedding calls go through wrappers in `repolens.llm`. Business logic never imports the Anthropic or OpenAI SDK directly.
- Wrappers expose: `complete`, `stream`, `embed`. They handle retries, timeouts, telemetry, and structured logging.
- Prompts live in dedicated files (`prompts/*.md` or `prompts/*.py`), not inline string literals scattered through the code.
- Retrieved code is wrapped in delimiters and the system prompt declares it as untrusted. This is a hard rule, not a guideline.
- Token counts and model identifiers are logged on every call.

### 2.11 Testing (Python)

- `pytest` only. No `unittest`-style test classes.
- Three tiers: `tests/unit/` (no I/O, milliseconds per test), `tests/integration/` (Postgres, Redis — `docker-compose.test.yml`), `tests/eval/` (RAGAS runs, may hit external APIs).
- Fixtures in `conftest.py` at the appropriate scope. Prefer factory fixtures over module-level singletons.
- Use `pytest.mark.asyncio` for async tests. Use `pytest-anyio` if multi-loop testing is needed.
- Coverage target: 80% line coverage for `unit/` and `integration/` combined. Coverage of evaluation harness is not measured.
- Mock the boundary, not the internals. Mock the LLM wrapper, not LangGraph internals. Mock the HTTP client, not your repository layer.

## 3. TypeScript / Angular (frontend)

### 3.1 Language and tooling

- **TypeScript strict mode.** `"strict": true` plus `"noUncheckedIndexedAccess": true` and `"exactOptionalPropertyTypes": true`.
- **Angular 18+.** Standalone components, Signals, the new control-flow syntax (`@if`, `@for`, `@switch`). No NgModules in new code. No `*ngIf` / `*ngFor` in new code.
- **Formatter:** Prettier. Line length 100.
- **Linter:** ESLint with `@angular-eslint` and `@typescript-eslint`. CI fails on lint errors.
- **Build:** `@angular/cli` with esbuild.

### 3.2 Project layout

```
frontend/
  src/
    app/
      core/         # singletons: api client, auth, config
      shared/       # reusable components, pipes, directives
      features/
        chat/       # chat UI feature
        repos/      # repo selector feature
        traces/     # agent trace side panel feature
      app.config.ts # standalone bootstrap config
      app.routes.ts # route definitions
    assets/
    styles/
  angular.json
  tsconfig.json
```

One feature per folder. Features do not import from other features directly — shared code goes through `shared/` or `core/`.

### 3.3 Naming conventions

- `kebab-case` for filenames: `chat-shell.component.ts`, `repo-selector.service.ts`.
- `PascalCase` for class names, interfaces, types.
- `camelCase` for variables, functions, signals.
- Components end in `.component.ts`, services in `.service.ts`, pipes in `.pipe.ts`, directives in `.directive.ts`.
- Signals are named for what they hold: `messages`, `isStreaming`, `selectedRepo()`. Computed signals describe the derived value: `unreadCount = computed(...)`.

### 3.4 Components

- Standalone components only. No NgModules.
- `OnPush` change detection by default — Signals integrate cleanly with it.
- Templates in separate `.html` files when they exceed ~30 lines; inline otherwise.
- Styles in separate `.scss` files; component-scoped (default view encapsulation).
- Inputs use `input()` / `input.required()` (signal inputs). Outputs use `output()`. No `@Input()` / `@Output()` decorators in new code.
- Components are dumb where possible: receive state via inputs, emit events via outputs. Logic lives in services.

### 3.5 State management

- **Default:** Angular Signals. `signal()`, `computed()`, `effect()`.
- **When state grows:** `@ngrx/signals` SignalStore. Move only when the cost of pure Signals is clearly higher than the cost of the abstraction.
- **No RxJS for state.** RxJS is reserved for streams that are genuinely streams: SSE events, debounced inputs, etc. State is signals.
- Effects (`effect()`) are for synchronization with the outside world (logging, persistence). Do not use effects to model derivations — that is what `computed` is for.

### 3.6 HTTP and streaming

- All HTTP through `HttpClient`, wrapped behind feature-specific services. No raw `fetch`.
- Backend types are generated from the FastAPI OpenAPI spec — frontend never hand-writes request/response interfaces.
- SSE for agent streaming uses `EventSource`. Errors and reconnects are handled centrally in a `StreamingService`.
- All HTTP calls return `Observable<T>` or `Promise<T>` — never both signatures from the same method.

### 3.7 Styling

- Tailwind CSS for layout and spacing. Component library (Angular Material or PrimeNG) for complex widgets — do not rebuild a date picker.
- Component styles for component-specific concerns. Global styles only for resets and design tokens.
- No inline `style="..."` attributes in templates.
- Color, spacing, and typography come from design tokens — no hex codes scattered through templates.

### 3.8 Testing (frontend)

- **Unit:** Jest (or Karma + Jasmine, depending on the chosen runner — pick one and stick with it). Test components with Testing Library style — query by role/text, not by CSS selector.
- **E2E:** Playwright. E2E tests cover the critical user paths only: ask a question, see streamed response, see retrieved chunks.
- Mock the HTTP layer, not the components.

## 4. Database conventions (PostgreSQL)

- **Names.** Tables are plural snake_case (`code_chunks`). Columns are snake_case singular. Foreign keys are `<table>_id` (`repository_id`).
- **Primary keys.** UUID v7 by default — sortable and globally unique. Internal-only auto-increment IDs are acceptable for high-write tables where UUID overhead matters.
- **Timestamps.** Every table has `created_at` and `updated_at` (both `timestamptz NOT NULL DEFAULT now()`). Soft deletes use `deleted_at` only when soft delete is required by domain logic — otherwise hard delete.
- **Indexes.** Named explicitly: `ix_<table>_<columns>`. Vector indexes named `<table>_<column>_hnsw_idx`.
- **Constraints.** Foreign keys with explicit `ON DELETE` behavior. Check constraints for enums when not using a real enum type.
- **Enums.** Prefer Postgres `enum` types over check constraints when the value set is stable.
- **Vector storage.** `vector(1536)` columns. HNSW index with cosine distance. Embedding model identifier is stored alongside the vector — embeddings from different models never coexist on the same column without an identifier.

## 5. Cypher / Neo4j (Phase 3+)

- Node labels in `PascalCase` singular: `:File`, `:Function`, `:Class`.
- Relationship types in `UPPER_SNAKE_CASE`: `:IMPORTS`, `:CALLS`, `:DEFINES`.
- All queries are parameterized — no string interpolation of user input.
- Queries live in dedicated `.cypher` files or constants, not scattered as inline strings.

## 6. Git and commit hygiene

- **Branches:** `feature/<short-name>`, `fix/<short-name>`, `chore/<short-name>`. No personal-name branches.
- **Commits:** Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`. Subject line ≤ 72 chars, imperative mood.
- **Body:** explain the *why*, not the *what*. The diff shows the what.
- **Atomic commits.** One logical change per commit. If a commit message contains "and", consider splitting.
- **No commits to `main`.** All changes via pull request.
- **PR size.** Aim for under 400 lines of diff. Larger PRs need a clear explanation of why they cannot be split.

## 7. Documentation

- **Docstrings.** Public Python functions and classes have docstrings in Google style. Private helpers may skip docstrings if their name and signature are self-explanatory.
- **TSDoc.** Public TypeScript functions/services use TSDoc comments.
- **READMEs.** Each top-level package (`backend/`, `frontend/`) has a README covering setup, run, test, and common workflows.
- **ADRs (Architecture Decision Records).** Significant architectural decisions are captured in `docs/adr/NNNN-<title>.md`. The decision to use Postgres + `pgvector` over a dedicated vector DB is an ADR. Adding Neo4j is an ADR.
- **No documentation in code that is not code.** Comments explain *why*, not *what*. If a comment paraphrases the code, delete it.

## 8. Security and privacy (operational rules)

- **Never log secrets.** API keys, JWTs, passwords, OAuth tokens — none of these enter logs, error messages, or telemetry.
- **Never echo user-supplied content into logs without sanitization.**
- **Retrieved code is untrusted.** Always wrap it in delimiters when sent to an LLM. Always declare it as untrusted in the system prompt.
- **Tool-call arguments are validated** before execution. The agent does not receive a free pass on input validation.
- **CORS is allowlist-based**, locked to the frontend origin per environment.
- **Rate limiting** is enforced at the API edge, backed by Redis. Bypassing it requires an explicit, audited exception.

## 9. Performance

- **Measure before optimizing.** No micro-optimizations without a profiler showing the hot path.
- **N+1 queries are bugs**, not nitpicks. Use eager loading (`selectinload`, `joinedload`) where it matters.
- **Embedding calls are batched.** Per-chunk embedding calls in a loop are forbidden; the wrapper batches.
- **LLM responses stream** wherever the user sees the output. Non-streaming is reserved for internal tool calls.
- **Caching.** Embeddings are cached by content hash. LLM responses are cached by prompt hash + model identifier. Cache layer is Redis.

## 10. Code review

- Every PR requires at least one approving review.
- Reviewers check: correctness, tests, naming, error handling, security, performance hotspots, adherence to these standards.
- Reviewers do not gatekeep on personal style — only on the standards documented here.
- Disagreements about standards are resolved by amending this document, not by relitigating the same argument in PRs.

## 11. Source

This document derives from the technology stack and security posture defined in `REPOLENS-PRD.md` v1.1.0. When the PRD changes, these standards are updated in the same PR.
