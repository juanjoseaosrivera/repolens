"""OpenAI embedding wrapper with Redis caching.

Business logic calls this module — never the OpenAI SDK directly.
Handles batching, caching, telemetry, and structured logging.
"""

import openai
import structlog

from repolens.config import get_settings
from repolens.errors import RepoLensError

log = structlog.get_logger(__name__)


class EmbeddingError(RepoLensError):
    """Raised when an embedding call fails."""


class EmbeddingClient:
    """Thin async wrapper around the OpenAI Embeddings API with Redis caching."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = openai.AsyncOpenAI(api_key=self._api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with Redis cache pass-through.

        Cached embeddings are returned immediately; only cache misses are
        sent to the OpenAI API.
        """
        if not texts:
            return []

        settings = get_settings()
        results: list[list[float]] = [[] for _ in texts]
        texts_to_embed: list[tuple[int, str]] = []

        # Check cache
        if settings.cache_enabled:
            try:
                from repolens.cache import get_cache

                cache = get_cache()
                cached = await cache.get_embeddings_batch(texts)
                for i, (text, vec) in enumerate(zip(texts, cached, strict=True)):
                    if vec is not None:
                        results[i] = vec
                    else:
                        texts_to_embed.append((i, text))

                if not texts_to_embed:
                    log.info("embedding.all_cached", batch_size=len(texts))
                    return results
            except Exception:
                log.debug("embedding.cache_unavailable")
                texts_to_embed = list(enumerate(texts))
        else:
            texts_to_embed = list(enumerate(texts))

        # Call API for misses
        miss_texts = [t for _, t in texts_to_embed]
        try:
            response = await self._client.embeddings.create(
                input=miss_texts,
                model=self._model,
                dimensions=self._dimensions,
            )
        except openai.APIError as exc:
            log.error(
                "embedding.failed",
                model=self._model,
                batch_size=len(miss_texts),
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise EmbeddingError(f"Embedding failed: {exc}") from exc

        vectors = [item.embedding for item in response.data]

        # Fill results and update cache
        for (idx, _text), vector in zip(texts_to_embed, vectors, strict=True):
            results[idx] = vector

        if settings.cache_enabled:
            try:
                from repolens.cache import get_cache

                cache = get_cache()
                await cache.set_embeddings_batch(miss_texts, vectors)
            except Exception:
                log.debug("embedding.cache_write_failed")

        log.info(
            "embedding.complete",
            model=self._model,
            batch_size=len(texts),
            cached=len(texts) - len(miss_texts),
            api_calls=len(miss_texts),
            dimensions=self._dimensions,
            total_tokens=response.usage.total_tokens,
        )
        return results

    async def embed_single(self, text: str) -> list[float]:
        """Convenience: embed a single text and return its vector."""
        results = await self.embed([text])
        return results[0]
