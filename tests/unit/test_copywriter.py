from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.agents.copywriter import CopywriterAgent, CopywriterResult
from zolvo.config import Settings
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway
from zolvo.models.domain import AgentRun, Lead

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_LEAD_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
_RUN_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")

_DRAFT_JSON = json.dumps(
    {
        "subject": "¿Cómo está escalando Kueski su equipo comercial?",
        "body": "Hola Carlos,\n\nVi que Kueski está expandiéndose a PYMES...",
        "channel": "email",
        "tone_notes": "Tono cercano apalancando el hook de expansión a PYMES.",
    }
)


def _make_enriched_lead() -> Lead:
    return Lead(
        id=_LEAD_ID,
        tenant_id=_TENANT,
        full_name="Carlos Mendoza",
        company="Kueski",
        role="CTO",
        email="carlos@kueski.com",
        source="linkedin",
        enriched_data={
            "icp_fit": "alto",
            "icp_reason": "Fintech mexicana de crédito con necesidad de scoring.",
            "pain_points": ["latencia en scoring", "costo de bureau"],
            "conversation_hooks": ["expansión a PYMES", "modelo de riesgo propio"],
            "estimated_company_size": "mediana",
            "industry_vertical": "crédito",
        },
    )


def _make_unenriched_lead() -> Lead:
    return Lead(
        id=_LEAD_ID,
        tenant_id=_TENANT,
        full_name="Ana Torres",
        company="Konfío",
        role="VP Ventas",
        source="manual",
    )


def _make_agent_run() -> AgentRun:
    return AgentRun(id=_RUN_ID, tenant_id=_TENANT, agent_name="copywriter")


def _make_gateway(draft_response: str) -> LLMGateway:
    fake = FakeLLMProvider(overrides={"generation_standard": draft_response})
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    return LLMGateway(settings, extra_providers={"openai": fake})


@pytest.mark.asyncio
async def test_copywriter_returns_structured_result() -> None:
    gateway = _make_gateway(_DRAFT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_enriched_lead())

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = CopywriterAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    assert isinstance(result, CopywriterResult)
    assert result.lead_id == _LEAD_ID
    assert result.subject == "¿Cómo está escalando Kueski su equipo comercial?"
    assert "Carlos" in result.body
    assert result.channel == "email"
    assert result.agent_run_id == _RUN_ID


@pytest.mark.asyncio
async def test_copywriter_records_agent_run() -> None:
    gateway = _make_gateway(_DRAFT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_enriched_lead())

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = CopywriterAgent(gateway, lead_repo, agent_run_repo)
    await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    agent_run_repo.create.assert_awaited_once()
    kwargs = agent_run_repo.create.call_args.kwargs
    assert kwargs["agent_name"] == "copywriter"
    assert kwargs["tenant_id"] == _TENANT
    assert kwargs["output_payload"]["channel"] == "email"
    assert kwargs["tokens_in"] > 0


@pytest.mark.asyncio
async def test_copywriter_works_without_enriched_data() -> None:
    """Uses fallback values when lead.enriched_data is None."""
    gateway = _make_gateway(_DRAFT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_unenriched_lead())

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = CopywriterAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    assert result.body != ""
    assert result.channel == "email"


@pytest.mark.asyncio
async def test_copywriter_handles_non_json_response() -> None:
    """Falls back gracefully when LLM returns plain text instead of JSON."""
    raw_message = "Hola Carlos, te escribo porque creo que podemos ayudarte en Kueski."
    gateway = _make_gateway(raw_message)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_enriched_lead())

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = CopywriterAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    assert result.body == raw_message
    assert result.subject == ""
    assert result.channel == "email"


@pytest.mark.asyncio
async def test_copywriter_raises_when_lead_not_found() -> None:
    gateway = _make_gateway(_DRAFT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=None)

    agent_run_repo = MagicMock()

    agent = CopywriterAgent(gateway, lead_repo, agent_run_repo)
    with pytest.raises(ValueError, match="not found"):
        await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)
