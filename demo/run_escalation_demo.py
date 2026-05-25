#!/usr/bin/env python3
"""
Demo: Zolvo AI Sales Engine — Escalation Path

Shows two distinct escalation mechanisms:
  Turn 1 — meeting_intent    → Gate 1 PASS  / Gate 2 PASS   → action: send
  Turn 2 — complex_technical → Gate 1 HANDOFF               → action: handoff (SDR alert)
  Turn 3 — complaint         → Gate 1 HANDOFF               → action: handoff (SDR alert)

Key insight: the system knows its own limits. Gate 1 routes complex technical questions
and complaints directly to a human rep instead of generating a potentially wrong answer.

Usage:
    # Terminal 1 — start API:
    PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --reload

    # Terminal 2 — run demo:
    .venv/bin/python demo/run_escalation_demo.py
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
    "full_name": "Sofía Herrera",
    "email": "sofia.herrera@conekta.com",
    "linkedin_url": "https://linkedin.com/in/sofia-herrera-conekta",
    "company": "Conekta",
    "role": "VP de Ventas B2B",
    "source": "linkedin",
    "channel": "linkedin",
}

REPLY_TURNS = [
    {
        "label": "Turn 1 — Interés: quiere agendar demo",
        "message": (
            "Hola, gracias por escribirme. En Conekta procesamos millones de pagos al mes "
            "y siempre estamos buscando herramientas que mejoren nuestra conversión de "
            "ventas B2B. Me interesa mucho lo que describes. ¿Podemos agendar una demo "
            "esta semana?"
        ),
        "expected": "meeting_intent → SEND",
    },
    {
        "label": "Turn 2 — Pregunta técnica compleja (escala a SDR)",
        "message": (
            "Antes de seguir, necesito saber si su sistema puede integrarse directamente "
            "con nuestro pipeline de datos en tiempo real: Kafka con schemas AVRO, "
            "50 000 transacciones por segundo, latencia máxima de 80 ms. Además tenemos "
            "restricciones de residencia de datos — todo debe quedarse en servidores "
            "mexicanos por cumplimiento con el CNBV. ¿Tienen certificación SOC 2 Tipo II "
            "y contrato de procesador de datos bajo LFPDPPP?"
        ),
        "expected": "complex_technical → HANDOFF",
    },
    {
        "label": "Turn 3 — Queja: nadie le respondió (escala a SDR)",
        "message": (
            "Ya han pasado dos días desde que pregunté lo técnico y no he recibido "
            "respuesta. Esto es exactamente el tipo de servicio que NO queremos de un "
            "proveedor. Si no pueden responder preguntas básicas en tiempo razonable, "
            "no veo cómo confiarles nuestra infraestructura de pagos."
        ),
        "expected": "complaint → HANDOFF",
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
        "[bold yellow]ZOLVO AI SALES ENGINE[/bold yellow]\n"
        "[dim]Demo · Escalation Path · El sistema sabe cuándo ceder el control[/dim]",
        border_style="yellow",
        padding=(1, 4),
    ))
    console.print(
        "  [dim]Gate 1 routes [bold]complex_technical[/bold], [bold]complaint[/bold], "
        "and [bold]opt_out[/bold] directly to a human rep.\n"
        "  Watch Terminal 1 for [bold yellow]slack.handoff_alert[/bold yellow] events.[/dim]\n"
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
    prospect_thread: list[dict] = [
        {"from": "agent", "text": f"Subject: {ingest['subject']}\n\n{ingest['body']}"},
    ]

    for i, turn in enumerate(REPLY_TURNS):
        console.print()
        console.rule(f"[bold]STEP {i + 2} — {turn['label']}[/bold]")
        console.print(f"  [dim]Expected: {turn['expected']}[/dim]\n")
        console.print(Panel(
            turn["message"],
            title="[bold blue]  PROSPECT  [/bold blue]",
            border_style="blue",
            padding=(0, 2),
        ))
        prospect_thread.append({"from": "prospect", "text": turn["message"]})

        t0 = time.monotonic()
        with console.status("[dim]Gate 1: classifying intent…[/dim]"):
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
                title="[bold green]  Agent Reply — enviado vía LinkedIn[/bold green]",
                border_style="green",
                padding=(0, 2),
            ))
            prospect_thread.append({"from": "agent", "text": reply["draft"]})

        elif action == "handoff":
            reason = reply.get("reason", "")
            console.print(Panel(
                f"[yellow]Intent:[/yellow] [bold]{intent}[/bold]\n\n"
                f"[yellow]Reason:[/yellow] {reason}\n\n"
                f"[dim]→ Sales rep notified via Slack\n"
                f"→ Conversation status: handoff\n"
                f"→ SDR takes over from here[/dim]",
                title="[bold yellow]  ⚠ HANDOFF — Human Rep Required  [/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            ))
            console.print(
                "  [dim yellow]→ Check Terminal 1: slack.handoff_alert[/dim yellow]\n"
            )
            prospect_thread.append({"from": "handoff", "text": reason})

        elif action == "escalate" and reply.get("draft"):
            console.print(Panel(
                reply["draft"],
                title="[bold red]  Draft blocked — pending operator review[/bold red]",
                border_style="red",
                padding=(0, 2),
            ))
            prospect_thread.append({"from": "pending", "text": reply["draft"]})

    # ── Pipeline Summary ─────────────────────────────────────────────────────
    console.print()
    console.rule("[bold]PIPELINE SUMMARY[/bold]")
    console.print()

    intents = [r["intent"] for r in results]
    actions = [r["action"] for r in results]
    scores = [r["confidence_score"] for r in results if r.get("confidence_score") is not None]

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("Turn",   style="dim",  width=6,  justify="center")
    table.add_column("Intent", style="cyan", min_width=20)
    table.add_column("Action", justify="center", min_width=12)
    table.add_column("Score",  justify="right", min_width=7)
    table.add_column("Gate 1", justify="center", min_width=12)
    table.add_column("Gate 2", justify="center", min_width=10)

    for i, r in enumerate(results):
        act = r["action"]
        lbl, sty = _ACTION_STYLE.get(act, (act.upper(), "white"))
        sc = r.get("confidence_score")
        sc_str = f"{sc:.3f}" if sc is not None else "n/a"
        gate1 = (
            "[yellow]HANDOFF[/yellow]" if act == "handoff"
            else "[green]PASS[/green]"
        )
        gate2 = (
            "[green]PASS[/green]" if act == "send"
            else "[red]BLOCK[/red]" if act == "escalate"
            else "[dim]skipped[/dim]"
        )
        table.add_row(str(i + 1), r["intent"], f"[{sty}]{lbl}[/]", sc_str, gate1, gate2)

    console.print(table)
    console.print()

    avg_score = sum(scores) / len(scores) if scores else 0
    send_count  = actions.count("send")
    esc_count   = actions.count("escalate")
    hand_count  = actions.count("handoff")

    console.print(f"  Intent path       [cyan]{' → '.join(intents)}[/cyan]")
    console.print(f"  Avg conf score    [bold]{'—' if not scores else f'{avg_score:.3f}'}[/bold]")
    console.print(
        f"  Sends / Escalations / Handoffs   "
        f"[green]{send_count}[/green] / [red]{esc_count}[/red] / [yellow]{hand_count}[/yellow]"
    )
    console.print()

    # ── Key insight ──────────────────────────────────────────────────────────
    console.rule("[bold]DESIGN INSIGHT[/bold]")
    console.print()
    console.print(Panel(
        "[bold]Gate 1 — Intent Classifier[/bold] routes these intents to human reps:\n\n"
        "  [yellow]complex_technical[/yellow]  →  Question requires product/engineering expertise\n"
        "  [yellow]complaint[/yellow]          →  Negative sentiment requires empathy + authority\n"
        "  [yellow]out_of_scope[/yellow]        →  Message is unrelated to the sales context\n"
        "  [yellow]opt_out[/yellow]             →  Legal/compliance — must be handled by a human\n\n"
        "[dim]The system does NOT try to answer what it cannot answer well.\n"
        "Autonomy where possible. Human escalation where necessary.[/dim]",
        border_style="yellow",
        padding=(1, 2),
    ))
    console.print()

    # ── Prospect view ─────────────────────────────────────────────────────────
    console.rule("[bold]VISTA DEL PROSPECTO — LinkedIn Inbox[/bold]")
    console.print(
        f"\n  [dim]Lo que {LEAD['full_name']} ve en su bandeja de LinkedIn[/dim]\n"
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
        elif src == "handoff":
            console.print(
                f"  [yellow]  ↑ Conversation transferred to sales team[/yellow]\n"
                f"  [dim yellow]  Reason: {text}[/dim yellow]\n"
            )
        elif src == "pending":
            console.print(Panel(
                "[dim italic]" + text[:200] + "...[/dim italic]",
                title="[bold red]  Draft pending operator review[/bold red]",
                border_style="red",
                padding=(0, 2),
            ))

    # ── Operator dashboard ───────────────────────────────────────────────────
    console.print()
    console.rule("[bold]DASHBOARD DEL OPERADOR[/bold]")
    console.print(
        f"\n  [dim]GET /operator/dashboard?tenant_id={TENANT_ID}[/dim]\n"
    )

    with console.status("[dim]Fetching operator dashboard...[/dim]"):
        dashboard = get(f"/operator/dashboard?tenant_id={TENANT_ID}")

    if dashboard:
        pipeline  = dashboard.get("pipeline", {})
        gates     = dashboard.get("quality_gates", {})
        cost_data = dashboard.get("cost", {})
        intents_d = dashboard.get("intent_distribution", {})

        p_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        p_table.add_column("Key",   style="dim")
        p_table.add_column("Value", style="bold")
        p_table.add_row("Leads en pipeline",      str(pipeline.get("total_leads", 0)))
        p_table.add_row("Conversaciones",          str(pipeline.get("total_conversations", 0)))
        p_table.add_row("Mensajes recibidos",     str(pipeline.get("messages_inbound", 0)))
        p_table.add_row("Mensajes enviados",       str(pipeline.get("messages_outbound", 0)))
        p_table.add_row(
            "Handoffs / Escalaciones",
            f"[yellow]{gates.get('pending_escalations', 0)}[/yellow]",
        )
        p_table.add_row("Costo total USD", f"${cost_data.get('total_usd', 0):.6f}")
        console.print(p_table)

        if intents_d:
            console.print("  [dim]Intent distribution:[/dim]")
            i_table = Table(box=box.ROUNDED, header_style="bold cyan", padding=(0, 1))
            i_table.add_column("Intent", style="cyan")
            i_table.add_column("Count",  justify="right")
            for intent_name, count in sorted(
                intents_d.items(), key=lambda x: x[1], reverse=True
            ):
                i_table.add_row(intent_name, str(count))
            console.print(i_table)

    # ── Final ─────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel.fit(
        "[bold yellow]classify → handoff × 2 — human rep alerted  ✓[/bold yellow]",
        border_style="yellow",
        padding=(0, 4),
    ))
    console.print()


if __name__ == "__main__":
    main()
