from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.config import Settings
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway
from zolvo.memory.service import MemoryService
from zolvo.models.domain import MemoryMatch, Message

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_CONV_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")


def _make_messages(n: int) -> list[Message]:
    """Generate *n* synthetic messages alternating inbound/outbound."""
    msgs: list[Message] = []
    for i in range(n):
        msgs.append(
            Message(
                tenant_id=_TENANT,
                conversation_id=_CONV_ID,
                direction="inbound" if i % 2 == 0 else "outbound",
                content=f"Mensaje de prueba {i}",
            )
        )
    return msgs


def _make_gateway(summary_response: str = "Resumen de prueba.") -> LLMGateway:
    fake = FakeLLMProvider(overrides={"generation_standard": summary_response})
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    return LLMGateway(settings, extra_providers={"openai": fake})


def _make_service(
    messages: list[Message] | None = None,
    lead_rpc_rows: list[dict] | None = None,
    summary_rpc_rows: list[dict] | None = None,
    gateway: LLMGateway | None = None,
) -> MemoryService:
    """Build a MemoryService with mocked dependencies."""
    message_repo = MagicMock()
    message_repo.get_by_conversation_id = AsyncMock(
        return_value=messages if messages is not None else []
    )

    gw = gateway or _make_gateway()

    # Mock supabase client with .rpc() and .table()
    client = MagicMock()

    async def fake_rpc_execute(fn_name: str, params: dict) -> MagicMock:
        result = MagicMock()
        if fn_name == "match_lead_embeddings":
            result.data = lead_rpc_rows or []
        elif fn_name == "match_conversation_summaries":
            result.data = summary_rpc_rows or []
        else:
            result.data = []
        return result

    # client.rpc("name", params).execute() pattern
    def rpc_side_effect(fn_name: str, params: dict) -> MagicMock:
        chain = MagicMock()
        chain.execute = AsyncMock(side_effect=lambda: fake_rpc_execute(fn_name, params))

        async def _exec():
            return await fake_rpc_execute(fn_name, params)

        chain.execute = AsyncMock(side_effect=_exec)
        return chain

    client.rpc = MagicMock(side_effect=rpc_side_effect)

    # client.table("x").upsert(...).execute() for summarize_and_index
    upsert_execute = AsyncMock(return_value=MagicMock(data=[{}]))
    upsert_chain = MagicMock()
    upsert_chain.execute = upsert_execute
    table_mock = MagicMock()
    table_mock.upsert = MagicMock(return_value=upsert_chain)
    client.table = MagicMock(return_value=table_mock)

    return MemoryService(message_repo, gw, client)


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_short_term_returns_recent_messages() -> None:
    messages = _make_messages(5)
    svc = _make_service(messages=messages)

    result = await svc.get_short_term(_CONV_ID, _TENANT, n=15)

    assert len(result) == 5
    assert all(isinstance(m, Message) for m in result)
    svc._message_repo.get_by_conversation_id.assert_awaited_once_with(_TENANT, _CONV_ID, limit=15)


@pytest.mark.asyncio
async def test_get_short_term_empty_conversation() -> None:
    svc = _make_service(messages=[])

    result = await svc.get_short_term(_CONV_ID, _TENANT)

    assert result == []


@pytest.mark.asyncio
async def test_get_long_term_combines_both_sources() -> None:
    lead_rows = [
        {
            "id": str(uuid.uuid4()),
            "lead_id": str(uuid.uuid4()),
            "source_text": "Lead de fintech mexicana",
            "similarity": 0.92,
        },
    ]
    summary_rows = [
        {
            "id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "summary_text": "Conversación sobre precios",
            "outcome": "scheduled",
            "similarity": 0.88,
        },
    ]
    svc = _make_service(lead_rpc_rows=lead_rows, summary_rpc_rows=summary_rows)

    query_vec = [0.1] * 1536
    result = await svc.get_long_term(query_vec, _TENANT, top_k=5)

    assert len(result) == 2
    assert all(isinstance(m, MemoryMatch) for m in result)
    # Sorted by similarity descending
    assert result[0].similarity >= result[1].similarity
    sources = {m.source for m in result}
    assert sources == {"lead_embedding", "conversation_summary"}


@pytest.mark.asyncio
async def test_get_long_term_no_results() -> None:
    svc = _make_service(lead_rpc_rows=[], summary_rpc_rows=[])

    result = await svc.get_long_term([0.0] * 1536, _TENANT)

    assert result == []


@pytest.mark.asyncio
async def test_summarize_and_index_generates_summary_and_embedding() -> None:
    messages = _make_messages(4)
    summary_text = "Resumen denso de la conversación de ventas."
    gateway = _make_gateway(summary_response=summary_text)
    svc = _make_service(messages=messages, gateway=gateway)

    await svc.summarize_and_index(_CONV_ID, _TENANT)

    # Verify LLM was called (indirectly, via gateway — the fake always returns)
    # Verify upsert was called on conversation_summaries_embeddings
    svc._client.table.assert_called_with("conversation_summaries_embeddings")
    upsert_call = svc._client.table.return_value.upsert
    upsert_call.assert_called_once()
    upsert_args = upsert_call.call_args
    data = upsert_args[0][0]
    assert data["conversation_id"] == str(_CONV_ID)
    assert data["tenant_id"] == str(_TENANT)
    assert data["summary_text"] == summary_text
    assert "embedding" in data
    assert len(data["embedding"]) == 1536
