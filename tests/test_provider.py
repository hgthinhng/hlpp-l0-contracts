import asyncio
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ht_l1_core.llm.provider import (
    AIProvider,
    AIResponse,
    AnthropicProvider,
    LocalProvider,
    OpenAICompatibleProvider,
    ProviderChain,
)


@dataclass
class MockProvider(AIProvider):
    name: str
    model: str = "mock-model"
    fail_complete: bool = False
    fail_translate: bool = False
    fail_embed: bool = False
    complete_calls: list[tuple[str, str, int]] = field(default_factory=list)
    translate_calls: list[tuple[str, str, str]] = field(default_factory=list)
    embed_calls: list[list[str]] = field(default_factory=list)

    async def complete(self, prompt: str, system: str = "", max_tokens: int = 1024) -> AIResponse:
        self.complete_calls.append((prompt, system, max_tokens))
        if self.fail_complete:
            raise RuntimeError(f"{self.name} complete failed")
        return AIResponse(text=f"{self.name} complete", provider=self.name, model=self.model)

    async def translate(self, text: str, source_lang: str, target_lang: str = "en") -> AIResponse:
        self.translate_calls.append((text, source_lang, target_lang))
        if self.fail_translate:
            raise RuntimeError(f"{self.name} translate failed")
        return AIResponse(text=f"{self.name} translate", provider=self.name, model=self.model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(texts)
        if self.fail_embed:
            raise RuntimeError(f"{self.name} embed failed")
        return [[0.1, 0.2, 0.3]]


def test_complete_falls_back_when_primary_fails():
    primary = MockProvider("primary", fail_complete=True)
    fallback = MockProvider("fallback")
    chain = ProviderChain(task="summary", providers=[primary, fallback])

    result = asyncio.run(chain.complete("prompt", system="system", max_tokens=128))

    assert result.provider == "fallback"
    assert primary.complete_calls == [("prompt", "system", 128)]
    assert fallback.complete_calls == [("prompt", "system", 128)]


def test_first_successful_complete_stops_chain():
    primary = MockProvider("primary")
    fallback = MockProvider("fallback")
    chain = ProviderChain(task="summary", providers=[primary, fallback])

    result = asyncio.run(chain.complete("prompt"))

    assert result.provider == "primary"
    assert len(primary.complete_calls) == 1
    assert fallback.complete_calls == []


def test_translate_falls_back_when_primary_fails():
    primary = MockProvider("primary", fail_translate=True)
    fallback = MockProvider("fallback")
    chain = ProviderChain(task="translation", providers=[primary, fallback])

    result = asyncio.run(chain.translate("xin chao", source_lang="vi", target_lang="en"))

    assert result.provider == "fallback"
    assert primary.translate_calls == [("xin chao", "vi", "en")]
    assert fallback.translate_calls == [("xin chao", "vi", "en")]


def test_embed_falls_back_when_primary_fails():
    primary = MockProvider("primary", fail_embed=True)
    fallback = MockProvider("fallback")
    chain = ProviderChain(task="embedding", providers=[primary, fallback])

    result = asyncio.run(chain.embed(["macro", "rates"]))

    assert result == [[0.1, 0.2, 0.3]]
    assert primary.embed_calls == [["macro", "rates"]]
    assert fallback.embed_calls == [["macro", "rates"]]


def test_raises_runtime_error_when_all_providers_fail():
    chain = ProviderChain(
        task="summary",
        providers=[
            MockProvider("primary", fail_complete=True),
            MockProvider("fallback", fail_complete=True),
        ],
    )

    with pytest.raises(RuntimeError, match="All providers failed for task: summary"):
        asyncio.run(chain.complete("prompt"))


def test_provider_chain_does_not_carry_a3_usage_buffer_methods():
    chain = ProviderChain(task="summary")

    assert not hasattr(chain, "_pending_usage")
    assert not hasattr(chain, "_log_usage")
    assert not hasattr(chain, "_flush_usage")
    assert not hasattr(chain, "flush_usage")


def test_core_provider_types_are_available_without_vendor_sdk_imports():
    import ht_l1_core.llm.provider as provider_module

    assert AnthropicProvider.name == "anthropic"
    assert OpenAICompatibleProvider.name == "openai"
    assert LocalProvider.name == "local"

    source = inspect.getsource(provider_module)
    assert "import anthropic" not in source
    assert "from anthropic" not in source
    assert "import openai" not in source
    assert "from openai" not in source
