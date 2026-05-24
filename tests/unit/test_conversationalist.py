from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from zolvo.agents.conversationalist import ConversationalistAgent, ConversationalistResult
from zolvo.config import Settings
from zolvo.intent.classifier import IntentResult
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway
from zolvo.models.domain import AgentRun, MemoryMatch, Message

_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
_CONV_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
_RUN_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000001")

_DRAFT = (
    "Entiendo perfectamente tu situación. "
    "¿Cuál sería el impacto si lograran reducir la latencia a menos de 50ms?"
)


def _make_gateway(draft: str = _DRAFT) -> LLMGateway:
    fake = FakeLLMProvider(overrides={"generation_standard": draft})
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    return LLMGateway(settings, extra_providers={"openai": fake})


def _make_intent(intent: str = "interested", should_handoff: bool = False) -> IntentResult:
    return IntentResult(
        intent=intent,  # type: ignore[arg-type]
        should_handoff=should_handoff,
        confidence=0.92,
        reason="test",
    )


def _make_messages(n: int = 3) -> list[Message]:
    return [
        Message(
            tenant_id=_TENANT,
            conversation_id=_CONV_ID,
            direction="inbound" if i % 2 == 0 else "outbound",
            content=f"Mensaje {i} de la conversación",
        )
        for i in range(n)
    ]


def _make_memory_matches() -> list[MemoryMatch]:
    return [
        MemoryMatch(
            source="lead_embedding",
            source_id=uuid.uuid4(),
            text="Lead de fintech mexicana interesado en scoring crediticio",
            similarity=0.91,
        )
    ]


def _make_agent(
    draft: str = _DRAFT,
    short_term: list[Message] | None = None,
    long_term: list[MemoryMatch] | None = None,
) -> tuple[ConversationalistAgent, MagicMock, MagicMock]:
    gateway = _make_gateway(draft)

    memory_service = MagicMock()
    memory_service.get_short_term = AsyncMock(
        return_value=short_term if short_term is not None else _make_messages()
    )
    memory_service.get_long_term = AsyncMock(
        return_value=long_term if long_term is not None else _make_memory_matches()
    )

    agent_run_repo = MagicMock()
    agent_run_repo.create = AsyncMock(
        return_value=AgentRun(id=_RUN_ID, tenant_id=_TENANT, agent_name="conversationalist")
    )

    agent = ConversationalistAgent(gateway, memory_service, agent_run_repo)
    return agent, memory_service, agent_run_repo


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_conversationalist_returns_draft_for_interested() -> None:
    agent, _, _ = _make_agent()
    result = await agent.run(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        latest_message="Me parece interesante, ¿cómo funciona el scoring?",
        intent_result=_make_intent("interested"),
    )

    assert isinstance(result, ConversationalistResult)
    assert result.draft_message == _DRAFT
    assert result.intent_handled == "interested"
    assert result.conversation_id == _CONV_ID
    assert result.agent_run_id == _RUN_ID


@pytest.mark.asyncio
async def test_conversationalist_queries_both_memory_layers() -> None:
    agent, memory_service, _ = _make_agent()
    await agent.run(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        latest_message="Su precio es muy alto para nuestro presupuesto.",
        intent_result=_make_intent("objection_price"),
    )

    memory_service.get_short_term.assert_awaited_once_with(_CONV_ID, _TENANT)
    memory_service.get_long_term.assert_awaited_once()
    long_term_call = memory_service.get_long_term.call_args
    assert long_term_call.kwargs["tenant_id"] == _TENANT
    assert long_term_call.kwargs["top_k"] == 3


@pytest.mark.asyncio
async def test_conversationalist_records_agent_run_with_conversation_id() -> None:
    agent, _, agent_run_repo = _make_agent()
    await agent.run(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        latest_message="¿Pueden agendar una demo?",
        intent_result=_make_intent("meeting_intent"),
    )

    agent_run_repo.create.assert_awaited_once()
    kwargs = agent_run_repo.create.call_args.kwargs
    assert kwargs["agent_name"] == "conversationalist"
    assert kwargs["conversation_id"] == _CONV_ID
    assert kwargs["tenant_id"] == _TENANT
    assert kwargs["input_payload"]["intent"] == "meeting_intent"
    assert kwargs["output_payload"]["draft"] == _DRAFT
    assert kwargs["tokens_in"] > 0


@pytest.mark.asyncio
async def test_conversationalist_works_with_empty_memory() -> None:
    """Handles gracefully when there is no prior context in either memory layer."""
    agent, _, _ = _make_agent(short_term=[], long_term=[])
    result = await agent.run(
        conversation_id=_CONV_ID,
        tenant_id=_TENANT,
        latest_message="Primer contacto.",
        intent_result=_make_intent("interested"),
    )

    assert result.draft_message == _DRAFT


@pytest.mark.asyncio
async def test_conversationalist_covers_all_9_intents() -> None:
    """Smoke: all 9 intent categories produce a result without raising."""
    intents = [
        "interested", "objection_price", "objection_authority", "objection_timing",
        "meeting_intent", "complaint", "complex_technical", "out_of_scope", "opt_out",
    ]
    for intent in intents:
        agent, _, _ = _make_agent()
        result = await agent.run(
            conversation_id=_CONV_ID,
            tenant_id=_TENANT,
            latest_message="Mensaje de prueba",
            intent_result=_make_intent(intent),
        )
        assert result.intent_handled == intent, f"Failed for intent: {intent}"
