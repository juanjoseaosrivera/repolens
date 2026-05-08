# RepoLens — Production Runbook

## Services

| Service | Port | Health check | Restart command |
|---------|------|-------------|-----------------|
| API (FastAPI) | 8000 | `GET /health` | `docker compose restart api` |
| Frontend (nginx) | 80 | `GET /` | `docker compose restart frontend` |
| PostgreSQL | 5432 | `pg_isready -U repolens` | `docker compose restart postgres` |
| Redis | 6379 | `redis-cli ping` | `docker compose restart redis` |
| Neo4j | 7474/7687 | `cypher-shell 'RETURN 1'` | `docker compose restart neo4j` |
| arq Worker | — | Check logs | `docker compose restart worker` |

## Starting the stack

```bash
# Pull latest images
docker compose pull

# Start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Verify health
curl http://localhost:8000/health
curl http://localhost:80/
```

## Deploying an update

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose build

# Apply migrations (if any)
docker compose exec api alembic upgrade head

# Rolling restart
docker compose up -d --no-deps api
docker compose up -d --no-deps frontend
docker compose up -d --no-deps worker
```

## Common issues

### API returns 500

1. Check logs: `docker compose logs api --tail=50`
2. Verify Postgres is healthy: `docker compose exec postgres pg_isready -U repolens`
3. Verify Redis is healthy: `docker compose exec redis redis-cli ping`
4. Check if migrations are up to date: `docker compose exec api alembic current`

### Ingestion stuck in "pending"

1. Check arq worker is running: `docker compose logs worker --tail=20`
2. Verify Redis connectivity: `docker compose exec redis redis-cli ping`
3. Re-enqueue: POST to `/repos` with the same URL (triggers re-ingestion if status is "failed")

### Neo4j connection errors

1. Neo4j is optional — agent queries degrade gracefully without it
2. Check Neo4j health: `docker compose exec neo4j cypher-shell -u neo4j -p repolens 'RETURN 1'`
3. Restart: `docker compose restart neo4j`

### High latency

1. Check if reranker is enabled (`REPOLENS_RERANKER_ENABLED=true`) — cross-encoder is CPU-intensive
2. Check embedding cache hit rate in structlog output (look for `cache.embedding_hit`)
3. Check LLM cache hit rate (look for `llm.cache_hit`)
4. Review agent step count in metrics SSE event

## Monitoring

### Structured logs

All logs are JSON (in production mode). Key log events:

| Event | Meaning |
|-------|---------|
| `pipeline.complete` | Ingestion finished |
| `pipeline.failed` | Ingestion failed |
| `retrieval.hybrid` | Search completed |
| `llm.completion` | LLM API call |
| `llm.cache_hit` | LLM response served from Redis |
| `embedding.complete` | Embedding API call |
| `embedding.all_cached` | All embeddings served from Redis |
| `rate_limit.exceeded` | Rate limit hit |
| `agent.max_steps_reached` | Agent loop guard triggered |

### OpenTelemetry

Enable OTEL export with:
```env
REPOLENS_OTEL_ENABLED=true
REPOLENS_OTEL_EXPORTER_ENDPOINT=http://otel-collector:4317
```

### LangSmith

Enable LangSmith tracing with:
```env
REPOLENS_LANGSMITH_API_KEY=lsv2_...
REPOLENS_LANGSMITH_PROJECT=repolens-prod
```

All LangGraph agent runs are automatically traced.

## Scaling

- **API**: Run multiple instances behind a load balancer. Stateless.
- **Worker**: Scale arq workers independently (`docker compose scale worker=3`).
- **PostgreSQL**: Use connection pooling (PgBouncer) for >50 concurrent connections.
- **Redis**: Single instance sufficient for typical workloads. Use Redis Cluster for >10K req/s.
- **Neo4j**: Single instance. Scale reads with read replicas if needed.
