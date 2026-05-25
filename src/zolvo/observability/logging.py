from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from zolvo.config import Settings

# Maps internal structlog event keys → human-readable labels shown in dev/demo mode.
_EVENT_LABELS: dict[str, str] = {
    # ── Agents ────────────────────────────────────────────────────────────────
    "researcher.completed":             "RESEARCHER   ▸ Lead enriched",
    "copywriter.completed":             "COPYWRITER   ▸ Outbound message drafted",
    "conversationalist.completed":      "AGENT        ▸ Reply generated",
    "evaluator.completed":              "EVALUATOR    ▸ Draft evaluated",
    # ── Gates ─────────────────────────────────────────────────────────────────
    "intent_classifier.classified":     "GATE 1       ▸ Intent classified",
    "intent_classifier.unknown_intent": "GATE 1       ▸ Unknown intent — fallback to out_of_scope",
    "orchestrator.intent_classified":   "GATE 1       ▸ Routing decision",
    "orchestrator.evaluated":           "GATE 2       ▸ Confidence gate result",
    # ── Channels ──────────────────────────────────────────────────────────────
    "channel.linkedin.send":            "LINKEDIN     ▸ Message sent to prospect",
    "channel.email.send":               "EMAIL        ▸ Message sent to prospect",
    # ── Alerts ────────────────────────────────────────────────────────────────
    "slack.handoff_alert":              "HANDOFF  !!  ▸ Human rep required — Slack notified",
    "slack.escalation_alert":           "ESCALATE !!  ▸ Draft blocked — Slack notified",
    # ── LLM Gateway ───────────────────────────────────────────────────────────
    "llm.gateway.fallback":             "LLM          ▸ Provider fallback activated",
    "llm.gateway.circuit_bypass":       "LLM          ▸ Circuit breaker bypass",
    "llm.gateway.provider_failure":     "LLM          ▸ Provider failed",
    # ── Memory ────────────────────────────────────────────────────────────────
    "memory.short_term.loaded":         "MEMORY       ▸ Short-term context loaded",
    "memory.long_term.searched":        "MEMORY       ▸ Long-term semantic search",
    # ── Debounce ──────────────────────────────────────────────────────────────
    "debounce.waiting":                 "DEBOUNCE     ▸ Waiting before processing",
    "debounce.ready":                   "DEBOUNCE     ▸ Ready — processing reply",
}

# Key fields to surface inline after the label (only in dev mode).
_INLINE_FIELDS: dict[str, list[str]] = {
    "GATE 1       ▸ Intent classified":           ["intent", "should_handoff", "confidence"],
    "GATE 1       ▸ Routing decision":             ["intent", "should_handoff"],
    "GATE 2       ▸ Confidence gate result":       ["score", "should_send"],
    "RESEARCHER   ▸ Lead enriched":                ["icp_fit", "latency_ms"],
    "COPYWRITER   ▸ Outbound message drafted":     ["channel", "latency_ms"],
    "AGENT        ▸ Reply generated":              ["intent", "latency_ms"],
    "EVALUATOR    ▸ Draft evaluated":              ["score", "should_send"],
    "LLM          ▸ Provider fallback activated":  ["preferred", "using"],
    "HANDOFF  !!  ▸ Human rep required — Slack notified":  ["intent"],
    "ESCALATE !!  ▸ Draft blocked — Slack notified":       ["intent", "score"],
}


def _human_event_processor(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Replace internal event codes with readable labels in dev/demo mode."""
    raw_event: str = event_dict.get("event", "")
    label = _EVENT_LABELS.get(raw_event)
    if label is None:
        return event_dict

    inline = _INLINE_FIELDS.get(label, [])
    parts: list[str] = []
    for key in inline:
        val = event_dict.get(key)
        if val is not None:
            parts.append(f"{key}={val}")

    event_dict["event"] = f"{label}  {'  '.join(parts)}" if parts else label
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Set up structlog with JSON output in prod, human-readable console in dev/test."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
    ]

    if settings.env == "prod":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        extra_processors: list[structlog.types.Processor] = []
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
        extra_processors = [_human_event_processor]

    structlog.configure(
        processors=[
            *shared_processors,
            *extra_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)
