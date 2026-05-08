"""Semantic vector search over pgvector chunk embeddings."""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.llm import EmbeddingClient
from repolens.storage.models import Chunk, File

log = structlog.get_logger(__name__)

DEFAULT_TOP_K = 8


@dataclass(frozen=True, slots=True)
class ChunkResult:
    """A retrieved chunk with its similarity score and file metadata."""

    chunk_id: uuid.UUID
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str | None
    score: float


async def semantic_search(
    query: str,
    repository_id: uuid.UUID,
    session: AsyncSession,
    *,
    top_k: int = DEFAULT_TOP_K,
    embedder: EmbeddingClient | None = None,
) -> list[ChunkResult]:
    """Embed *query* and return the closest *top_k* chunks from the repository.

    Uses pgvector cosine distance (``<=>``) with the HNSW index.
    """
    embedder = embedder or EmbeddingClient()
    query_vector = await embedder.embed_single(query)

    # pgvector cosine distance: <=> returns distance (0 = identical, 2 = opposite)
    # We convert to a similarity score: 1 - distance
    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.start_line,
            Chunk.end_line,
            File.path,
            File.language,
            (1 - Chunk.embedding.cosine_distance(query_vector)).label("score"),
        )
        .join(File, Chunk.file_id == File.id)
        .where(File.repository_id == repository_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(text("score DESC"))
        .limit(top_k)
    )

    rows = (await session.execute(stmt)).all()

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
        "retrieval.search",
        repository_id=str(repository_id),
        query_len=len(query),
        results=len(results),
        top_score=results[0].score if results else None,
    )
    return results
