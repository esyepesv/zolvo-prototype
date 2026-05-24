from __future__ import annotations

from fastapi import APIRouter, Depends

from zolvo.agents.copywriter import CopywriterAgent
from zolvo.agents.researcher import ResearcherAgent
from zolvo.api.deps import get_conv_repo, get_copywriter, get_lead_repo, get_researcher
from zolvo.repositories.conversations import ConversationRepository
from zolvo.repositories.leads import LeadRepository
from zolvo.schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_lead(
    body: IngestRequest,
    lead_repo: LeadRepository = Depends(get_lead_repo),
    researcher: ResearcherAgent = Depends(get_researcher),
    copywriter: CopywriterAgent = Depends(get_copywriter),
    conv_repo: ConversationRepository = Depends(get_conv_repo),
) -> IngestResponse:
    """Create lead → enrich → embed → open conversation → generate outbound message."""
    lead = await lead_repo.create(
        tenant_id=body.tenant_id,
        full_name=body.full_name,
        email=body.email,
        linkedin_url=body.linkedin_url,
        company=body.company,
        role=body.role,
        source=body.source,
    )

    research_result = await researcher.run(lead_id=lead.id, tenant_id=body.tenant_id)

    conversation = await conv_repo.create(
        tenant_id=body.tenant_id,
        lead_id=lead.id,
        channel=body.channel,
    )

    copy_result = await copywriter.run(lead_id=lead.id, tenant_id=body.tenant_id)

    return IngestResponse(
        lead_id=lead.id,
        conversation_id=conversation.id,
        subject=copy_result.subject,
        body=copy_result.body,
        channel=copy_result.channel,
        researcher_run_id=research_result.agent_run_id,
        copywriter_run_id=copy_result.agent_run_id,
    )
