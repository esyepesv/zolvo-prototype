from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.agents.evaluator import EvaluationResult, EvaluatorAgent
from zolvo.config import Settings
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway
from zolvo.models.domain import AgentRun

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_CONV_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000002")
_RUN_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000002")

_GOOD_RESPONSE = json.dumps({
    "naturalidad": 0.90,
    "relevancia": 0.85,
    "riesgo": 0.05,
    "reason": "El mensaje es natural y relevante. No presenta riesgo.",
})

_BAD_RESPONSE = json.dumps({
    "naturalidad": 0.40,
    "relevancia": 0.35,
    "riesgo": 0.20,
    "reason": "El mensaje suena robótico y no responde bien al prospecto.",
})

_HIGH_RISK_RESPONSE = json.dumps({
    "naturalidad": 0.85,
    "relevancia": 0.80,
    "riesgo": 0.95,
    "reason": "El mensaje contiene promesas de ROI específicas y precios.",
})

_DRAFT = "Entiendo tu situación. ¿Tienes disponibilidad esta semana para una llamada de 20 minutos?"
_CONTEXT = "[PROSPECT]: Hola, me interesa el scoring crediticio.\n[AGENTE]: Con gusto te cuento."


def _make_gateway(fake_response: str = _GOOD_RESPONSE) -> LLMGateway:
    fake = FakeLLMProvider(overrides={"classification": fake_response})
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    return LLMGateway(settings, extra_providers={"openai": fake})


def _make_agent(
    fake_response: str = _GOOD_RESPONSE,
    threshold: float = 0.70,
) -> tuple[EvaluatorAgent, MagicMock]:
    gateway = _make_gateway(fake_response)
    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(
        return_value=AgentRun(id=_RUN_ID, tenant_id=_TENANT, agent_name="evaluator")
    )
    agent = EvaluatorAgent(gateway, agent_run_repo, threshold=threshold)
    return agent, agent_run_repo


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_good_draft_should_send() -> None:
    agent, _ = _make_agent(_GOOD_RESPONSE)
    result = await agent.evaluate(
        draft=_DRAFT, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    assert isinstance(result, EvaluationResult)
    assert result.should_send is True
    assert result.score >= 0.70
    assert result.agent_run_id == _RUN_ID


@pytest.mark.asyncio
async def test_bad_draft_blocked() -> None:
    agent, _ = _make_agent(_BAD_RESPONSE)
    result = await agent.evaluate(
        draft="Hola, espero que estes bien. Como te comenté somos la mejor solución.",
        context=_CONTEXT,
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
    )

    assert result.should_send is False
    assert result.score < 0.70


@pytest.mark.asyncio
async def test_high_risk_draft_blocked() -> None:
    """A draft that sounds natural and relevant but contains risky content is blocked."""
    agent, _ = _make_agent(_HIGH_RISK_RESPONSE)
    result = await agent.evaluate(
        draft="Te garantizamos un ROI de 300% en 6 meses por solo $50k USD.",
        context=_CONTEXT,
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
    )

    assert result.should_send is False
    assert result.breakdown["riesgo"] > 0.90


@pytest.mark.asyncio
async def test_breakdown_populated() -> None:
    agent, _ = _make_agent(_GOOD_RESPONSE)
    result = await agent.evaluate(
        draft=_DRAFT, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    assert set(result.breakdown.keys()) == {"naturalidad", "relevancia", "riesgo"}
    assert all(0.0 <= v <= 1.0 for v in result.breakdown.values())
    assert result.reason != ""


@pytest.mark.asyncio
async def test_records_agent_run() -> None:
    agent, agent_run_repo = _make_agent(_GOOD_RESPONSE)
    await agent.evaluate(
        draft=_DRAFT, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    agent_run_repo.create.assert_awaited_once()
    kwargs = agent_run_repo.create.call_args.kwargs
    assert kwargs["agent_name"] == "evaluator"
    assert kwargs["conversation_id"] == _CONV_ID
    assert kwargs["tenant_id"] == _TENANT
    assert "score" in kwargs["output_payload"]
    assert "should_send" in kwargs["output_payload"]
    assert kwargs["tokens_in"] > 0


@pytest.mark.asyncio
async def test_configurable_threshold_passes_mediocre_draft() -> None:
    """A low threshold allows borderline drafts through."""
    agent, _ = _make_agent(_BAD_RESPONSE, threshold=0.40)
    result = await agent.evaluate(
        draft=_DRAFT, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    assert result.should_send is True


# ─── Pre-filter (hard rules) tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prefilter_blocks_forbidden_promise() -> None:
    """Drafts with explicit guarantees are blocked before the LLM is called."""
    agent, agent_run_repo = _make_agent()
    result = await agent.evaluate(
        draft="Te garantizamos un ROI de 300% en 6 meses.",
        context=_CONTEXT,
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
    )

    assert result.should_send is False
    assert result.score == 0.0
    # LLM was NOT called — create called without tokens_in
    call_kwargs = agent_run_repo.create.call_args.kwargs
    assert "tokens_in" not in call_kwargs


@pytest.mark.asyncio
async def test_prefilter_blocks_excessive_length() -> None:
    """Drafts exceeding max character limit are blocked without LLM call."""
    agent, _ = _make_agent()
    long_draft = "Hola, " + ("esto es muy largo. " * 100)  # > 1500 chars
    result = await agent.evaluate(
        draft=long_draft, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    assert result.should_send is False
    assert result.score == 0.0
    assert "caracteres" in result.reason


@pytest.mark.asyncio
async def test_prefilter_allows_clean_draft() -> None:
    """A clean draft passes the pre-filter and reaches the LLM evaluator."""
    agent, agent_run_repo = _make_agent(_GOOD_RESPONSE)
    result = await agent.evaluate(
        draft=_DRAFT, context=_CONTEXT, conversation_id=_CONV_ID, tenant_id=_TENANT
    )

    assert result.should_send is True
    # LLM was called — tokens_in present in agent_run create call
    call_kwargs = agent_run_repo.create.call_args.kwargs
    assert call_kwargs.get("tokens_in", 0) > 0
