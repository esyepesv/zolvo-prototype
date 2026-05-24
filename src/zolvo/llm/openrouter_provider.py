from __future__ import annotations

import time

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from zolvo.llm.base import EmbeddingResponse, LLMProvider, LLMProviderError, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)

# OpenRouter uses OpenAI-compatible format.
# Model IDs confirmed at openrouter.ai/anthropic/ (May 2026)
_MODELS: dict[str, str] = {
    "classification": "anthropic/claude-haiku-4.5",
    "generation_standard": "anthropic/claude-haiku-4.5",
    "generation_critical": "anthropic/claude-sonnet-4.5",
    "embedding": "openai/text-embedding-3-small",
}

# Cost per 1K tokens (USD) from openrouter.ai pricing
_COSTS: dict[str, dict[str, float]] = {
    "anthropic/claude-haiku-4.5": {"in": 0.001, "out": 0.005},
    "anthropic/claude-sonnet-4.5": {"in": 0.003, "out": 0.015},
    "anthropic/claude-opus-4.5": {"in": 0.005, "out": 0.025},
    "openai/text-embedding-3-small": {"in": 0.00002, "out": 0.0},
}

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider via OpenAI-compatible API.

    Primary provider for the demo: unified gateway to Claude models at
    competitive prices without direct Anthropic/OpenAI accounts.
    """

    def __init__(self, api_key: str, site_url: str = "", site_name: str = "Zolvo Demo") -> None:
        self._api_key = api_key
        self._site_url = site_url
        self._site_name = site_name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = _MODELS.get(request.task_type, _MODELS["generation_standard"])

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        if self._site_url:
            headers["HTTP-Referer"] = self._site_url
        if self._site_name:
            headers["X-Title"] = self._site_name

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(_API_URL, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"OpenRouter request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        tokens_in = data["usage"]["prompt_tokens"]
        tokens_out = data["usage"]["completion_tokens"]
        costs = _COSTS.get(model, {"in": 0.0, "out": 0.0})
        cost_usd = (tokens_in / 1000) * costs["in"] + (tokens_out / 1000) * costs["out"]

        log.info(
            "llm.complete",
            provider=self.provider_name,
            model=model,
            task_type=request.task_type,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def embed(self, text: str) -> EmbeddingResponse:
        model = _MODELS["embedding"]
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
            "X-Title": self._site_name,
        }
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _EMBED_URL,
                    json={"model": model, "input": text},
                    headers=headers,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"OpenRouter embed HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"OpenRouter embed request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()
        vector: list[float] = data["data"][0]["embedding"]
        tokens_in: int = data.get("usage", {}).get("prompt_tokens", len(text.split()))
        costs = _COSTS.get(model, {"in": 0.00002, "out": 0.0})
        cost_usd = (tokens_in / 1000) * costs["in"]

        return EmbeddingResponse(
            vector=vector,
            model=model,
            provider=self.provider_name,
            tokens_in=tokens_in,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
        )

    @property
    def provider_name(self) -> str:
        return "openrouter"
