from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.agents.researcher import ResearcherAgent, ResearchResult
from zolvo.config import Settings
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway
from zolvo.models.domain import AgentRun, Lead

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_LEAD_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_RUN_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")

_ENRICHMENT_JSON = json.dumps(
    {
        "summary": "Carlos es CTO de Kueski, relevante para la venta de soluciones de scoring.",
        "icp_fit": "alto",
        "icp_reason": "Fintech mexicana con necesidad de infraestructura crediticia.",
        "pain_points": ["latencia en scoring", "costo de bureau", "fraude en onboarding"],
        "conversation_hooks": ["modelo de riesgo propio", "expansión a PYMES"],
        "decision_maker": True,
        "estimated_company_size": "mediana",
        "industry_vertical": "crédito",
    }
)


def _make_lead() -> Lead:
    return Lead(
        id=_LEAD_ID,
        tenant_id=_TENANT,
        full_name="Carlos Mendoza",
        company="Kueski",
        role="CTO",
        email="carlos@kueski.com",
        source="linkedin",
    )


def _make_agent_run() -> AgentRun:
    return AgentRun(
        id=_RUN_ID,
        tenant_id=_TENANT,
        agent_name="researcher",
    )


def _make_gateway(enrichment_response: str) -> LLMGateway:
    fake = FakeLLMProvider(overrides={"generation_standard": enrichment_response})
    # Clear all real provider keys so only the injected fake is used.
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    # inject fake as "openai" so both complete() and embed() resolve to it
    return LLMGateway(settings, extra_providers={"openai": fake})


@pytest.mark.asyncio
async def test_researcher_enriches_lead_and_returns_result() -> None:
    gateway = _make_gateway(_ENRICHMENT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_lead())
    lead_repo.update_enriched_data = AsyncMock()
    lead_repo.update_status = AsyncMock()
    lead_repo.save_embedding = AsyncMock()

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = ResearcherAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    assert isinstance(result, ResearchResult)
    assert result.lead_id == _LEAD_ID
    assert result.enriched_data["icp_fit"] == "alto"
    assert result.enriched_data["industry_vertical"] == "crédito"
    assert result.agent_run_id == _RUN_ID


@pytest.mark.asyncio
async def test_researcher_persists_enriched_data_and_status() -> None:
    gateway = _make_gateway(_ENRICHMENT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_lead())
    lead_repo.update_enriched_data = AsyncMock()
    lead_repo.update_status = AsyncMock()
    lead_repo.save_embedding = AsyncMock()

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = ResearcherAgent(gateway, lead_repo, agent_run_repo)
    await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    lead_repo.update_enriched_data.assert_awaited_once()
    call_args = lead_repo.update_enriched_data.call_args
    assert call_args.args[0] == _LEAD_ID
    assert call_args.args[1]["icp_fit"] == "alto"

    lead_repo.update_status.assert_awaited_once_with(_LEAD_ID, "enriched")


@pytest.mark.asyncio
async def test_researcher_records_agent_run_with_costs() -> None:
    gateway = _make_gateway(_ENRICHMENT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_lead())
    lead_repo.update_enriched_data = AsyncMock()
    lead_repo.update_status = AsyncMock()
    lead_repo.save_embedding = AsyncMock()

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = ResearcherAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    agent_run_repo.create.assert_awaited_once()
    kwargs = agent_run_repo.create.call_args.kwargs
    assert kwargs["tenant_id"] == _TENANT
    assert kwargs["agent_name"] == "researcher"
    assert kwargs["llm_provider"] == "fake"
    assert kwargs["tokens_in"] > 0
    assert kwargs["cost_usd"] == 0.0
    assert result.embedding_saved is True


@pytest.mark.asyncio
async def test_researcher_raises_when_lead_not_found() -> None:
    gateway = _make_gateway(_ENRICHMENT_JSON)

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=None)

    agent_run_repo = MagicMock()

    agent = ResearcherAgent(gateway, lead_repo, agent_run_repo)
    with pytest.raises(ValueError, match="not found"):
        await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)


@pytest.mark.asyncio
async def test_researcher_handles_non_json_llm_response() -> None:
    gateway = _make_gateway("No pude generar un JSON válido en este momento.")

    lead_repo = MagicMock()
    lead_repo.get_by_id_and_tenant = AsyncMock(return_value=_make_lead())
    lead_repo.update_enriched_data = AsyncMock()
    lead_repo.update_status = AsyncMock()
    lead_repo.save_embedding = AsyncMock()

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(return_value=_make_agent_run())

    agent = ResearcherAgent(gateway, lead_repo, agent_run_repo)
    result = await agent.run(lead_id=_LEAD_ID, tenant_id=_TENANT)

    assert "raw" in result.enriched_data
    assert result.enriched_data["raw"].startswith("No pude")
