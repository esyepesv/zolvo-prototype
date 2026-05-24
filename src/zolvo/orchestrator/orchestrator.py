from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

import structlog

from zolvo.agents.conversationalist import ConversationalistAgent
from zolvo.agents.evaluator import EvaluatorAgent
from zolvo.intent.classifier import IntentClassifier

log = structlog.get_logger(__name__)

Action = Literal["send", "handoff", "escalate"]


@dataclass(frozen=True)
class OrchestratorResult:
    action: Action
    conversation_id: uuid.UUID
    tenant_id: uuid.UUID
    intent: str
    draft: str | None           # populated for "send" and "escalate"
    confidence_score: float | None  # populated for "send" and "escalate"
    reason: str


class Orchestrator:
    """Coordinates the two-gate pipeline: classify → generate → evaluate → route."""

    def __init__(
        self,
        intent_classifier: IntentClassifier,
        conversationalist: ConversationalistAgent,
        evaluator: EvaluatorAgent,
    ) -> None:
        self._classifier = intent_classifier
        self._conversationalist = conversationalist
        self._evaluator = evaluator

    async def handle_reply(
        self,
        *,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        message: str,
    ) -> OrchestratorResult:
        # ── Gate 1: Intent Classification ────────────────────────────────────
        intent_result = await self._classifier.classify(message)

        log.info(
            "orchestrator.intent_classified",
            conversation_id=str(conversation_id),
            intent=intent_result.intent,
            should_handoff=intent_result.should_handoff,
        )

        if intent_result.should_handoff:
            return OrchestratorResult(
                action="handoff",
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                intent=intent_result.intent,
                draft=None,
                confidence_score=None,
                reason=f"Intent '{intent_result.intent}' requires human handling.",
            )

        # ── Generation ───────────────────────────────────────────────────────
        conv_result = await self._conversationalist.run(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            latest_message=message,
            intent_result=intent_result,
        )

        # ── Gate 2: Confidence Gate ──────────────────────────────────────────
        eval_context = (
            f"Intent detectado: {intent_result.intent}\n"
            f"Mensaje del prospecto: {message}"
        )
        eval_result = await self._evaluator.evaluate(
            draft=conv_result.draft_message,
            context=eval_context,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
        )

        log.info(
            "orchestrator.evaluated",
            conversation_id=str(conversation_id),
            score=round(eval_result.score, 4),
            should_send=eval_result.should_send,
        )

        action: Action = "send" if eval_result.should_send else "escalate"
        return OrchestratorResult(
            action=action,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            intent=intent_result.intent,
            draft=conv_result.draft_message,
            confidence_score=eval_result.score,
            reason=eval_result.reason,
        )
