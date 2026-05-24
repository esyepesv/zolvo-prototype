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

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "copywriter.txt"

_FALLBACK_ENRICHED: dict = {
    "icp_fit": "desconocido",
    "icp_reason": "sin analizar",
    "pain_points": [],
    "conversation_hooks": [],
    "estimated_company_size": "desconocido",
    "industry_vertical": "otro",
}


@dataclass(frozen=True)
class CopywriterResult:
    lead_id: uuid.UUID
    subject: str
    body: str
    channel: str
    agent_run_id: uuid.UUID


class CopywriterAgent(AgentBase):
    """Generates the first outbound message for a lead using their enriched profile."""

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
        return "copywriter"

    async def run(self, *, lead_id: uuid.UUID, tenant_id: uuid.UUID) -> CopywriterResult:
        lead = await self._lead_repo.get_by_id_and_tenant(lead_id, tenant_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found for tenant {tenant_id}")

        enriched = lead.enriched_data or _FALLBACK_ENRICHED

        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(
            full_name=lead.full_name,
            company=lead.company or "su empresa",
            role=lead.role or "su área",
            icp_fit=enriched.get("icp_fit", "desconocido"),
            icp_reason=enriched.get("icp_reason", "sin analizar"),
            pain_points=", ".join(enriched.get("pain_points", [])) or "no identificados",
            conversation_hooks=(
                ", ".join(enriched.get("conversation_hooks", [])) or "no identificados"
            ),
            estimated_company_size=enriched.get("estimated_company_size", "desconocido"),
            industry_vertical=enriched.get("industry_vertical", "otro"),
        )

        t0 = time.monotonic()
        response = await self._gateway.complete(
            task_type="generation_standard",
            prompt=prompt,
            max_tokens=768,
            temperature=0.7,
        )

        try:
            draft: dict = json.loads(response.content)
            subject = draft.get("subject", "")
            body = draft.get("body", response.content)
            channel = draft.get("channel", "email")
        except json.JSONDecodeError:
            subject = ""
            body = response.content
            channel = "email"

        latency_ms = int((time.monotonic() - t0) * 1000)
        agent_run = await self._agent_run_repo.create(
            tenant_id=tenant_id,
            agent_name=self.agent_name,
            input_payload={"lead_id": str(lead_id)},
            output_payload={"subject": subject, "body": body, "channel": channel},
            llm_provider=response.provider,
            llm_model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
            latency_ms=latency_ms,
        )

        log.info(
            "copywriter.completed",
            lead_id=str(lead_id),
            channel=channel,
            subject=subject,
            cost_usd=round(response.cost_usd, 6),
            latency_ms=latency_ms,
        )

        return CopywriterResult(
            lead_id=lead_id,
            subject=subject,
            body=body,
            channel=channel,
            agent_run_id=agent_run.id,
        )
