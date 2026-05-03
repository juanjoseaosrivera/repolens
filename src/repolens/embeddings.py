"""Wrapper around OpenAI's embeddings API for batch text embedding."""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536


class Embedder:
    """Embeds a list of strings into fixed-dimensional vectors."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            key = api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
                )
            self._client = OpenAI(api_key=key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def embed(texts: list[str]) -> list[list[float]]:
    """Module-level convenience: build a default Embedder and embed `texts`."""
    return Embedder().embed(texts)
