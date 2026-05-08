# RepoLens — Backup & Restore

## What to back up

| Component | Data | Method | Frequency |
|-----------|------|--------|-----------|
| PostgreSQL | All tables (repos, files, chunks, eval_runs) | `pg_dump` | Daily |
| Neo4j | Dependency graph | `neo4j-admin dump` | After each ingestion |
| Redis | Cache only — ephemeral, no backup needed | — | — |
| Cloned repos | `/tmp/repolens/repos` (or `REPOLENS_CLONE_BASE_DIR`) | Re-clone from source | On demand |

## PostgreSQL backup

### Full backup

```bash
# From the Docker host
docker compose exec postgres pg_dump -U repolens -Fc repolens > backup_$(date +%Y%m%d).dump

# Or from a remote machine
pg_dump -h <host> -U repolens -Fc repolens > backup_$(date +%Y%m%d).dump
```

### Restore

```bash
# Drop and recreate the database
docker compose exec postgres psql -U repolens -c "DROP DATABASE IF EXISTS repolens_restore;"
docker compose exec postgres psql -U repolens -c "CREATE DATABASE repolens_restore;"

# Restore from dump
docker compose exec -T postgres pg_restore -U repolens -d repolens_restore < backup_20260508.dump

# Or restore in-place (destructive)
docker compose exec -T postgres pg_restore -U repolens -d repolens --clean --if-exists < backup_20260508.dump
```

### Automated daily backup (cron)

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /opt/repolens && docker compose exec -T postgres pg_dump -U repolens -Fc repolens > /backups/repolens_$(date +\%Y\%m\%d).dump && find /backups -name "repolens_*.dump" -mtime +7 -delete
```

## Neo4j backup

### Full backup

```bash
# Stop Neo4j first (online backup requires Enterprise edition)
docker compose stop neo4j

# Dump the database
docker compose run --rm neo4j neo4j-admin database dump neo4j --to-path=/backups

# Restart
docker compose start neo4j
```

### Restore

```bash
docker compose stop neo4j
docker compose run --rm neo4j neo4j-admin database load neo4j --from-path=/backups --overwrite-destination
docker compose start neo4j
```

### Alternative: re-build from Postgres

The Neo4j graph can be fully rebuilt from the ingested code in Postgres:

```bash
# Re-trigger ingestion for all repos (this rebuilds the graph)
curl http://localhost:8000/repos | jq -r '.[].url' | while read url; do
  curl -X POST http://localhost:8000/repos -H 'Content-Type: application/json' -d "{\"url\": \"$url\"}"
done
```

## Disaster recovery

### Full restore procedure

1. Start infrastructure: `docker compose up -d postgres redis neo4j`
2. Wait for health checks to pass
3. Restore Postgres: `pg_restore -U repolens -d repolens < latest.dump`
4. Run migrations: `docker compose exec api alembic upgrade head`
5. Start API and worker: `docker compose up -d api worker`
6. Rebuild Neo4j graph (optional — re-ingest repos)
7. Start frontend: `docker compose up -d frontend`
8. Verify: `curl http://localhost:8000/health`

### Data loss scenarios

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Postgres lost | All data lost | Restore from pg_dump backup |
| Neo4j lost | Graph queries fail, agent degrades | Re-ingest repos to rebuild |
| Redis lost | Cache cold, rate limits reset | Automatic — cache rebuilds on use |
| Clone directory lost | Re-ingestion required | Re-trigger ingestion per repo |

## Testing backups

Verify backups monthly:

```bash
# 1. Restore to a test database
docker compose exec postgres psql -U repolens -c "CREATE DATABASE repolens_test;"
docker compose exec -T postgres pg_restore -U repolens -d repolens_test < latest.dump

# 2. Check row counts
docker compose exec postgres psql -U repolens -d repolens_test -c "SELECT 'repos', count(*) FROM repositories UNION ALL SELECT 'files', count(*) FROM files UNION ALL SELECT 'chunks', count(*) FROM chunks;"

# 3. Clean up
docker compose exec postgres psql -U repolens -c "DROP DATABASE repolens_test;"
```
