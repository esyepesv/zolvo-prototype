from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.agents.conversationalist import ConversationalistResult
from zolvo.agents.evaluator import EvaluationResult
from zolvo.intent.classifier import IntentResult
from zolvo.orchestrator.orchestrator import Orchestrator, OrchestratorResult

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_CONV_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000003")
_RUN_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000003")
_DRAFT = "Entiendo tu situación. ¿Tienes disponibilidad esta semana?"


def _make_intent(intent: str, should_handoff: bool = False) -> IntentResult:
    return IntentResult(
        intent=intent,  # type: ignore[arg-type]
        should_handoff=should_handoff,
        confidence=0.92,
        reason="test",
    )


def _make_conv_result() -> ConversationalistResult:
    return ConversationalistResult(
        conversation_id=_CONV_ID,
        draft_message=_DRAFT,
        intent_handled="interested",
        agent_run_id=_RUN_ID,
    )


def _make_eval_result(should_send: bool, score: float = 0.85) -> EvaluationResult:
    return EvaluationResult(
        score=score,
        breakdown={"naturalidad": 0.9, "relevancia": 0.85, "riesgo": 0.05},
        should_send=should_send,
        reason="Evaluación de prueba.",
        agent_run_id=_RUN_ID,
    )


def _make_orchestrator(
    intent: str = "interested",
    should_handoff: bool = False,
    eval_should_send: bool = True,
    eval_score: float = 0.85,
) -> tuple[Orchestrator, MagicMock, MagicMock, MagicMock]:
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=_make_intent(intent, should_handoff))

    conversationalist = MagicMock()
    conversationalist.run = AsyncMock(return_value=_make_conv_result())

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=_make_eval_result(eval_should_send, eval_score))

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=None)

    orchestrator = Orchestrator(classifier, conversationalist, evaluator, agent_run_repo)
    return orchestrator, classifier, conversationalist, evaluator


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handoff_intent_skips_generation() -> None:
    """Handoff intents bypass generation and evaluator entirely."""
    orch, _, conversationalist, evaluator = _make_orchestrator(
        intent="opt_out", should_handoff=True
    )
    result = await orch.handle_reply(
        conversation_id=_CONV_ID, tenant_id=_TENANT, message="No me interesa, gracias."
    )

    assert result.action == "handoff"
    assert result.intent == "opt_out"
    assert result.draft is None
    assert result.confidence_score is None
    conversationalist.run.assert_not_awaited()
    evaluator.evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_good_draft_returns_send() -> None:
    orch, _, _, _ = _make_orchestrator(eval_should_send=True, eval_score=0.88)
    result = await orch.handle_reply(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        message="Me parece interesante, ¿cómo funciona?",
    )

    assert isinstance(result, OrchestratorResult)
    assert result.action == "send"
    assert result.draft == _DRAFT
    assert result.confidence_score == pytest.approx(0.88)
    assert result.conversation_id == _CONV_ID
    assert result.tenant_id == _TENANT


@pytest.mark.asyncio
async def test_low_confidence_returns_escalate() -> None:
    orch, _, _, _ = _make_orchestrator(eval_should_send=False, eval_score=0.45)
    result = await orch.handle_reply(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        message="Me interesa pero necesito más información.",
    )

    assert result.action == "escalate"
    assert result.draft == _DRAFT   # draft preserved so human can review
    assert result.confidence_score == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_full_pipeline_calls_all_stages() -> None:
    orch, classifier, conversationalist, evaluator = _make_orchestrator()
    await orch.handle_reply(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        message="¿Qué presupuesto maneja el plan básico?",
    )

    classifier.classify.assert_awaited_once()
    conversationalist.run.assert_awaited_once()
    evaluator.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluator_receives_intent_in_context() -> None:
    """Evaluator context string must include the detected intent."""
    orch, _, _, evaluator = _make_orchestrator(intent="objection_price")
    await orch.handle_reply(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        message="El precio es muy alto para nuestro presupuesto.",
    )

    eval_kwargs = evaluator.evaluate.call_args.kwargs
    assert "objection_price" in eval_kwargs["context"]
    assert eval_kwargs["conversation_id"] == _CONV_ID
    assert eval_kwargs["tenant_id"] == _TENANT
