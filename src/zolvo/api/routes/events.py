from __future__ import annotations

import asyncio
import random
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends

from zolvo.api.deps import (
    get_linkedin_adapter,
    get_message_repo,
    get_orchestrator,
    get_slack_stub,
)
from zolvo.channels.linkedin_mock import LinkedInMockAdapter
from zolvo.channels.slack_stub import SlackStub
from zolvo.config import get_settings
from zolvo.orchestrator.orchestrator import Orchestrator
from zolvo.repositories.messages import MessageRepository
from zolvo.schemas import ReplyRequest, ReplyResponse

router = APIRouter(prefix="/events", tags=["events"])
log = structlog.get_logger(__name__)


@router.post("/reply", response_model=ReplyResponse)
async def receive_reply(
    body: ReplyRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    message_repo: MessageRepository = Depends(get_message_repo),
    linkedin: LinkedInMockAdapter = Depends(get_linkedin_adapter),
    slack: SlackStub = Depends(get_slack_stub),
) -> ReplyResponse:
    """Receive an inbound reply → debounce → two-gate pipeline → route via channel or escalate."""
    settings = get_settings()

    # Persist the inbound message before debounce so it is not lost if the process restarts.
    await message_repo.create(
        tenant_id=body.tenant_id,
        conversation_id=body.conversation_id,
        direction="inbound",
        content=body.message,
    )

    # ADR-06: debounce window before processing to consolidate rapid messages and
    # produce human-like response timing.
    if settings.debounce_max_seconds > 0:
        delay = random.uniform(settings.debounce_min_seconds, settings.debounce_max_seconds)
        log.info(
            "debounce.waiting",
            delay_seconds=round(delay, 1),
            conversation_id=str(body.conversation_id),
        )
        await asyncio.sleep(delay)
        log.info("debounce.ready", conversation_id=str(body.conversation_id))

    result = await orchestrator.handle_reply(
        conversation_id=body.conversation_id,
        tenant_id=body.tenant_id,
        message=body.message,
    )

    if result.action == "send" and result.draft:
        await message_repo.create(
            tenant_id=body.tenant_id,
            conversation_id=body.conversation_id,
            direction="outbound",
            content=result.draft,
            generated_by_agent="conversationalist",
            confidence_score=Decimal(str(round(result.confidence_score or 0, 4))),
        )
        # Simulate delivery via channel adapter (LinkedIn DM in this demo)
        await linkedin.send_message(
            to=str(body.conversation_id),
            body=result.draft,
        )

    elif result.action == "handoff":
        await slack.notify_handoff(
            conversation_id=str(body.conversation_id),
            intent=result.intent,
            reason=result.reason,
        )

    elif result.action == "escalate" and result.draft:
        await slack.notify_escalation(
            conversation_id=str(body.conversation_id),
            intent=result.intent,
            confidence_score=result.confidence_score or 0.0,
            draft_preview=result.draft,
            reason=result.reason,
        )

    return ReplyResponse(
        action=result.action,
        intent=result.intent,
        draft=result.draft,
        confidence_score=result.confidence_score,
        reason=result.reason,
    )
