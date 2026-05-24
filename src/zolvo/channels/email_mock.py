from __future__ import annotations

import structlog

from zolvo.channels.base import ChannelAdapter, SendResult

log = structlog.get_logger(__name__)


class EmailMockAdapter(ChannelAdapter):
    """Simulates sending an email via SMTP. Logs instead of calling an email provider.

    In production: SendGrid / AWS SES / Gmail API.
    """

    async def send_message(
        self,
        *,
        to: str,
        body: str,
        subject: str | None = None,
    ) -> SendResult:
        log.info(
            "channel.email.send",
            to=to,
            subject=subject or "(no subject)",
            body_preview=body[:120],
            chars=len(body),
        )
        return SendResult(success=True, channel=self.channel_name)

    @property
    def channel_name(self) -> str:
        return "email"
