#!/usr/bin/env python3
"""
Demo: Zolvo AI Sales Engine — Happy Path End-to-End

Runs the full pipeline against a live FastAPI server at localhost:8000:
  1. POST /agents/ingest  — create lead + research + copywriter
  2. POST /events/reply   — 3 reply turns (interested → objection_price → meeting_intent)

Usage:
    # Terminal 1 — start API:
    PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --reload

    # Terminal 2 — run demo:
    PYTHONPATH=src .venv/bin/python demo/run_happy_path.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"

LEAD = {
    "tenant_id": TENANT_ID,
    "full_name": "Diego Ramírez",
    "email": "diego.ramirez@credimex.com.mx",
    "linkedin_url": "https://linkedin.com/in/diego-ramirez-cto",
    "company": "CredIMex",
    "role": "CTO",
    "source": "linkedin",
    "channel": "linkedin",
}

REPLY_TURNS = [
    {
        "label": "Turn 1 — Interés inicial",
        "message": (
            "Hola, me llegó tu mensaje. Estamos evaluando soluciones de scoring crediticio "
            "para nuestro producto de microcréditos. ¿Pueden agendar una llamada?"
        ),
    },
    {
        "label": "Turn 2 — Objeción de precio",
        "message": (
            "Suena interesante, pero el precio que mencionaste está fuera de nuestro "
            "presupuesto actual. Somos una startup de 30 personas, no una institución grande."
        ),
    },
    {
        "label": "Turn 3 — Intent de meeting",
        "message": (
            "Entiendo. ¿Pueden hacer una demo el jueves o viernes de esta semana? "
            "Quiero que lo vea también nuestro CEO."
        ),
    },
]


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"\n  [ERROR] HTTP {e.code}: {body[:400]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n  [ERROR] Cannot reach {BASE_URL}: {e.reason}")
        print("  Start the API: PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app")
        sys.exit(1)


def sep(title: str) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {title}")
    print("─" * 62)


def indent(text: str, w: int = 4) -> str:
    pad = " " * w
    return "\n".join(pad + line for line in text.splitlines())


def main() -> None:
    print("\n" + "=" * 62)
    print("  ZOLVO AI SALES ENGINE — DEMO END-TO-END")
    print("=" * 62)

    # ── Step 1: Ingest ───────────────────────────────────────────
    sep("STEP 1: Ingest Lead")
    print(f"  Lead : {LEAD['full_name']} — {LEAD['role']} @ {LEAD['company']}")

    t0 = time.monotonic()
    ingest = post("/agents/ingest", LEAD)
    elapsed = time.monotonic() - t0

    lead_id = ingest["lead_id"]
    conv_id = ingest["conversation_id"]
    print(f"  ✓ lead_id        : {lead_id}")
    print(f"  ✓ conversation_id: {conv_id}")
    print(f"  ✓ elapsed        : {elapsed:.1f}s")
    print(f"\n  Subject : {ingest['subject']}")
    print(f"\n  Body:\n{indent(ingest['body'])}")

    # ── Step 2: Reply turns ──────────────────────────────────────
    results: list[dict] = []
    for i, turn in enumerate(REPLY_TURNS):
        sep(f"STEP {i + 2}: {turn['label']}")
        print(f"  PROSPECT: {turn['message'][:90]}...")

        t0 = time.monotonic()
        reply = post("/events/reply", {
            "conversation_id": conv_id,
            "tenant_id": TENANT_ID,
            "message": turn["message"],
        })
        elapsed = time.monotonic() - t0

        results.append(reply)
        action = reply["action"]
        intent = reply["intent"]
        score = reply.get("confidence_score")
        icons = {"send": "✓ SEND", "handoff": "⚠ HANDOFF", "escalate": "↑ ESCALATE"}

        print(f"\n  Intent  : {intent}")
        score_str = f"{score:.3f}" if score is not None else "n/a"
        print(f"  Action  : {icons[action]}  (score: {score_str})  [{elapsed:.1f}s]")

        if reply.get("draft"):
            print(f"\n  Draft:\n{indent(reply['draft'])}")
        if action != "send":
            print(f"  Reason  : {reply.get('reason', '')}")

    # ── Summary ──────────────────────────────────────────────────
    sep("PIPELINE SUMMARY")
    print(f"  lead_id          : {lead_id}")
    print(f"  conversation_id  : {conv_id}")
    print(f"  Reply turns      : {len(results)}")

    intents = [r["intent"] for r in results]
    actions = [r["action"] for r in results]
    scores = [r["confidence_score"] for r in results if r.get("confidence_score") is not None]

    print(f"\n  Intent path      : {' → '.join(intents)}")
    print(f"  Action path      : {' → '.join(actions)}")
    if scores:
        print(f"  Avg conf score   : {sum(scores)/len(scores):.3f}")

    send_count = actions.count("send")
    escalate_count = actions.count("escalate")
    handoff_count = actions.count("handoff")
    print(f"\n  Sends            : {send_count}")
    print(f"  Escalations      : {escalate_count}")
    print(f"  Handoffs         : {handoff_count}")
    print(f"\n  Stages: ingest → classify → generate → evaluate → route  ✓")
    print("\n" + "=" * 62 + "\n")


if __name__ == "__main__":
    main()
