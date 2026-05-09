"""arq background worker settings.

Start the worker with:  ``arq repolens.worker.WorkerSettings``
"""

import uuid
from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.typing import WorkerCoroutine

from repolens.config import get_settings
from repolens.ingestion.pipeline import run_ingestion
from repolens.storage.engine import build_engine


async def startup(ctx: dict[str, Any]) -> None:
    """Create DB engine + session factory once per worker lifetime."""
    _engine, session_factory = build_engine()
    ctx["session_factory"] = session_factory


async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up on worker shutdown."""


async def ingest_repo(ctx: dict[str, Any], repository_id: str) -> None:
    """arq task: run the full ingestion pipeline for a repository."""
    session_factory = ctx["session_factory"]
    await run_ingestion(uuid.UUID(repository_id), session_factory)


class WorkerSettings:
    """arq worker configuration."""

    functions: ClassVar[list[WorkerCoroutine]] = [ingest_repo]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
