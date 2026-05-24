from __future__ import annotations

import time

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from zolvo.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)

# Model selection per task type
_MODELS: dict[str, str] = {
    "classification": "claude-haiku-4-5-20251001",
    "generation_standard": "claude-haiku-4-5-20251001",
    "generation_critical": "claude-sonnet-4-6",
    "embedding": "",  # Anthropic has no embeddings API; gateway falls back
}

# Cost per 1K tokens (USD) — approximate as of May 2026
_COSTS: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"in": 0.00025, "out": 0.00125},
    "claude-sonnet-4-6": {"in": 0.003, "out": 0.015},
}

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider via httpx (no SDK)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = _MODELS.get(request.task_type, _MODELS["generation_standard"])
        if not model:
            raise LLMProviderError(f"Anthropic does not support task_type={request.task_type}")

        messages = [{"role": "user", "content": request.prompt}]
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(_API_URL, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Anthropic HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"Anthropic request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()

        content = data["content"][0]["text"]
        tokens_in = data["usage"]["input_tokens"]
        tokens_out = data["usage"]["output_tokens"]
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

    @property
    def provider_name(self) -> str:
        return "anthropic"
