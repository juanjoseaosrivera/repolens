"""Unit tests for the LLM wrapper. Network calls are mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from repolens.llm import LLM


def _fake_message(text: str = "hi", input_tokens: int = 10, output_tokens: int = 5):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )


def test_complete_returns_text_and_usage():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message(text="hello!")
    llm = LLM(client=fake_client)

    response = llm.complete("say hi", system="be terse")

    assert response.text == "hello!"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.model == "claude-sonnet-4-6"
    assert response.stop_reason == "end_turn"


def test_complete_passes_system_and_messages():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message()
    llm = LLM(client=fake_client, model="claude-sonnet-4-6")

    llm.complete("question?", system="you are helpful", max_tokens=128)

    fake_client.messages.create.assert_called_once()
    kwargs = fake_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["max_tokens"] == 128
    assert kwargs["system"] == "you are helpful"
    assert kwargs["messages"] == [{"role": "user", "content": "question?"}]


def test_complete_omits_system_when_none():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_message()
    llm = LLM(client=fake_client)

    llm.complete("hello")

    kwargs = fake_client.messages.create.call_args.kwargs
    assert "system" not in kwargs


def test_complete_concatenates_text_blocks():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="part 1 "),
            SimpleNamespace(type="thinking", thinking="ignore me"),
            SimpleNamespace(type="text", text="part 2"),
        ],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )
    llm = LLM(client=fake_client)

    response = llm.complete("hi")

    assert response.text == "part 1 part 2"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        LLM()
