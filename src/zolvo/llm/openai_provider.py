from __future__ import annotations

import time

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from zolvo.llm.base import EmbeddingResponse, LLMProvider, LLMProviderError, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)

_MODELS: dict[str, str] = {
    "classification": "gpt-4o-mini",
    "generation_standard": "gpt-4o-mini",
    "generation_critical": "gpt-4o",
    "embedding": "text-embedding-3-small",
}

# Cost per 1K tokens (USD) — approximate as of May 2026
_COSTS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"in": 0.00015, "out": 0.0006},
    "gpt-4o": {"in": 0.0025, "out": 0.01},
    "text-embedding-3-small": {"in": 0.00002, "out": 0.0},
}

_API_URL = "https://api.openai.com/v1/chat/completions"
_EMBED_URL = "https://api.openai.com/v1/embeddings"
_EMBED_MODEL = "text-embedding-3-small"
_EMBED_COST_PER_1K = 0.00002


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions API provider via httpx (no SDK)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

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

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(_API_URL, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"OpenAI HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

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
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _EMBED_URL,
                    json={"model": _EMBED_MODEL, "input": text},
                    headers=headers,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"OpenAI embed HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"OpenAI embed request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()
        vector: list[float] = data["data"][0]["embedding"]
        tokens_in: int = data["usage"]["prompt_tokens"]
        cost_usd = (tokens_in / 1000) * _EMBED_COST_PER_1K

        log.info(
            "llm.embed",
            provider=self.provider_name,
            model=_EMBED_MODEL,
            tokens_in=tokens_in,
            cost_usd=round(cost_usd, 8),
            latency_ms=latency_ms,
        )
        return EmbeddingResponse(
            vector=vector,
            model=_EMBED_MODEL,
            provider=self.provider_name,
            tokens_in=tokens_in,
            cost_usd=round(cost_usd, 8),
            latency_ms=latency_ms,
        )

    @property
    def provider_name(self) -> str:
        return "openai"
