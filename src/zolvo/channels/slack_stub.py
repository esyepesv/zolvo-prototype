from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


class SlackStub:
    """Simulates posting to a Slack channel. Logs instead of calling the Slack Webhook API.

    In production: POST to an Incoming Webhook URL with the escalation payload.
    The sales rep sees the notification in #zolvo-escalations and reviews the draft.
    """

    async def notify_handoff(
        self,
        *,
        conversation_id: str,
        intent: str,
        reason: str,
    ) -> None:
        log.warning(
            "slack.handoff_alert",
            conversation_id=conversation_id,
            intent=intent,
            reason=reason,
            action_required="Assign to SDR for manual response",
        )

    async def notify_escalation(
        self,
        *,
        conversation_id: str,
        intent: str,
        confidence_score: float,
        draft_preview: str,
        reason: str,
    ) -> None:
        log.warning(
            "slack.escalation_alert",
            conversation_id=conversation_id,
            intent=intent,
            confidence_score=round(confidence_score, 3),
            draft_preview=draft_preview[:120],
            reason=reason,
            action_required="Review and approve/edit draft before sending",
        )
