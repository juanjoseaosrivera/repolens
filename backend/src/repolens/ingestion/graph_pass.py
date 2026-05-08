"""Graph-build pass — populates Neo4j during ingestion."""

from pathlib import Path
from typing import Any

import structlog

from repolens.ingestion.walker import walk_repo

log = structlog.get_logger(__name__)


async def build_graph_from_repo(repo_id: str, clone_path: Path) -> None:
    """Walk the repo and build the Neo4j graph.

    This is a best-effort operation — if Neo4j is unavailable, the
    ingestion pipeline continues without the graph.
    """
    from repolens.graph.builder import build_graph, setup_graph_schema
    from repolens.graph.client import get_graph_client

    client = get_graph_client()
    await setup_graph_schema(client)

    files: list[dict[str, Any]] = []
    for rel_path, content, language in walk_repo(clone_path):
        files.append({"path": rel_path, "language": language, "content": content})

    await build_graph(client, repo_id, files)
    log.info("graph_pass.complete", repo_id=repo_id, files=len(files))
