.PHONY: sync up down logs psql migrate revision test lint typecheck check

COMPOSE := docker compose -f docker/docker-compose.yml

# iCloud Drive on macOS marks newly-written files (including the editable-install
# `repolens.pth`) as UF_HIDDEN, which causes Python's site.addpackage to silently
# skip them — making `import repolens` fail. Clear the flag after every sync.
sync:
	uv sync
	@if command -v chflags >/dev/null 2>&1; then \
		find .venv -name 'repolens*.pth' -exec chflags nohidden {} +; \
	fi

up:
	$(COMPOSE) up -d
	@echo "Waiting for Postgres to be healthy..."
	@until $(COMPOSE) exec -T postgres pg_isready -U repolens -d repolens >/dev/null 2>&1; do sleep 1; done
	@echo "Postgres is ready."

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

psql:
	$(COMPOSE) exec postgres psql -U repolens -d repolens

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy src

check: lint typecheck test
