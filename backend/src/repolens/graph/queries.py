"""Cypher query service — wraps common graph queries behind a clean interface."""

import uuid
from dataclasses import dataclass
from typing import Any

import structlog

from repolens.graph.client import GraphClient

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node result from a graph query."""

    label: str
    name: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None


class GraphQueryService:
    """High-level Cypher query interface for the agent's query_graph tool."""

    def __init__(self, client: GraphClient) -> None:
        self._client = client

    async def who_calls(self, function_name: str, repo_id: uuid.UUID) -> list[GraphNode]:
        """Find all functions that call *function_name*."""
        rows = await self._client.run(
            "MATCH (caller:Function)-[:CALLS]->(callee:Function {name: $name, repo_id: $repo_id}) "
            "RETURN caller.name AS name, caller.file_path AS file_path, "
            "caller.start_line AS start_line, caller.end_line AS end_line",
            name=function_name,
            repo_id=str(repo_id),
        )
        return [
            GraphNode(
                label="Function",
                name=r["name"],
                file_path=r["file_path"],
                start_line=r.get("start_line"),
                end_line=r.get("end_line"),
            )
            for r in rows
        ]

    async def what_imports(self, file_path: str, repo_id: uuid.UUID) -> list[GraphNode]:
        """Find all files that import *file_path*."""
        rows = await self._client.run(
            "MATCH (importer:File)-[:IMPORTS]->(target:File {path: $path, repo_id: $repo_id}) "
            "RETURN importer.path AS path, importer.language AS language",
            path=file_path,
            repo_id=str(repo_id),
        )
        return [GraphNode(label="File", name=r["path"], file_path=r["path"]) for r in rows]

    async def what_does_file_define(self, file_path: str, repo_id: uuid.UUID) -> list[GraphNode]:
        """Find all functions and classes defined in *file_path*."""
        rows = await self._client.run(
            "MATCH (f:File {path: $path, repo_id: $repo_id})-[:DEFINES]->(d) "
            "RETURN labels(d)[0] AS label, d.name AS name, d.file_path AS file_path, "
            "d.start_line AS start_line, d.end_line AS end_line",
            path=file_path,
            repo_id=str(repo_id),
        )
        return [
            GraphNode(
                label=r["label"],
                name=r["name"],
                file_path=r["file_path"] or file_path,
                start_line=r.get("start_line"),
                end_line=r.get("end_line"),
            )
            for r in rows
        ]

    async def impact_analysis(
        self, function_name: str, repo_id: uuid.UUID, *, max_depth: int = 3
    ) -> list[GraphNode]:
        """Find all transitive callers of *function_name* up to *max_depth* hops."""
        rows = await self._client.run(
            "MATCH (callee:Function {name: $name, repo_id: $repo_id}) "
            f"MATCH (caller:Function)-[:CALLS*1..{max_depth}]->(callee) "
            "WHERE caller.repo_id = $repo_id "
            "RETURN DISTINCT caller.name AS name, caller.file_path AS file_path, "
            "caller.start_line AS start_line, caller.end_line AS end_line",
            name=function_name,
            repo_id=str(repo_id),
        )
        log.info(
            "graph.impact_analysis",
            function=function_name,
            repo_id=str(repo_id),
            callers=len(rows),
        )
        return [
            GraphNode(
                label="Function",
                name=r["name"],
                file_path=r["file_path"],
                start_line=r.get("start_line"),
                end_line=r.get("end_line"),
            )
            for r in rows
        ]

    async def raw_cypher(
        self, query: str, repo_id: uuid.UUID, **params: Any
    ) -> list[dict[str, Any]]:
        """Execute a raw Cypher query (for advanced agent use)."""
        params["repo_id"] = str(repo_id)
        log.info("graph.raw_cypher", query=query[:200])
        return await self._client.run(query, **params)
