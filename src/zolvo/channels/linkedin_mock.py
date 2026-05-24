from __future__ import annotations

import structlog

from zolvo.channels.base import ChannelAdapter, SendResult

log = structlog.get_logger(__name__)


class LinkedInMockAdapter(ChannelAdapter):
    """Simulates sending a LinkedIn DM. Logs the send event instead of calling the API.

    In production this would call the LinkedIn Messaging API (or a scraper/automation
    layer). For the prototype it proves the channel abstraction is wired end-to-end.
    """

    async def send_message(
        self,
        *,
        to: str,
        body: str,
        subject: str | None = None,
    ) -> SendResult:
        log.info(
            "channel.linkedin.send",
            to=to,
            body_preview=body[:120],
            chars=len(body),
        )
        return SendResult(success=True, channel=self.channel_name)

    @property
    def channel_name(self) -> str:
        return "linkedin"
