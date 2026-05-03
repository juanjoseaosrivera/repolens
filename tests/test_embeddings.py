"""Unit tests for the embeddings wrapper. Network calls are mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from repolens.embeddings import DEFAULT_DIMENSIONS, Embedder


def _fake_response(*vectors: list[float]):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


def test_embed_single_text():
    vec = [0.1] * DEFAULT_DIMENSIONS
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = _fake_response(vec)
    embedder = Embedder(client=fake_client)

    result = embedder.embed(["hello"])

    assert result == [vec]
    fake_client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", input=["hello"]
    )


def test_embed_batch():
    v1 = [0.1] * DEFAULT_DIMENSIONS
    v2 = [0.2] * DEFAULT_DIMENSIONS
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = _fake_response(v1, v2)
    embedder = Embedder(client=fake_client)

    result = embedder.embed(["foo", "bar"])

    assert result == [v1, v2]


def test_embed_empty_list_short_circuits():
    fake_client = MagicMock()
    embedder = Embedder(client=fake_client)

    result = embedder.embed([])

    assert result == []
    fake_client.embeddings.create.assert_not_called()


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        Embedder()
