from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from supabase import AsyncClient, acreate_client

from zolvo.agents.conversationalist import ConversationalistAgent
from zolvo.agents.copywriter import CopywriterAgent
from zolvo.agents.evaluator import EvaluatorAgent
from zolvo.agents.researcher import ResearcherAgent
from zolvo.channels.email_mock import EmailMockAdapter
from zolvo.channels.linkedin_mock import LinkedInMockAdapter
from zolvo.channels.slack_stub import SlackStub
from zolvo.config import get_settings
from zolvo.intent.classifier import IntentClassifier
from zolvo.llm.gateway import LLMGateway
from zolvo.memory.service import MemoryService
from zolvo.orchestrator.orchestrator import Orchestrator
from zolvo.repositories.agent_runs import AgentRunRepository
from zolvo.repositories.conversations import ConversationRepository
from zolvo.repositories.leads import LeadRepository
from zolvo.repositories.messages import MessageRepository


@lru_cache
def _get_client_args() -> tuple[str, str]:
    s = get_settings()
    return s.supabase_url, s.supabase_service_role_key


async def get_supabase() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI dependency that yields an async Supabase client (service role)."""
    url, key = _get_client_args()
    client: AsyncClient = await acreate_client(url, key)
    try:
        yield client
    finally:
        await client.auth.sign_out()


def get_gateway() -> LLMGateway:
    return LLMGateway(get_settings())


async def get_researcher(
    supabase: AsyncClient = Depends(get_supabase),
    gateway: LLMGateway = Depends(get_gateway),
) -> ResearcherAgent:
    return ResearcherAgent(gateway, LeadRepository(supabase), AgentRunRepository(supabase))


async def get_copywriter(
    supabase: AsyncClient = Depends(get_supabase),
    gateway: LLMGateway = Depends(get_gateway),
) -> CopywriterAgent:
    return CopywriterAgent(gateway, LeadRepository(supabase), AgentRunRepository(supabase))


async def get_lead_repo(supabase: AsyncClient = Depends(get_supabase)) -> LeadRepository:
    return LeadRepository(supabase)


async def get_conv_repo(supabase: AsyncClient = Depends(get_supabase)) -> ConversationRepository:
    return ConversationRepository(supabase)


async def get_message_repo(supabase: AsyncClient = Depends(get_supabase)) -> MessageRepository:
    return MessageRepository(supabase)


def get_linkedin_adapter() -> LinkedInMockAdapter:
    return LinkedInMockAdapter()


def get_email_adapter() -> EmailMockAdapter:
    return EmailMockAdapter()


def get_slack_stub() -> SlackStub:
    return SlackStub()


async def get_orchestrator(
    supabase: AsyncClient = Depends(get_supabase),
    gateway: LLMGateway = Depends(get_gateway),
) -> Orchestrator:
    settings = get_settings()
    agent_run_repo = AgentRunRepository(supabase)
    message_repo = MessageRepository(supabase)
    memory = MemoryService(message_repo, gateway, supabase)
    classifier = IntentClassifier(gateway)
    conversationalist = ConversationalistAgent(gateway, memory, agent_run_repo)
    evaluator = EvaluatorAgent(gateway, agent_run_repo, threshold=settings.confidence_threshold)
    conv_repo = ConversationRepository(supabase)
    return Orchestrator(classifier, conversationalist, evaluator, agent_run_repo, conv_repo)
