from __future__ import annotations

import pytest

from zolvo.llm.base import LLMProviderError, LLMRequest
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway

# ─── FakeLLMProvider ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fake_provider_returns_default() -> None:
    provider = FakeLLMProvider()
    req = LLMRequest(prompt="test", task_type="classification")
    result = await provider.complete(req)
    assert result.content == "Respuesta de prueba."
    assert result.provider == "fake"
    assert result.cost_usd == 0.0


@pytest.mark.asyncio
async def test_fake_provider_returns_task_override() -> None:
    provider = FakeLLMProvider(overrides={"classification": "interesado"})
    req = LLMRequest(prompt="test", task_type="classification")
    result = await provider.complete(req)
    assert result.content == "interesado"


@pytest.mark.asyncio
async def test_fake_provider_falls_back_to_default_key() -> None:
    provider = FakeLLMProvider(overrides={"default": "fallback_response"})
    req = LLMRequest(prompt="test", task_type="generation_critical")
    result = await provider.complete(req)
    assert result.content == "fallback_response"


# ─── LLMGateway ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gateway_with_fake_provider_completes() -> None:
    fake = FakeLLMProvider(overrides={"classification": "objection_price"})
    gateway = _make_gateway(fake)
    result = await gateway.complete(task_type="classification", prompt="Su precio es alto")
    assert result.content == "objection_price"
    assert result.provider == "fake"


@pytest.mark.asyncio
async def test_gateway_raises_when_no_providers_configured() -> None:
    gateway = _make_gateway(None)
    with pytest.raises(LLMProviderError, match="No LLM providers configured"):
        await gateway.complete(task_type="classification", prompt="test")


@pytest.mark.asyncio
async def test_gateway_falls_back_when_preferred_not_available() -> None:
    """If preferred provider is 'anthropic' but only 'openai' is registered, use openai."""
    fake_openai = FakeLLMProvider(overrides={"default": "openai_response"})
    gateway = _make_gateway(None)
    gateway._providers = {"openai": fake_openai}
    gateway._settings.preferred_llm_provider = "anthropic"  # type: ignore[misc]

    result = await gateway.complete(task_type="classification", prompt="test")
    assert result.provider == "fake"  # FakeLLMProvider always reports "fake"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_gateway(provider: FakeLLMProvider | None) -> LLMGateway:
    """Build a LLMGateway with no real providers, injecting a fake one if given."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.anthropic_api_key = ""
    settings.openai_api_key = ""
    settings.preferred_llm_provider = "fake"

    gw = LLMGateway(settings)
    gw._providers = {}
    if provider is not None:
        gw._providers["fake"] = provider
    return gw
