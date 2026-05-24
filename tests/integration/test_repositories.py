"""Integration tests for repository layer against real Supabase.

Skipped automatically when SUPABASE_URL is not configured.
Run with: pytest tests/integration/ -v
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from supabase import AsyncClient, acreate_client

from zolvo.config import get_settings
from zolvo.repositories.agent_runs import AgentRunRepository
from zolvo.repositories.conversations import ConversationRepository
from zolvo.repositories.leads import LeadRepository
from zolvo.repositories.messages import MessageRepository

DEMO_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _is_configured() -> bool:
    return bool(get_settings().supabase_url and get_settings().supabase_service_role_key)


pytestmark = pytest.mark.skipif(
    not _is_configured(),
    reason="SUPABASE_URL/KEY not configured — skipping integration tests",
)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    s = get_settings()
    return await acreate_client(s.supabase_url, s.supabase_service_role_key)


@pytest.mark.asyncio
async def test_lead_create_and_read(client: AsyncClient):
    repo = LeadRepository(client)

    lead = await repo.create(
        tenant_id=DEMO_TENANT,
        full_name="Ana García",
        email="ana@konfio.mx",
        company="Konfío",
        role="CFO",
        source="csv_import",
    )

    assert lead.id is not None
    assert lead.full_name == "Ana García"
    assert lead.status == "researching"

    fetched = await repo.get_by_id(lead.id)
    assert fetched is not None
    assert fetched.email == "ana@konfio.mx"
    assert fetched.company == "Konfío"


@pytest.mark.asyncio
async def test_conversation_create_and_read(client: AsyncClient):
    lead_repo = LeadRepository(client)
    conv_repo = ConversationRepository(client)

    lead = await lead_repo.create(
        tenant_id=DEMO_TENANT,
        full_name="Carlos Mendoza",
        company="Klar",
    )

    conv = await conv_repo.create(
        tenant_id=DEMO_TENANT,
        lead_id=lead.id,
        channel="linkedin",
    )

    assert conv.id is not None
    assert conv.status == "researching"

    convs = await conv_repo.get_by_lead_id(DEMO_TENANT, lead.id)
    assert len(convs) >= 1
    assert convs[0].lead_id == lead.id


@pytest.mark.asyncio
async def test_message_create_and_read(client: AsyncClient):
    lead_repo = LeadRepository(client)
    conv_repo = ConversationRepository(client)
    msg_repo = MessageRepository(client)

    lead = await lead_repo.create(tenant_id=DEMO_TENANT, full_name="Test Lead Msg")
    conv = await conv_repo.create(tenant_id=DEMO_TENANT, lead_id=lead.id)

    msg = await msg_repo.create(
        tenant_id=DEMO_TENANT,
        conversation_id=conv.id,
        direction="outbound",
        content="Hola Carlos, ¿tienes 15 minutos esta semana?",
        generated_by_agent="copywriter",
    )

    assert msg.id is not None
    assert msg.direction == "outbound"

    messages = await msg_repo.get_by_conversation_id(DEMO_TENANT, conv.id)
    assert len(messages) >= 1
    assert messages[0].content == "Hola Carlos, ¿tienes 15 minutos esta semana?"


@pytest.mark.asyncio
async def test_agent_run_create(client: AsyncClient):
    lead_repo = LeadRepository(client)
    run_repo = AgentRunRepository(client)
    conv_repo = ConversationRepository(client)

    lead = await lead_repo.create(tenant_id=DEMO_TENANT, full_name="Test Lead Run")
    conv = await conv_repo.create(tenant_id=DEMO_TENANT, lead_id=lead.id)

    run = await run_repo.create(
        tenant_id=DEMO_TENANT,
        agent_name="copywriter",
        conversation_id=conv.id,
        llm_provider="openrouter",
        llm_model="openai/gpt-4o-mini",
        tokens_in=150,
        tokens_out=80,
        latency_ms=1200,
    )

    assert run.id is not None
    assert run.agent_name == "copywriter"
    assert run.tokens_in == 150


@pytest.mark.asyncio
async def test_rls_cross_tenant_isolation(client: AsyncClient):
    """Lead created for DEMO_TENANT must not be visible when filtering by OTHER_TENANT."""
    repo = LeadRepository(client)

    lead = await repo.create(
        tenant_id=DEMO_TENANT,
        full_name="RLS Test Lead",
        company="SecretCo",
    )

    # Query with wrong tenant_id filter — should return None
    fetched = await repo.get_by_id_and_tenant(lead.id, OTHER_TENANT)
    assert fetched is None, "Cross-tenant filter should return no result"
