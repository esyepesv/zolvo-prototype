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

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "evaluator.txt"
_DEFAULT_THRESHOLD = 0.70


@dataclass(frozen=True)
class EvaluationResult:
    score: float
    breakdown: dict
    should_send: bool
    reason: str
    agent_run_id: uuid.UUID


class EvaluatorAgent(AgentBase):
    """Scores a draft message on naturalness, relevance, and risk before sending."""

    def __init__(
        self,
        gateway: LLMGateway,
        agent_run_repo: AgentRunRepository,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        super().__init__(gateway)
        self._agent_run_repo = agent_run_repo
        self._threshold = threshold

    @property
    def agent_name(self) -> str:
        return "evaluator"

    async def evaluate(
        self,
        *,
        draft: str,
        context: str,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> EvaluationResult:
        t0 = time.monotonic()

        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(draft=draft, context=context)

        response = await self._gateway.complete(
            task_type="classification",
            prompt=prompt,
            max_tokens=256,
            temperature=0.0,
        )

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        naturalidad = _clamp(float(data.get("naturalidad", 0.5)))
        relevancia = _clamp(float(data.get("relevancia", 0.5)))
        riesgo = _clamp(float(data.get("riesgo", 0.5)))
        reason = str(data.get("reason", "Evaluación completada."))

        score = (naturalidad + relevancia + (1.0 - riesgo)) / 3.0
        should_send = score >= self._threshold

        breakdown = {"naturalidad": naturalidad, "relevancia": relevancia, "riesgo": riesgo}
        latency_ms = int((time.monotonic() - t0) * 1000)

        agent_run = await self._agent_run_repo.create(
            tenant_id=tenant_id,
            agent_name=self.agent_name,
            conversation_id=conversation_id,
            input_payload={"draft_length": len(draft)},
            output_payload={
                "score": round(score, 4),
                "should_send": should_send,
                "breakdown": breakdown,
            },
            llm_provider=response.provider,
            llm_model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
            latency_ms=latency_ms,
        )

        log.info(
            "evaluator.completed",
            conversation_id=str(conversation_id),
            score=round(score, 4),
            should_send=should_send,
            latency_ms=latency_ms,
        )

        return EvaluationResult(
            score=score,
            breakdown=breakdown,
            should_send=should_send,
            reason=reason,
            agent_run_id=agent_run.id,
        )


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))
