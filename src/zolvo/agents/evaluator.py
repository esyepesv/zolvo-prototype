from __future__ import annotations

import json
import re
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
_MAX_DRAFT_CHARS = 1500
_MAX_CAPS_RATIO = 0.40

# Patterns that guarantee rejection regardless of LLM score.
# Uses stem matching (garantiz\w*) to catch all conjugations.
_FORBIDDEN_PATTERNS = re.compile(
    r"\b(garantiz\w+|asegurar\w*\s+que|100\s*%\s*(seguro|garantizado)|"
    r"sin\s*(ningún\s*)?costo|completamente\s*gratis|gratis\s*total|"
    r"promet\w+)\b",
    re.IGNORECASE,
)


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

        # Deterministic pre-filter — blocks obviously bad drafts before spending tokens.
        rule_violation = _check_hard_rules(draft)
        if rule_violation:
            rule_name, rule_reason = rule_violation
            log.warning(
                "evaluator.hard_rule_blocked",
                conversation_id=str(conversation_id),
                rule=rule_name,
            )
            agent_run = await self._agent_run_repo.create(
                tenant_id=tenant_id,
                agent_name=self.agent_name,
                conversation_id=conversation_id,
                input_payload={"draft_length": len(draft)},
                output_payload={"score": 0.0, "should_send": False, "rule_violation": rule_name},
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return EvaluationResult(
                score=0.0,
                breakdown={"naturalidad": 0.0, "relevancia": 0.0, "riesgo": 1.0},
                should_send=False,
                reason=f"Bloqueado por regla: {rule_reason}",
                agent_run_id=agent_run.id,
            )

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


def _check_hard_rules(draft: str) -> tuple[str, str] | None:
    """Return (rule_name, human_reason) if the draft violates a hard rule, else None."""
    if len(draft) > _MAX_DRAFT_CHARS:
        return ("draft_too_long", f"El mensaje supera {_MAX_DRAFT_CHARS} caracteres.")

    if _FORBIDDEN_PATTERNS.search(draft):
        match = _FORBIDDEN_PATTERNS.search(draft)
        return ("forbidden_promise", f"Contiene promesa prohibida: '{match.group()}'.")

    words = [w for w in draft.split() if w.isalpha()]
    if words:
        caps_ratio = sum(1 for w in words if w.isupper()) / len(words)
        if caps_ratio > _MAX_CAPS_RATIO:
            return ("excessive_caps", f"Ratio de mayúsculas {caps_ratio:.0%} supera el umbral.")

    return None
