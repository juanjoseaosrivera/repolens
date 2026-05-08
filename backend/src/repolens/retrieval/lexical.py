"""Lexical search using Postgres tsvector full-text search and pg_trgm.

Complements semantic vector search for symbol-name and keyword queries.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.retrieval.vector import ChunkResult

log = structlog.get_logger(__name__)


async def fulltext_search(
    query: str,
    repository_id: uuid.UUID,
    session: AsyncSession,
    *,
    top_k: int = 20,
) -> list[ChunkResult]:
    """Search chunks using Postgres full-text search (tsvector + ts_rank).

    Falls back to pg_trgm similarity if FTS returns no results.
    """
    # Full-text search with ts_rank scoring
    stmt = text("""
        SELECT c.id, c.content, c.start_line, c.end_line,
               f.path, f.language,
               ts_rank(c.search_vector, plainto_tsquery('english', :query)) AS score
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE f.repository_id = :repo_id
          AND c.search_vector @@ plainto_tsquery('english', :query)
        ORDER BY score DESC
        LIMIT :top_k
    """)

    rows = (
        await session.execute(
            stmt,
            {"query": query, "repo_id": str(repository_id), "top_k": top_k},
        )
    ).all()

    # If FTS returns nothing, try pg_trgm similarity
    if not rows:
        rows = (await _trgm_search(query, repository_id, session, top_k=top_k)).all()

    results = [
        ChunkResult(
            chunk_id=row.id,
            file_path=row.path,
            start_line=row.start_line,
            end_line=row.end_line,
            content=row.content,
            language=row.language,
            score=float(row.score),
        )
        for row in rows
    ]

    log.info(
        "retrieval.lexical",
        repository_id=str(repository_id),
        query_len=len(query),
        results=len(results),
    )
    return results


async def metadata_filter_search(
    query: str,
    repository_id: uuid.UUID,
    session: AsyncSession,
    *,
    language: str | None = None,
    path_prefix: str | None = None,
    top_k: int = 20,
) -> list[ChunkResult]:
    """Search chunks with SQL metadata filters (language, path prefix)."""
    conditions = ["f.repository_id = :repo_id"]
    params: dict[str, object] = {"repo_id": str(repository_id), "top_k": top_k}

    if language:
        conditions.append("f.language = :language")
        params["language"] = language

    if path_prefix:
        conditions.append("f.path LIKE :path_prefix")
        params["path_prefix"] = f"{path_prefix}%"

    where_clause = " AND ".join(conditions)
    stmt = text(f"""
        SELECT c.id, c.content, c.start_line, c.end_line,
               f.path, f.language,
               similarity(c.content, :query) AS score
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE {where_clause}
          AND similarity(c.content, :query) > 0.05
        ORDER BY score DESC
        LIMIT :top_k
    """)  # noqa: S608

    params["query"] = query
    rows = (await session.execute(stmt, params)).all()

    return [
        ChunkResult(
            chunk_id=row.id,
            file_path=row.path,
            start_line=row.start_line,
            end_line=row.end_line,
            content=row.content,
            language=row.language,
            score=float(row.score),
        )
        for row in rows
    ]


async def _trgm_search(
    query: str,
    repository_id: uuid.UUID,
    session: AsyncSession,
    *,
    top_k: int = 20,
) -> Any:
    """Fallback: pg_trgm similarity search when FTS returns nothing."""
    stmt = text("""
        SELECT c.id, c.content, c.start_line, c.end_line,
               f.path, f.language,
               similarity(c.content, :query) AS score
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE f.repository_id = :repo_id
          AND similarity(c.content, :query) > 0.05
        ORDER BY score DESC
        LIMIT :top_k
    """)

    return await session.execute(
        stmt,
        {"query": query, "repo_id": str(repository_id), "top_k": top_k},
    )
