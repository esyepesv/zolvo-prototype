from __future__ import annotations

import structlog

from zolvo.config import Settings
from zolvo.llm.anthropic_provider import AnthropicProvider
from zolvo.llm.base import (
    EmbeddingResponse,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    TaskType,
)
from zolvo.llm.circuit_breaker import CircuitBreaker, CircuitOpenError
from zolvo.llm.ollama_provider import OllamaProvider
from zolvo.llm.openai_provider import OpenAIProvider
from zolvo.llm.openrouter_provider import OpenRouterProvider

log = structlog.get_logger(__name__)


class LLMGateway:
    """Routes LLM requests to the appropriate provider based on task_type and settings.

    Provider priority:
      1. preferred_llm_provider from settings (if configured and key present)
      2. Any other available provider as fallback (skipping providers with open circuits)
    """

    def __init__(
        self, settings: Settings, extra_providers: dict[str, LLMProvider] | None = None
    ) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._setup_providers()
        if extra_providers:
            self._providers.update(extra_providers)

    def _setup_providers(self) -> None:
        # Priority order for demo: openrouter → ollama → anthropic → openai
        if self._settings.openrouter_api_key:
            self._providers["openrouter"] = OpenRouterProvider(self._settings.openrouter_api_key)
        if self._settings.ollama_api_key:
            self._providers["ollama"] = OllamaProvider(self._settings.ollama_api_key)
        if self._settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(self._settings.anthropic_api_key)
        if self._settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider(self._settings.openai_api_key)

    async def complete(
        self,
        *,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a completion request via the selected provider, with circuit breaker protection."""
        provider = self._select_provider(task_type)
        provider_name = provider.provider_name
        breaker = self._breakers.setdefault(provider_name, CircuitBreaker())

        try:
            breaker.before_call(provider_name)
        except CircuitOpenError:
            # Preferred provider circuit is open — try any available alternative
            for name, alt in self._providers.items():
                alt_breaker = self._breakers.setdefault(name, CircuitBreaker())
                if alt_breaker.state != "open":
                    log.warning(
                        "llm.gateway.circuit_bypass",
                        failed=provider_name,
                        using=name,
                        task_type=task_type,
                    )
                    provider, provider_name, breaker = alt, name, alt_breaker
                    break
            else:
                raise LLMProviderError("All LLM providers have open circuit breakers.")

        request = LLMRequest(
            prompt=prompt,
            task_type=task_type,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        log.debug("llm.gateway.routing", provider=provider_name, task_type=task_type)
        try:
            result = await provider.complete(request)
            breaker.record_success()
            return result
        except LLMProviderError as exc:
            breaker.record_failure()
            log.warning(
                "llm.gateway.provider_failure",
                provider=provider_name,
                failures=breaker._failures,
                error=str(exc),
            )
            raise

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate a text embedding. Tries providers in priority order until one succeeds."""
        order = ["openai", *[k for k in self._providers if k != "openai"]]
        for name in order:
            provider = self._providers.get(name)
            if provider is None:
                continue
            try:
                return await provider.embed(text)
            except NotImplementedError:
                continue
        raise LLMProviderError("No embedding provider available. Set OPENAI_API_KEY.")

    def _select_provider(self, task_type: TaskType) -> LLMProvider:
        if not self._providers:
            raise LLMProviderError(
                "No LLM providers configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
            )

        preferred = self._settings.preferred_llm_provider
        if preferred in self._providers:
            return self._providers[preferred]

        # Fallback to first available
        fallback = next(iter(self._providers.values()))
        log.warning(
            "llm.gateway.fallback",
            preferred=preferred,
            using=fallback.provider_name,
            task_type=task_type,
        )
        return fallback
