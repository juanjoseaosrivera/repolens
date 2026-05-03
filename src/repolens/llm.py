"""Thin wrapper around the Anthropic SDK for single-turn Claude calls."""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str | None


class LLM:
    """Single-turn Claude wrapper. Stateless — caller manages history."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
                )
            self._client = anthropic.Anthropic(api_key=key)

    def complete(
        self,
        user_message: str,
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": user_message}]
        if system is None:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
            )
        else:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
                system=system,
            )

        text_parts = [block.text for block in message.content if block.type == "text"]
        return LLMResponse(
            text="".join(text_parts),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=message.model,
            stop_reason=message.stop_reason,
        )
