"""Anthropic completion wrapper.

Business logic calls this module — never the Anthropic SDK directly.
Handles retries, telemetry, and structured logging.
"""

from collections.abc import AsyncIterator

import anthropic
import structlog

from repolens.config import get_settings
from repolens.errors import RepoLensError

log = structlog.get_logger(__name__)


class CompletionError(RepoLensError):
    """Raised when an LLM completion call fails after retries."""


class CompletionClient:
    """Thin async wrapper around the Anthropic Messages API."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.default_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a non-streaming completion request.

        Returns the full assistant response text.
        """
        model = model or self._model
        max_tokens = max_tokens or self._max_tokens
        temperature = temperature if temperature is not None else self._temperature

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
        except anthropic.APIError as exc:
            log.error(
                "llm.completion_failed",
                model=model,
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise CompletionError(f"Completion failed: {exc}") from exc

        text = response.content[0].text  # type: ignore[union-attr]
        log.info(
            "llm.completion",
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return text

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens as they arrive."""
        model = model or self._model
        max_tokens = max_tokens or self._max_tokens
        temperature = temperature if temperature is not None else self._temperature

        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield text

                response = await stream.get_final_message()
                log.info(
                    "llm.stream_complete",
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
        except anthropic.APIError as exc:
            log.error(
                "llm.stream_failed",
                model=model,
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise CompletionError(f"Stream failed: {exc}") from exc
