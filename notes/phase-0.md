# Phase 0 — Foundations & Project Skeleton

**Completed:** 2026-05-03
**Goal:** Stand up a reproducible workspace and prove the LLM + embeddings pipes work. No RAG, no agents — just plumbing.

---

## What I built

- **Project skeleton** with `uv` for dependency management, Python 3.12 pinned via `.python-version`, and a `src/`-layout package (`src/repolens/`).
- **Tooling:** `ruff` (lint + format), `mypy` in strict mode, `pytest`, all configured in `pyproject.toml` so a fresh clone + `uv sync` reproduces my environment exactly.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) running ruff + mypy + secret detection so I can't accidentally ship broken or leaky code.
- **Secrets hygiene:** `.env.example` checked in, real `.env` gitignored, both API keys (Anthropic + OpenAI) loaded via `python-dotenv` at runtime.
- **`src/repolens/llm.py`** — thin Anthropic wrapper (`LLM.complete(user_message, system=...)`) using Claude Sonnet 4.6, returning text + token counts in a typed `LLMResponse` dataclass. Network injectable for tests.
- **`src/repolens/embeddings.py`** — `Embedder.embed(texts)` against OpenAI `text-embedding-3-small` (1536 dims), with a module-level `embed()` convenience and the same injectable-client pattern.
- **`src/repolens/hello.py`** — Phase 0 deliverable: embeds `"hello world"`, prints the first 5 dimensions, asks Claude to comment on them. Wired as the `repolens-hello` console script.
- **9 unit tests** with all network calls mocked via injected fake clients. `uv run pytest` is green.
- **Jupyter** added as a dev dependency with the project venv registered as a kernel, so notebook code can `import repolens` directly.

---

## What I learned that surprised me

### 1. Cosine similarity has no absolute meaning

I ran the embedding-similarity exercise on four strings (two prose phrases about auth, an unrelated pizza phrase, and a Python function signature). The results:

| Cosine | Pair |
|---|---|
| 0.617 | `"user authentication"` ↔ `"login system"` |
| 0.614 | `"user authentication"` ↔ `"def authenticate(user, password):"` |
| 0.351 | `"login system"` ↔ `"def authenticate(user, password):"` |
| 0.165 | `"login system"` ↔ `"how to make pizza"` |
| 0.131 | `"user authentication"` ↔ `"how to make pizza"` |
| 0.045 | `"how to make pizza"` ↔ `"def authenticate(user, password):"` |

I expected unrelated pairs to score near 0.0. They didn't — they sat around 0.13–0.17. **OpenAI's embeddings live in a small slice of the 1536-dim space, so even random English-language strings have a baseline similarity floor.** The lesson: never threshold on cosine directly (`if score > 0.5: return chunk` is a trap). Always rank `top_k` and let downstream stages decide.

### 2. Embeddings can bridge prose and code — but only when tokens align

`"user authentication"` ↔ `"def authenticate(...)"` scored **0.614** — basically tied with the prose-prose comparison. That's why vector RAG on code works at all: the embedding model has learned that `authenticate` in code and `authentication` in English point at the same idea.

But — and this is the load-bearing observation — `"login system"` ↔ `"def authenticate(...)"` scored only **0.351**, even though "login system" and "user authentication" are practically synonyms in English. The difference is the literal token `authenticate` appearing in both the prose and the code in the high-scoring pair. **Surface-form word overlap matters as much as semantics.**

### 3. This is exactly why naive vector search fails on code

If a user asks *"where is the login system?"* and the codebase calls the function `authenticate()`, vector search alone may rank that function lower than less-relevant code that happens to share words with the query. I've now measured that failure mode in 4 lines of code, before building the system that exhibits it.

This is the concrete justification for what Phase 2 adds:
- **BM25 / lexical search** — to catch exact symbol-name matches the user types verbatim (`process_payment`, `UserService`).
- **Query rewriting / HyDE** — to turn `"where is the login system?"` into a hypothetical document like `"def login(...)"` before embedding, closing the surface-form gap.
- **Reranking** — to recover from the cases where neither retrieval channel ranks the right chunk first.

---

## Cost of the hello script

A single `repolens-hello` run does one embedding call on `"hello world"` (~2 input tokens for the embedding) plus one Claude Sonnet 4.6 call with a short prompt. Order of magnitude: a few hundred input tokens + a few hundred output tokens, so well under $0.01 per run. The lesson isn't the dollar amount — it's the habit of *knowing* the cost rather than guessing.

---

## What I'd do differently

- **Trust uv's defaults less.** `uv init` initially created the venv against Python 3.14 (the system default) instead of the 3.12 I asked for. I had to `uv python pin 3.12 && rm -rf .venv && uv sync` to fix it. Next time I'll verify `.venv/bin/python --version` immediately after init.
- **Lock down `.env` checks earlier.** I almost committed an `.env` once before remembering it was ignored. The `detect-private-key` pre-commit hook catches some of this; running `git status` before every commit catches the rest.
- **Mock at the client boundary, not the SDK internals.** I used `MagicMock` and injected fake clients via constructor arguments. This kept tests fast and decoupled from the SDK's response shapes — when the Anthropic SDK changes, only the wrapper breaks, not the tests.

---

## Self-check answers

> **"Can you explain why two semantically similar strings produce vectors with high cosine similarity, in your own words?"**

The embedding model maps text into a high-dimensional space where directions encode meaning. Two phrases describing the same concept end up pointing in roughly the same direction, so their cosine (which measures angle) is high. But the embedding is also influenced by surface-form features — shared tokens, syntax, casing — so two phrases about the same concept that share *no* words score lower than two that share keywords, even when humans would judge them equally similar. This is why vector search is necessary but not sufficient for code retrieval, and why production RAG systems combine it with lexical search and reranking.

> **"Do you know the per-call cost of your hello script to within ±20%?"**

Yes — well under $0.01 per run. One `text-embedding-3-small` embedding (~2 input tokens) plus one Claude Sonnet 4.6 call with a short prompt and short response.

---

## Ready for Phase 1

The plumbing works, the tests pass, the cost model is internalized, and I've measured the failure mode that justifies Phase 2's complexity. Next: Postgres + `pgvector` running in Docker, naive ingestion pipeline, and the first real "where is X?" question against a real repo.
