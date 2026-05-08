"""Neo4j async client wrapper."""

from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

from repolens.config import get_settings

log = structlog.get_logger(__name__)

_driver: AsyncDriver | None = None


class GraphClient:
    """Thin wrapper around the Neo4j async driver."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a Cypher query and return all records as dicts."""
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [dict(record) for record in await result.data()]

    async def write(self, query: str, **params: Any) -> None:
        """Execute a write Cypher query."""
        async with self._driver.session() as session:
            await session.run(query, params)

    async def close(self) -> None:
        await self._driver.close()


def get_graph_client() -> GraphClient:
    """Return a singleton GraphClient instance."""
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        log.info("graph.connected", uri=settings.neo4j_uri)
    return GraphClient(_driver)
