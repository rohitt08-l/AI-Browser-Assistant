"""Async LLM access with provider fallback.

All supported providers speak the OpenAI chat-completions protocol (Groq via
its OpenAI-compatible endpoint), so a single SDK covers them. Clients are
created once and reused so HTTP connections are pooled. Transient errors are
retried by the SDK (`max_retries`, exponential backoff); if the primary
provider still fails, the optional fallback provider is tried.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAIError

from backend.core.config import Settings
from backend.core.errors import LLMError

logger = logging.getLogger(__name__)

Message = dict[str, str]


@dataclass
class _Backend:
    name: str
    client: AsyncOpenAI
    model: str


def _build_backend(provider: str, settings: Settings) -> _Backend:
    common = {"timeout": settings.llm_timeout_seconds, "max_retries": settings.llm_max_retries}
    if provider == "groq":
        client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url, **common)
        return _Backend("groq", client, settings.groq_model)
    if provider == "azure":
        client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            **common,
        )
        return _Backend("azure", client, settings.azure_deployment_name)
    if provider == "openai":
        client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, **common)
        return _Backend("openai", client, settings.openai_model)
    raise ValueError(f"Unsupported provider: {provider}")


class LLMService:
    def __init__(self, settings: Settings):
        self._temperature = settings.llm_temperature
        self._backends = [_build_backend(settings.llm_provider, settings)]
        if settings.llm_fallback_provider:
            self._backends.append(_build_backend(settings.llm_fallback_provider, settings))

    async def complete(self, messages: list[Message], max_tokens: int | None = None) -> str:
        """Return the full completion text."""
        last_error: Exception | None = None
        for backend in self._backends:
            try:
                response = await backend.client.chat.completions.create(
                    model=backend.model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except OpenAIError as exc:
                last_error = exc
                logger.warning("LLM provider %s failed: %s", backend.name, exc)
        raise LLMError(_describe(last_error)) from last_error

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Yield completion tokens as they arrive.

        Falls back to the next provider only if nothing has been streamed yet,
        so the user never sees two half-answers spliced together.
        """
        last_error: Exception | None = None
        for backend in self._backends:
            started = False
            try:
                response = await backend.client.chat.completions.create(
                    model=backend.model,
                    messages=messages,
                    temperature=self._temperature,
                    stream=True,
                )
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        started = True
                        yield delta
                return
            except OpenAIError as exc:
                last_error = exc
                logger.warning("LLM provider %s failed while streaming: %s", backend.name, exc)
                if started:
                    break
        raise LLMError(_describe(last_error)) from last_error

    async def aclose(self) -> None:
        for backend in self._backends:
            await backend.client.close()


def _describe(exc: Exception | None) -> str:
    if exc is None:
        return "The AI provider returned no response."
    name = type(exc).__name__
    if "RateLimit" in name:
        return "The AI provider is rate-limiting requests. Please try again in a moment."
    if "Authentication" in name or "PermissionDenied" in name:
        return "The AI provider rejected the API key. Check the backend configuration."
    if "Timeout" in name or "Connection" in name:
        return "Could not reach the AI provider. Please try again."
    if "BadRequest" in name:
        return "The AI provider rejected the request (the page may be too large for this model)."
    return "The AI provider returned an error. Please try again."
