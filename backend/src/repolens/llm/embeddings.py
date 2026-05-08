"""OpenAI embedding wrapper.

Business logic calls this module — never the OpenAI SDK directly.
Handles batching, telemetry, and structured logging.
"""

import openai
import structlog

from repolens.config import get_settings
from repolens.errors import RepoLensError

log = structlog.get_logger(__name__)


class EmbeddingError(RepoLensError):
    """Raised when an embedding call fails."""


class EmbeddingClient:
    """Thin async wrapper around the OpenAI Embeddings API."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = openai.AsyncOpenAI(api_key=self._api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Never call per-chunk in a loop — always batch.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors (each ``list[float]`` of length ``self._dimensions``).
        """
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                input=texts,
                model=self._model,
                dimensions=self._dimensions,
            )
        except openai.APIError as exc:
            log.error(
                "embedding.failed",
                model=self._model,
                batch_size=len(texts),
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise EmbeddingError(f"Embedding failed: {exc}") from exc

        vectors = [item.embedding for item in response.data]
        log.info(
            "embedding.complete",
            model=self._model,
            batch_size=len(texts),
            dimensions=self._dimensions,
            total_tokens=response.usage.total_tokens,
        )
        return vectors

    async def embed_single(self, text: str) -> list[float]:
        """Convenience: embed a single text and return its vector."""
        results = await self.embed([text])
        return results[0]
