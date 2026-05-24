from __future__ import annotations

from zolvo.llm.base import LLMProvider, LLMRequest, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Deterministic provider for tests. Returns predefined responses by task_type."""

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides: dict[str, str] = overrides or {}
        self._default = "Respuesta de prueba."

    async def complete(self, request: LLMRequest) -> LLMResponse:
        content = self._overrides.get(
            request.task_type, self._overrides.get("default", self._default)
        )
        return LLMResponse(
            content=content,
            model="fake-model-1",
            provider=self.provider_name,
            tokens_in=len(request.prompt.split()),
            tokens_out=len(content.split()),
            cost_usd=0.0,
            latency_ms=0,
        )

    @property
    def provider_name(self) -> str:
        return "fake"
