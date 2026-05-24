from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends

from zolvo.api.deps import get_message_repo, get_orchestrator
from zolvo.orchestrator.orchestrator import Orchestrator
from zolvo.repositories.messages import MessageRepository
from zolvo.schemas import ReplyRequest, ReplyResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/reply", response_model=ReplyResponse)
async def receive_reply(
    body: ReplyRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    message_repo: MessageRepository = Depends(get_message_repo),
) -> ReplyResponse:
    """Receive an inbound reply → run two-gate pipeline → return routing decision."""
    await message_repo.create(
        tenant_id=body.tenant_id,
        conversation_id=body.conversation_id,
        direction="inbound",
        content=body.message,
    )

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

    return ReplyResponse(
        action=result.action,
        intent=result.intent,
        draft=result.draft,
        confidence_score=result.confidence_score,
        reason=result.reason,
    )
