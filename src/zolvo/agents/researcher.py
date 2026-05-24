from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog

from zolvo.agents.base import AgentBase
from zolvo.llm.gateway import LLMGateway
from zolvo.repositories.agent_runs import AgentRunRepository
from zolvo.repositories.leads import LeadRepository

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "researcher.txt"


@dataclass(frozen=True)
class ResearchResult:
    lead_id: uuid.UUID
    enriched_data: dict
    embedding_saved: bool
    agent_run_id: uuid.UUID


class ResearcherAgent(AgentBase):
    """Enriches a lead profile and generates a semantic embedding for RAG retrieval."""

    def __init__(
        self,
        gateway: LLMGateway,
        lead_repo: LeadRepository,
        agent_run_repo: AgentRunRepository,
    ) -> None:
        super().__init__(gateway)
        self._lead_repo = lead_repo
        self._agent_run_repo = agent_run_repo

    @property
    def agent_name(self) -> str:
        return "researcher"

    async def run(self, *, lead_id: uuid.UUID, tenant_id: uuid.UUID) -> ResearchResult:
        lead = await self._lead_repo.get_by_id_and_tenant(lead_id, tenant_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found for tenant {tenant_id}")

        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(
            full_name=lead.full_name,
            company=lead.company or "desconocida",
            role=lead.role or "desconocido",
            email=lead.email or "no disponible",
            linkedin_url=lead.linkedin_url or "no disponible",
        )

        t0 = time.monotonic()
        response = await self._gateway.complete(
            task_type="generation_standard",
            prompt=prompt,
            max_tokens=512,
            temperature=0.3,
        )

        try:
            enriched: dict = json.loads(response.content)
        except json.JSONDecodeError:
            enriched = {"raw": response.content}

        embed_text = (
            f"{lead.full_name} {lead.company or ''} {lead.role or ''} "
            f"{enriched.get('summary', response.content)}"
        )
        embed_response = await self._gateway.embed(embed_text)

        await self._lead_repo.update_enriched_data(lead_id, enriched)
        await self._lead_repo.update_status(lead_id, "enriched")

        embedding_saved = False
        try:
            await self._lead_repo.save_embedding(
                lead_id=lead_id,
                tenant_id=tenant_id,
                vector=embed_response.vector,
                source_text=embed_text,
                model=embed_response.model,
            )
            embedding_saved = True
        except Exception as exc:
            log.warning("researcher.embed_save_failed", lead_id=str(lead_id), error=str(exc))

        latency_ms = int((time.monotonic() - t0) * 1000)
        agent_run = await self._agent_run_repo.create(
            tenant_id=tenant_id,
            agent_name=self.agent_name,
            input_payload={"lead_id": str(lead_id)},
            output_payload=enriched,
            llm_provider=response.provider,
            llm_model=response.model,
            tokens_in=response.tokens_in + embed_response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd + embed_response.cost_usd,
            latency_ms=latency_ms,
        )

        log.info(
            "researcher.completed",
            lead_id=str(lead_id),
            icp_fit=enriched.get("icp_fit"),
            embedding_saved=embedding_saved,
            cost_usd=round(response.cost_usd + embed_response.cost_usd, 6),
            latency_ms=latency_ms,
        )

        return ResearchResult(
            lead_id=lead_id,
            enriched_data=enriched,
            embedding_saved=embedding_saved,
            agent_run_id=agent_run.id,
        )
