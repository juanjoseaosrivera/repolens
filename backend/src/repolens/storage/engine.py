"""SQLAlchemy async engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from repolens.config import get_settings


def build_engine() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    """Create the async engine and session factory from settings.

    Returns:
        A tuple of (engine, session_factory).
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
