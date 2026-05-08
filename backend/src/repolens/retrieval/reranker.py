"""Cross-encoder reranker wrapper.

Wraps a sentence-transformers CrossEncoder for scoring query-chunk pairs.
The reranker is behind a protocol so it can be swapped for a different
implementation (e.g., Cohere Rerank API, Voyage, etc.).
"""

from __future__ import annotations

from typing import Protocol

import structlog

from repolens.config import get_settings
from repolens.retrieval.vector import ChunkResult

log = structlog.get_logger(__name__)


class Reranker(Protocol):
    """Protocol for reranker implementations."""

    def rerank(
        self,
        query: str,
        results: list[ChunkResult],
        *,
        top_n: int | None = None,
    ) -> list[ChunkResult]: ...


class CrossEncoderReranker:
    """Reranker using a sentence-transformers CrossEncoder model.

    Requires the ``rerank`` optional dependency group:
    ``uv sync --extra rerank``
    """

    def __init__(self, *, model_name: str | None = None) -> None:
        settings = get_settings()
        self._model_name = model_name or settings.reranker_model
        self._top_n = settings.reranker_top_n
        self._model: object | None = None

    def _load_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self._model_name)
                log.info("reranker.loaded", model=self._model_name)
            except ImportError:
                log.error(
                    "reranker.import_error",
                    detail="sentence-transformers not installed. Run: uv sync --extra rerank",
                )
                raise
        return self._model

    def rerank(
        self,
        query: str,
        results: list[ChunkResult],
        *,
        top_n: int | None = None,
    ) -> list[ChunkResult]:
        """Score and rerank results using the cross-encoder."""
        if not results:
            return []

        top_n = top_n or self._top_n
        model = self._load_model()

        pairs = [[query, r.content] for r in results]
        scores = model.predict(pairs)  # type: ignore[attr-defined]

        scored = sorted(
            zip(results, scores, strict=True),
            key=lambda x: float(x[1]),
            reverse=True,
        )

        reranked = [
            ChunkResult(
                chunk_id=r.chunk_id,
                file_path=r.file_path,
                start_line=r.start_line,
                end_line=r.end_line,
                content=r.content,
                language=r.language,
                score=float(s),
            )
            for r, s in scored[:top_n]
        ]

        log.info(
            "reranker.done",
            model=self._model_name,
            input_count=len(results),
            output_count=len(reranked),
        )
        return reranked


class NoOpReranker:
    """Pass-through reranker that just truncates to top_n. Used when reranking is disabled."""

    def rerank(
        self,
        query: str,
        results: list[ChunkResult],
        *,
        top_n: int | None = None,
    ) -> list[ChunkResult]:
        settings = get_settings()
        top_n = top_n or settings.reranker_top_n
        return results[:top_n]


def get_reranker() -> Reranker:
    """Return the appropriate reranker based on settings."""
    settings = get_settings()
    if settings.reranker_enabled:
        return CrossEncoderReranker()
    return NoOpReranker()
