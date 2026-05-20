"""HTTP-only LLM providers (Anthropic, OpenAI-compatible, Ollama/local) and failover chain.

Exports ``AIProvider`` (abstract base), ``AIResponse``, concrete providers, and
``ProviderChain`` (tries multiple providers in order until one succeeds).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class AIResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AIResponse:
        ...

    @abstractmethod
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> AIResponse:
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model})"


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError))


async def _post_json(
    url: str,
    *,
    json: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    timeout: float = 60.0,
    attempts: int = 3,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    retryer = AsyncRetrying(
        retry=retry_if_exception(_is_retryable_exception),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(max(1, attempts)),
        reraise=True,
    )

    async def send(active_client: httpx.AsyncClient) -> dict[str, Any]:
        response = await active_client.post(url, json=json, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object from {url}")
        return data

    if client is not None:
        async for attempt in retryer:
            with attempt:
                return await send(client)
    else:
        async with httpx.AsyncClient(timeout=timeout) as owned_client:
            async for attempt in retryer:
                with attempt:
                    return await send(owned_client)

    raise RuntimeError(f"Request did not return a response: {url}")


def _translation_prompt(text: str, source_lang: str, target_lang: str) -> str:
    return (
        f"Translate the following {source_lang} text to {target_lang}. "
        f"Return ONLY the translation, nothing else.\n\n{text}"
    )


def _anthropic_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    chunks = []
    for item in content:
        if isinstance(item, dict):
            chunks.append(str(item.get("text") or ""))
    return "".join(chunks)


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60.0,
        attempts: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._attempts = attempts
        self._client = http_client

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AIResponse:
        data = await _post_json(
            f"{self._base_url}/messages",
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system or "You are a financial news analyst.",
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=self._timeout,
            attempts=self._attempts,
            client=self._client,
        )
        usage = data.get("usage") or {}
        return AIResponse(
            text=_anthropic_text(data.get("content")),
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            provider=self.name,
            model=self.model,
        )

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> AIResponse:
        return await self.complete(
            _translation_prompt(text, source_lang, target_lang),
            system="You are a professional translator.",
            max_tokens=len(text) * 3,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not provide embeddings.")


class OpenAICompatibleProvider(AIProvider):
    """Provider for OpenAI-compatible chat and embeddings endpoints."""

    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        base_url: str | None = None,
        provider_name: str | None = None,
        timeout: float = 60.0,
        attempts: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout
        self._attempts = attempts
        self._client = http_client
        if provider_name:
            self.name = provider_name

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AIResponse:
        data = await _post_json(
            f"{self._base_url}/chat/completions",
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": system or "You are a financial news analyst.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            headers={
                "authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            },
            timeout=self._timeout,
            attempts=self._attempts,
            client=self._client,
        )
        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else {}
        usage = data.get("usage") or {}
        return AIResponse(
            text=str((message or {}).get("content") or ""),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            provider=self.name,
            model=self.model,
        )

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> AIResponse:
        return await self.complete(
            _translation_prompt(text, source_lang, target_lang),
            system="You are a professional translator.",
            max_tokens=len(text) * 3,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = await _post_json(
            f"{self._base_url}/embeddings",
            json={"model": self.model, "input": texts},
            headers={
                "authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            },
            timeout=self._timeout,
            attempts=self._attempts,
            client=self._client,
        )
        items = data.get("data") or []
        return [list(item.get("embedding") or []) for item in items if isinstance(item, dict)]


class LocalProvider(AIProvider):
    """Local HTTP provider using Ollama-compatible generate and embeddings APIs."""

    name = "local"

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        *,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        attempts: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._attempts = attempts
        self._client = http_client

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AIResponse:
        data = await _post_json(
            f"{self._base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "system": system or "You are a financial news analyst.",
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=self._timeout,
            attempts=self._attempts,
            client=self._client,
        )
        return AIResponse(
            text=str(data.get("response") or ""),
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
            provider=self.name,
            model=self.model,
        )

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> AIResponse:
        return await self.complete(
            _translation_prompt(text, source_lang, target_lang),
            system="You are a professional translator.",
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            data = await _post_json(
                f"{self._base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self._timeout,
                attempts=self._attempts,
                client=self._client,
            )
            embeddings.append(list(data.get("embedding") or []))
        return embeddings


OpenAIProvider = OpenAICompatibleProvider


@dataclass
class ProviderChain:
    """Try providers in order until one completes the requested operation."""

    task: str
    providers: list[AIProvider] = field(default_factory=list)

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AIResponse:
        for provider in self.providers:
            try:
                return await provider.complete(prompt, system, max_tokens)
            except Exception as exc:
                log.warning("%s: %s failed: %s", self.task, provider, exc)
        raise RuntimeError(f"All providers failed for task: {self.task}")

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> AIResponse:
        for provider in self.providers:
            try:
                return await provider.translate(text, source_lang, target_lang)
            except Exception as exc:
                log.warning("%s: %s translation failed: %s", self.task, provider, exc)
        raise RuntimeError(f"All providers failed for translation: {self.task}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        for provider in self.providers:
            try:
                return await provider.embed(texts)
            except Exception as exc:
                log.warning("%s: %s embed failed: %s", self.task, provider, exc)
        raise RuntimeError(f"All providers failed for embedding: {self.task}")


__all__ = [
    "AIProvider",
    "AIResponse",
    "AnthropicProvider",
    "LocalProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "ProviderChain",
]
