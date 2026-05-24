from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

TaskType = Literal["classification", "generation_standard", "generation_critical", "embedding"]


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    task_type: TaskType
    system_prompt: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    # Preserved for agent_runs persistence in Hito 2
    extra: dict[str, object] = field(default_factory=dict)


class LLMProvider(ABC):
    """Strategy interface for LLM providers."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request and return a structured response."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier used in agent_runs and routing config."""


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails after retries."""
