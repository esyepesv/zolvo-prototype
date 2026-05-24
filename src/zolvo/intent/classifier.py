from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from zolvo.llm.base import LLMProviderError
from zolvo.llm.gateway import LLMGateway

log = structlog.get_logger(__name__)

IntentCategory = Literal[
    "interested",
    "objection_price",
    "objection_authority",
    "objection_timing",
    "meeting_intent",
    "complaint",
    "complex_technical",
    "out_of_scope",
    "opt_out",
]

_HANDOFF_INTENTS: frozenset[str] = frozenset(
    {"complaint", "complex_technical", "out_of_scope", "opt_out"}
)

_VALID_INTENTS: frozenset[str] = frozenset(
    {
        "interested",
        "objection_price",
        "objection_authority",
        "objection_timing",
        "meeting_intent",
        "complaint",
        "complex_technical",
        "out_of_scope",
        "opt_out",
    }
)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "intent_classifier.txt"


@dataclass(frozen=True)
class IntentResult:
    intent: IntentCategory
    should_handoff: bool
    confidence: float
    reason: str


class IntentClassificationError(Exception):
    """Raised when intent classification fails after retries."""


class IntentClassifier:
    """Classifies incoming prospect messages into one of 9 intent categories.

    Uses a cheap LLM model via LLMGateway (task_type='classification').
    """

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def classify(self, message: str, context: str = "") -> IntentResult:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(message=message, context=context or "Sin contexto previo.")

        try:
            response = await self._gateway.complete(
                task_type="classification",
                prompt=prompt,
                max_tokens=256,
                temperature=0.1,
            )
        except LLMProviderError as exc:
            raise IntentClassificationError(f"LLM call failed: {exc}") from exc

        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IntentClassificationError(
                f"LLM returned non-JSON intent response: {response.content!r}"
            ) from exc

        intent_raw: str = data.get("intent", "out_of_scope")
        if intent_raw not in _VALID_INTENTS:
            log.warning(
                "intent_classifier.unknown_intent",
                raw_intent=intent_raw,
                fallback="out_of_scope",
            )
            intent_raw = "out_of_scope"

        intent: IntentCategory = intent_raw  # type: ignore[assignment]
        should_handoff = intent in _HANDOFF_INTENTS
        confidence = float(data.get("confidence", 0.5))
        reason = str(data.get("reason", ""))

        log.info(
            "intent_classifier.classified",
            intent=intent,
            should_handoff=should_handoff,
            confidence=round(confidence, 3),
        )

        return IntentResult(
            intent=intent,
            should_handoff=should_handoff,
            confidence=confidence,
            reason=reason,
        )
