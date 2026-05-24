from __future__ import annotations

from abc import ABC, abstractmethod

from zolvo.llm.gateway import LLMGateway


class AgentBase(ABC):
    """Base class for all Zolvo agents. Provides gateway DI via constructor."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Identifier logged in agent_runs."""
