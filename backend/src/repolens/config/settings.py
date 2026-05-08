"""Centralized application settings via Pydantic BaseSettings.

All configuration flows through this module. No scattered os.environ.get calls.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RepoLens application settings.

    Values are loaded from environment variables (case-insensitive).
    Prefix: ``REPOLENS_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="REPOLENS_",
        env_file=".env",
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

    # --- Server ---
    host: str = "0.0.0.0"  # noqa: S104 — bind all interfaces intentionally for Docker
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:4200"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
