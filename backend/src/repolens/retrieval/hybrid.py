"""Hybrid retrieval with Reciprocal Rank Fusion (RRF).

Fuses semantic (pgvector), lexical (tsvector/pg_trgm), and optionally
metadata-filtered results into a single ranked list.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.config import get_settings
from repolens.llm import EmbeddingClient
from repolens.retrieval.lexical import fulltext_search
from repolens.retrieval.vector import ChunkResult, semantic_search

log = structlog.get_logger(__name__)


async def hybrid_search(
    query: str,
    repository_id: uuid.UUID,
    session: AsyncSession,
    *,
    top_k: int | None = None,
    embedder: EmbeddingClient | None = None,
) -> list[ChunkResult]:
    """Run semantic + lexical search and fuse with RRF.

    Returns up to *top_k* results sorted by fused score.
    """
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k

    # Run both retrieval channels
    vector_results = await semantic_search(
        query,
        repository_id,
        session,
        top_k=top_k,
        embedder=embedder,
    )

    lexical_results = await fulltext_search(
        query,
        repository_id,
        session,
        top_k=top_k,
    )

    # Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(
        [vector_results, lexical_results],
        weights=[settings.retrieval_vector_weight, settings.retrieval_lexical_weight],
        k=settings.rrf_k,
    )

    result = fused[:top_k]
    log.info(
        "retrieval.hybrid",
        repository_id=str(repository_id),
        vector_count=len(vector_results),
        lexical_count=len(lexical_results),
        fused_count=len(result),
    )
    return result


def reciprocal_rank_fusion(
    result_lists: list[list[ChunkResult]],
    *,
    weights: list[float] | None = None,
    k: int = 60,
) -> list[ChunkResult]:
    """Fuse multiple ranked result lists using RRF.

    RRF score for a document d across n rankings:
        score(d) = sum( w_i / (k + rank_i(d)) )

    where rank_i(d) is the 1-based rank of d in ranking i, and w_i is the
    weight for ranking i (default: all equal).
    """
    if weights is None:
        weights = [1.0] * len(result_lists)

    # Map chunk_id → best ChunkResult object (keep the one with highest original score)
    chunk_map: dict[uuid.UUID, ChunkResult] = {}
    rrf_scores: dict[uuid.UUID, float] = {}

    for result_list, weight in zip(result_lists, weights, strict=True):
        for rank, result in enumerate(result_list, start=1):
            cid = result.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + weight / (k + rank)

            if cid not in chunk_map or result.score > chunk_map[cid].score:
                chunk_map[cid] = result

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

    return [
        ChunkResult(
            chunk_id=chunk_map[cid].chunk_id,
            file_path=chunk_map[cid].file_path,
            start_line=chunk_map[cid].start_line,
            end_line=chunk_map[cid].end_line,
            content=chunk_map[cid].content,
            language=chunk_map[cid].language,
            score=rrf_scores[cid],
        )
        for cid in sorted_ids
    ]
