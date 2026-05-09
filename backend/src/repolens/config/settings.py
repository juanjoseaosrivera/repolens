"""Centralized application settings via Pydantic BaseSettings.

All configuration flows through this module. No scattered os.environ.get calls.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env at the repo root (two levels up from this file: config/ → repolens/ → src/ → backend/ → repo root)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """RepoLens application settings.

    Values are loaded from environment variables (case-insensitive).
    Prefix: ``REPOLENS_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="REPOLENS_",
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "RepoLens"
    debug: bool = False
    log_level: str = "INFO"

    # --- Database (PostgreSQL + pgvector) ---
    database_url: str = Field(
        default="postgresql+psycopg://repolens:repolens@localhost:5432/repolens",
        description="Async-compatible PostgreSQL DSN",
    )

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM (Anthropic) ---
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"
    hard_reasoning_model: str = "claude-opus-4-7"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0

    # --- Embeddings (OpenAI) ---
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Ingestion ---
    clone_base_dir: str = "/tmp/repolens/repos"  # noqa: S108
    chunk_size: int = 60
    chunk_overlap: int = 20
    embedding_batch_size: int = 100

    # --- Neo4j (Phase 3+) ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "repolens"  # noqa: S105

    # --- Agent ---
    agent_max_steps: int = 5
    agent_max_tokens: int = 16000
    agent_model: str = "claude-sonnet-4-6"

    # --- Retrieval ---
    retrieval_top_k: int = 20
    retrieval_vector_weight: float = 1.0
    retrieval_lexical_weight: float = 1.0
    rrf_k: int = 60
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_n: int = 5
    reranker_enabled: bool = False

    # --- Observability ---
    otel_enabled: bool = False
    otel_service_name: str = "repolens-api"
    otel_exporter_endpoint: str = "http://localhost:4317"
    langsmith_api_key: str = ""
    langsmith_project: str = "repolens"

    # --- Cache ---
    cache_enabled: bool = True
    cache_embedding_ttl: int = 86400  # 24 hours
    cache_llm_ttl: int = 3600  # 1 hour

    # --- Rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 30
    rate_limit_burst: int = 10

    # --- Server ---
    host: str = "0.0.0.0"  # noqa: S104 — bind all interfaces intentionally for Docker
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:4200"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
