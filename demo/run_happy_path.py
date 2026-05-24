#!/usr/bin/env python3
"""
Demo: Zolvo AI Sales Engine — Happy Path End-to-End

Runs the full pipeline against a live FastAPI server at localhost:8000:
  1. POST /agents/ingest  — create lead + research + copywriter
  2. POST /events/reply   — 3 reply turns (interested → objection_price → meeting_intent)
  3. GET  /operator/dashboard — operator state after the run

Usage:
    # Terminal 1 — start API (watch for channel/Slack logs here):
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

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

BASE_URL = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"

console = Console()

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

_ACTION_STYLE: dict[str, tuple[str, str]] = {
    "send":     ("✓ SEND",     "bold green"),
    "handoff":  ("⚠ HANDOFF",  "bold yellow"),
    "escalate": ("↑ ESCALATE", "bold red"),
}


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
        console.print(f"\n[bold red]ERROR[/] HTTP {e.code}: {body[:400]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        console.print(f"\n[bold red]ERROR[/] Cannot reach {BASE_URL}: {e.reason}")
        console.print(
            "  [dim]Start the API: PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app[/dim]"
        )
        sys.exit(1)


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def main() -> None:
    # ── Header ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel.fit(
        "[bold cyan]ZOLVO AI SALES ENGINE[/bold cyan]\n"
        "[dim]Demo End-to-End · Happy Path · Fintech B2B México[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print(
        "  [dim]Terminal 1 shows live API logs: researcher, intent, evaluator, "
        "channel.linkedin.send, slack alerts[/dim]\n"
    )

    # ── Step 1: Ingest ───────────────────────────────────────────────────────
    console.rule("[bold]STEP 1 — Ingest Lead[/bold]")
    console.print(
        f"\n  Lead : [bold white]{LEAD['full_name']}[/bold white]"
        f" — {LEAD['role']} @ [cyan]{LEAD['company']}[/cyan]"
        f"  [dim]({LEAD['email']})[/dim]\n"
    )

    t0 = time.monotonic()
    with console.status("[dim]Researcher enriching lead + Copywriter drafting outbound...[/dim]"):
        ingest = post("/agents/ingest", LEAD)
    elapsed = time.monotonic() - t0

    lead_id = ingest["lead_id"]
    conv_id = ingest["conversation_id"]

    console.print(f"  [green]✓[/green] lead_id          [dim]{lead_id}[/dim]")
    console.print(f"  [green]✓[/green] conversation_id  [dim]{conv_id}[/dim]")
    console.print(f"  [green]✓[/green] elapsed          {elapsed:.1f}s\n")

    console.print(Panel(
        f"[bold]Subject:[/bold] {ingest['subject']}\n\n{ingest['body']}",
        title="[bold green]  Outbound Message  [/bold green]",
        border_style="green",
        padding=(1, 2),
    ))

    # ── Reply turns ──────────────────────────────────────────────────────────
    results: list[dict] = []
    # Track the full conversation for the prospect view
    prospect_thread: list[dict] = [
        {"from": "agent", "text": f"Subject: {ingest['subject']}\n\n{ingest['body']}"},
    ]

    for i, turn in enumerate(REPLY_TURNS):
        console.print()
        console.rule(f"[bold]STEP {i + 2} — {turn['label']}[/bold]")
        console.print()
        console.print(Panel(
            turn["message"],
            title="[bold blue]  PROSPECT  [/bold blue]",
            border_style="blue",
            padding=(0, 2),
        ))
        prospect_thread.append({"from": "prospect", "text": turn["message"]})

        t0 = time.monotonic()
        with console.status(
            "[dim]Gate 1: classifying intent… Gate 2: evaluating draft…[/dim]"
        ):
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
        label, style = _ACTION_STYLE.get(action, (action.upper(), "white"))
        score_str = f"{score:.3f}" if score is not None else "n/a"

        console.print(
            f"\n  Intent  [cyan]{intent}[/cyan]\n"
            f"  Action  [{style}]{label}[/]   "
            f"score [bold]{score_str}[/bold]   [{elapsed:.1f}s]\n"
        )

        if action == "send" and reply.get("draft"):
            console.print(Panel(
                reply["draft"],
                title="[bold green]  Agent Reply  — enviado vía LinkedIn[/bold green]",
                border_style="green",
                padding=(0, 2),
            ))
            prospect_thread.append({"from": "agent", "text": reply["draft"]})
        elif action == "escalate" and reply.get("draft"):
            console.print(Panel(
                reply["draft"],
                title="[bold red]  Draft bloqueado — pendiente revisión del Operador  [/bold red]",
                border_style="red",
                padding=(0, 2),
            ))
            console.print(
                "  [dim red]→ Slack alert enviado al Sales Rep "
                "(ver Terminal 1: slack.escalation_alert)[/dim red]\n"
            )
            prospect_thread.append({"from": "pending", "text": reply["draft"]})
        elif action == "handoff":
            console.print(
                "  [yellow]→ Handoff al Sales Rep "
                "(ver Terminal 1: slack.handoff_alert)[/yellow]\n"
            )
            if reply.get("reason"):
                console.print(f"  [yellow]Reason:[/yellow] {reply['reason']}\n")
            prospect_thread.append({"from": "handoff", "text": ""})

    # ── Pipeline Summary ─────────────────────────────────────────────────────
    console.print()
    console.rule("[bold]PIPELINE SUMMARY[/bold]")
    console.print()

    intents = [r["intent"] for r in results]
    actions = [r["action"] for r in results]
    scores = [r["confidence_score"] for r in results if r.get("confidence_score") is not None]

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("Turn",   style="dim",    width=6,  justify="center")
    table.add_column("Intent", style="cyan",   min_width=20)
    table.add_column("Action", justify="center", min_width=12)
    table.add_column("Score",  justify="right", min_width=7)
    table.add_column("Gate 1", justify="center", min_width=10)
    table.add_column("Gate 2", justify="center", min_width=10)

    for i, r in enumerate(results):
        act = r["action"]
        lbl, sty = _ACTION_STYLE.get(act, (act.upper(), "white"))
        sc = r.get("confidence_score")
        sc_str = f"{sc:.3f}" if sc is not None else "n/a"
        gate1 = "[green]PASS[/green]" if act != "handoff" else "[yellow]HANDOFF[/yellow]"
        gate2 = (
            "[green]PASS[/green]" if act == "send"
            else "[red]BLOCK[/red]" if act == "escalate"
            else "[dim]—[/dim]"
        )
        table.add_row(str(i + 1), r["intent"], f"[{sty}]{lbl}[/]", sc_str, gate1, gate2)

    console.print(table)
    console.print()

    avg_score = sum(scores) / len(scores) if scores else 0
    send_count  = actions.count("send")
    esc_count   = actions.count("escalate")
    hand_count  = actions.count("handoff")

    console.print(f"  Intent path       [cyan]{' → '.join(intents)}[/cyan]")
    console.print(f"  Avg conf score    [bold]{avg_score:.3f}[/bold]")
    console.print(
        f"  Sends / Escalations / Handoffs   "
        f"[green]{send_count}[/green] / [red]{esc_count}[/red] / [yellow]{hand_count}[/yellow]"
    )

    # ── Prospect view — LinkedIn inbox simulation ─────────────────────────────
    console.print()
    console.rule("[bold]VISTA DEL PROSPECTO — LinkedIn Inbox[/bold]")
    console.print(
        "\n  [dim]Lo que Diego Ramírez ve en su bandeja de LinkedIn[/dim]\n"
    )

    for msg in prospect_thread:
        src = msg["from"]
        text = msg["text"]

        if src == "agent":
            console.print(Panel(
                text,
                title="[bold white]  Sales Rep @ Zolvo  [/bold white]  [dim]← recibido[/dim]",
                border_style="white",
                padding=(0, 2),
            ))
        elif src == "prospect":
            console.print(Panel(
                text,
                title=f"[bold blue]  {LEAD['full_name']}  [/bold blue]  [dim]→ enviado[/dim]",
                border_style="blue",
                padding=(0, 2),
            ))
        elif src == "pending":
            console.print(Panel(
                "[dim italic]" + text[:200] + "...[/dim italic]",
                title=(
                    "[bold red]  Sales Rep @ Zolvo  [/bold red]"
                    "  [dim red]⏳ pendiente — en revisión del Operador[/dim red]"
                ),
                border_style="red",
                padding=(0, 2),
            ))
        elif src == "handoff":
            console.print(
                "  [yellow]  ↑ Conversación transferida al equipo de ventas[/yellow]\n"
            )

    # ── Operator dashboard ───────────────────────────────────────────────────
    console.print()
    console.rule("[bold]DASHBOARD DEL OPERADOR[/bold]")
    console.print(
        f"\n  [dim]GET /operator/dashboard?tenant_id={TENANT_ID}[/dim]\n"
    )

    with console.status("[dim]Fetching operator dashboard...[/dim]"):
        dashboard = get(f"/operator/dashboard?tenant_id={TENANT_ID}")

    if dashboard:
        pipeline = dashboard.get("pipeline", {})
        gates = dashboard.get("quality_gates", {})
        cost_data = dashboard.get("cost", {})
        intents_dist = dashboard.get("intent_distribution", {})

        # Pipeline stats
        p_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        p_table.add_column("Key", style="dim")
        p_table.add_column("Value", style="bold")
        p_table.add_row("Leads en pipeline",    str(pipeline.get("total_leads", 0)))
        p_table.add_row("Conversaciones",        str(pipeline.get("total_conversations", 0)))
        p_table.add_row("Mensajes recibidos",   str(pipeline.get("messages_inbound", 0)))
        p_table.add_row("Mensajes enviados",     str(pipeline.get("messages_outbound", 0)))
        p_table.add_row(
            "Escalaciones pendientes",
            f"[{'red' if gates.get('pending_escalations', 0) > 0 else 'green'}]"
            f"{gates.get('pending_escalations', 0)}[/]",
        )
        p_table.add_row(
            "Costo total USD",
            f"${cost_data.get('total_usd', 0):.6f}",
        )
        console.print(p_table)

        # Cost by agent
        if cost_data.get("by_agent"):
            console.print("  [dim]Costo por agente:[/dim]")
            a_table = Table(box=box.ROUNDED, header_style="bold cyan", padding=(0, 1))
            a_table.add_column("Agente", style="cyan")
            a_table.add_column("USD", justify="right")
            for agent, cost in sorted(
                cost_data["by_agent"].items(), key=lambda x: x[1], reverse=True
            ):
                a_table.add_row(agent, f"${cost:.6f}")
            console.print(a_table)

        # Intent distribution
        if intents_dist:
            console.print()
            console.print("  [dim]Distribución de intents:[/dim]")
            i_table = Table(box=box.ROUNDED, header_style="bold cyan", padding=(0, 1))
            i_table.add_column("Intent", style="cyan")
            i_table.add_column("Count", justify="right")
            for intent_name, count in sorted(
                intents_dist.items(), key=lambda x: x[1], reverse=True
            ):
                i_table.add_row(intent_name, str(count))
            console.print(i_table)

    # ── Final status ─────────────────────────────────────────────────────────
    console.print()
    console.print(
        "  [dim]Cost breakdown → paste [bold]demo/metrics.sql[/bold] in Supabase SQL Editor[/dim]"
    )
    console.print()
    console.print(Panel.fit(
        "[bold green]ingest → classify → generate → evaluate → route  ✓[/bold green]",
        border_style="green",
        padding=(0, 4),
    ))
    console.print()


if __name__ == "__main__":
    main()
