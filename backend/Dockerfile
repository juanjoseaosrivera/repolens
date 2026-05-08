# Multi-stage Dockerfile for the RepoLens backend
# Build: docker build -t repolens-api backend/
# Run:   docker run -p 8000:8000 --env-file .env repolens-api

# Stage 1: Install dependencies
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
COPY src/ src/

RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Stage 2: Production image
FROM python:3.12-slim AS runtime

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/sh --create-home app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

# Install git (needed for repo cloning)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV REPOLENS_HOST="0.0.0.0"
ENV REPOLENS_PORT="8000"

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "repolens.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
