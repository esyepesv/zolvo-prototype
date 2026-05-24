from __future__ import annotations

import time

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from zolvo.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)

# Default model when none specified. Override via OLLAMA_MODEL env var.
_DEFAULT_MODEL = "qwen3-coder"

# Ollama natively implements the Anthropic Messages API at the same endpoint.
# Docs: https://ollama.com/blog/openai-compatibility (Anthropic compat since v0.14+)
_API_PATH = "/api/messages"


class OllamaProvider(LLMProvider):
    """Ollama local provider via Anthropic Messages API.

    Ollama v0.14+ exposes an Anthropic-compatible endpoint, so this provider
    reuses the same request/response shape as AnthropicProvider but points at
    the local Ollama instance. No internet required; ideal for PII-sensitive tasks.
    """

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = _DEFAULT_MODEL
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def complete(self, request: LLMRequest) -> LLMResponse:
        messages: list[dict[str, str]] = [{"role": "user", "content": request.prompt}]

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        headers = {
            "x-api-key": "ollama",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        url = f"{self._base_url}{_API_PATH}"
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()

        content = data["content"][0]["text"]
        tokens_in = data["usage"]["input_tokens"]
        tokens_out = data["usage"]["output_tokens"]

        log.info(
            "llm.complete",
            provider=self.provider_name,
            model=self._model,
            task_type=request.task_type,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=self._model,
            provider=self.provider_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            latency_ms=latency_ms,
        )

    @property
    def provider_name(self) -> str:
        return "ollama"
