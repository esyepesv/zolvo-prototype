from __future__ import annotations

import time

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from zolvo.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

log = structlog.get_logger(__name__)

# Ollama Cloud uses OpenAI-compatible format at ollama.com.
_API_URL = "https://ollama.com/v1/chat/completions"

# Map task types to model sizes: cheap for classification, large for critical generation.
_MODELS: dict[str, str] = {
    "classification": "gemma3:4b",
    "generation_standard": "gemma3:12b",
    "generation_critical": "gemma4:31b",
    "embedding": "gemma3:4b",
}


class OllamaProvider(LLMProvider):
    """Ollama Cloud provider via OpenAI-compatible API.

    Uses ollama.com public endpoint with bearer token auth.
    Models available: gemma4:31b (critical), gemma3:12b (standard), gemma3:4b (cheap).
    """

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
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(_API_URL, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        tokens_in = data["usage"]["prompt_tokens"]
        tokens_out = data["usage"]["completion_tokens"]

        log.info(
            "llm.complete",
            provider=self.provider_name,
            model=model,
            task_type=request.task_type,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            latency_ms=latency_ms,
        )

    @property
    def provider_name(self) -> str:
        return "ollama"
