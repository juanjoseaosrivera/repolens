"""Redis cache client for embedding and LLM response caching.

Embedding cache: keyed by content hash (SHA-256 of input text).
LLM cache: keyed by prompt hash (SHA-256 of system + messages).
"""

import hashlib
import json

import structlog
from redis.asyncio import Redis

from repolens.config import get_settings

log = structlog.get_logger(__name__)

_redis: Redis | None = None  

class RedisCache:
    """Async Redis cache with typed get/set for embeddings and LLM responses."""

    def __init__(self, client: Redis) -> None:          self._client = client

    # --- Embedding cache ---

    async def get_embedding(self, text: str) -> list[float] | None:
        """Look up a cached embedding by content hash."""
        key = f"emb:{_hash(text)}"
        raw = await self._client.get(key)
        if raw is None:
            return None
        log.debug("cache.embedding_hit", key=key[:20])
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set_embedding(self, text: str, vector: list[float]) -> None:
        """Cache an embedding vector."""
        settings = get_settings()
        key = f"emb:{_hash(text)}"
        await self._client.set(key, json.dumps(vector), ex=settings.cache_embedding_ttl)

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Look up a batch of embeddings. Returns None for misses."""
        if not texts:
            return []
        keys = [f"emb:{_hash(t)}" for t in texts]
        pipe = self._client.pipeline()
        for k in keys:
            pipe.get(k)
        results = await pipe.execute()
        return [json.loads(r) if r is not None else None for r in results]

    async def set_embeddings_batch(self, texts: list[str], vectors: list[list[float]]) -> None:
        """Cache a batch of embeddings."""
        settings = get_settings()
        pipe = self._client.pipeline()
        for text, vec in zip(texts, vectors, strict=True):
            key = f"emb:{_hash(text)}"
            pipe.set(key, json.dumps(vec), ex=settings.cache_embedding_ttl)
        await pipe.execute()

    # --- LLM response cache ---

    async def get_llm_response(self, system: str, messages: list[dict[str, str]]) -> str | None:
        """Look up a cached LLM response by prompt hash."""
        key = f"llm:{_prompt_hash(system, messages)}"
        raw = await self._client.get(key)
        if raw is None:
            return None
        log.debug("cache.llm_hit", key=key[:20])
        decoded: str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        return decoded

    async def set_llm_response(
        self, system: str, messages: list[dict[str, str]], response: str
    ) -> None:
        """Cache an LLM response."""
        settings = get_settings()
        key = f"llm:{_prompt_hash(system, messages)}"
        await self._client.set(key, response, ex=settings.cache_llm_ttl)

    # --- Rate limiting support ---

    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Sliding-window rate limiter. Returns True if within limit."""
        current = await self._client.incr(key)
        if current == 1:
            await self._client.expire(key, window)
        return int(current) <= limit


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _prompt_hash(system: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"system": system, "messages": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cache() -> RedisCache:
    """Return a singleton RedisCache instance."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=False)
        log.info("cache.connected", url=settings.redis_url)
    return RedisCache(_redis)
