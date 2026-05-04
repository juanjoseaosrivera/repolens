"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_DATABASE_URL = "postgresql+psycopg://repolens:repolens@localhost:5432/repolens"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    embedding_dimensions: int = 1536


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
