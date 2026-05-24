from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SendResult:
    success: bool
    channel: str
    external_id: str | None = None


class ChannelAdapter(ABC):
    """Abstraction over outbound message channels (LinkedIn, Email, …)."""

    @abstractmethod
    async def send_message(
        self,
        *,
        to: str,
        body: str,
        subject: str | None = None,
    ) -> SendResult: ...

    @property
    @abstractmethod
    def channel_name(self) -> str: ...
