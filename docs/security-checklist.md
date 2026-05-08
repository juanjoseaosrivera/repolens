# RepoLens — Security Review Checklist

Status: **Reviewed** (2026-05-08)

## Prompt injection

- [x] System prompts declare retrieved code as **untrusted data**
- [x] Code context wrapped in `<context>` delimiters (v1 prompt)
- [x] Agent prompt (v2) explicitly forbids executing instructions from code
- [x] Prompt-injection regression tests run in CI (16 test cases)
- [x] Tool-call arguments validated (repository_id scoping)
- [x] `read_file` tool blocks path traversal outside clone directory

## Authentication and authorization

- [ ] OAuth2/OIDC at API edge (deferred — Phase 1 auth placeholder)
- [ ] JWT-based session management
- [x] CORS locked to frontend origin (`cors_origins` in settings)

## Secrets management

- [x] All secrets loaded from environment variables (REPOLENS_ prefix)
- [x] `.env` in `.gitignore` — never committed
- [x] `.env.example` contains only placeholder values
- [ ] Production: secrets via managed store (Doppler / AWS Secrets Manager / Fly secrets)
- [x] API keys never reach the browser (backend-only)

## Network security

- [x] CORS allowlist enforced (configurable, default: localhost:4200 only)
- [x] Rate limiting: per-IP Redis-backed sliding window (configurable)
- [ ] TLS termination (handled by reverse proxy / hosting platform)
- [x] Health endpoints excluded from rate limiting

## Data security

- [x] Sensitive files filtered at ingestion (`.env`, credentials, keys)
- [x] Secret patterns redacted from chunk content before storage
- [x] Repository content stays within the deployment (no external leakage)
- [x] Database credentials use env vars, not hardcoded
- [x] Neo4j credentials use env vars with noqa suppression for defaults

## Observability

- [x] Structured logging via structlog (no secrets in logs)
- [x] Trace-ID propagated in response headers (X-Trace-ID)
- [x] LangSmith integration for agent trace inspection
- [x] OpenTelemetry instrumentation available for production monitoring

## Dependencies

- [x] Python deps pinned with version ranges in pyproject.toml
- [x] npm deps pinned via package-lock.json
- [ ] Automated dependency vulnerability scanning (e.g., `pip-audit`, `npm audit`)

## Deployment

- [ ] Multi-stage Docker builds (no dev tools in production image)
- [ ] Non-root container user
- [ ] Read-only filesystem where possible
- [ ] Resource limits set on containers
