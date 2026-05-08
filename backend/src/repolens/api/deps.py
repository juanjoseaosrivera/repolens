"""FastAPI dependency injection providers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repolens.llm import CompletionClient, EmbeddingClient
from repolens.storage.engine import build_engine

_engine, _session_factory = build_engine()


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a scoped async DB session, auto-closing on exit."""
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory (for use in background workers)."""
    return _session_factory


def get_completion_client() -> CompletionClient:
    """Return a CompletionClient instance."""
    return CompletionClient()


def get_embedding_client() -> EmbeddingClient:
    """Return an EmbeddingClient instance."""
    return EmbeddingClient()
