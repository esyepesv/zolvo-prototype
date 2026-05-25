from __future__ import annotations

import asyncio
import random
from collections import OrderedDict
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

# In-memory LRU lock cache per conversation_id — prevents parallel processing of
# the same conversation in a single-process deployment (ADR-06). Bounded to avoid
# unbounded growth across many distinct conversations.
_MAX_CONV_LOCKS = 1000
_conv_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()


def _get_conv_lock(conv_id: str) -> asyncio.Lock:
    if conv_id in _conv_locks:
        _conv_locks.move_to_end(conv_id)
        return _conv_locks[conv_id]
    if len(_conv_locks) >= _MAX_CONV_LOCKS:
        _conv_locks.popitem(last=False)  # evict least-recently-used
    _conv_locks[conv_id] = asyncio.Lock()
    return _conv_locks[conv_id]


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

    # Persist the inbound message before acquiring the lock so it is never lost.
    await message_repo.create(
        tenant_id=body.tenant_id,
        conversation_id=body.conversation_id,
        direction="inbound",
        content=body.message,
    )

    # ADR-06: serialize processing per conversation and apply debounce jitter.
    async with _get_conv_lock(str(body.conversation_id)):
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
