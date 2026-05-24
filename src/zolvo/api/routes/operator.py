from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from zolvo.api.deps import get_supabase

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/dashboard")
async def operator_dashboard(
    tenant_id: uuid.UUID,
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """Real-time pipeline state for the Sales Rep / Operator."""
    tid = str(tenant_id)

    leads_resp = await supabase.table("leads").select("id").eq("tenant_id", tid).execute()
    convs_resp = await supabase.table("conversations").select("id").eq("tenant_id", tid).execute()
    msgs_resp = (
        await supabase.table("messages").select("direction").eq("tenant_id", tid).execute()
    )
    runs_resp = (
        await supabase.table("agent_runs")
        .select("agent_name, cost_usd, latency_ms, output_payload")
        .eq("tenant_id", tid)
        .execute()
    )

    total_leads = len(leads_resp.data)
    total_conversations = len(convs_resp.data)
    inbound = sum(1 for m in msgs_resp.data if m["direction"] == "inbound")
    outbound = sum(1 for m in msgs_resp.data if m["direction"] == "outbound")

    total_cost = 0.0
    intent_distribution: dict[str, int] = {}
    pending_escalations = 0
    agent_cost: dict[str, float] = {}

    for run in runs_resp.data:
        cost = float(run.get("cost_usd") or 0)
        total_cost += cost
        name = run["agent_name"]
        agent_cost[name] = round(agent_cost.get(name, 0.0) + cost, 6)

        payload = run.get("output_payload") or {}
        if name == "intent_classifier":
            intent = payload.get("intent", "unknown")
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
        if name == "evaluator" and not payload.get("should_send", True):
            pending_escalations += 1

    return {
        "tenant_id": tid,
        "pipeline": {
            "total_leads": total_leads,
            "total_conversations": total_conversations,
            "messages_inbound": inbound,
            "messages_outbound": outbound,
        },
        "quality_gates": {
            "pending_escalations": pending_escalations,
        },
        "cost": {
            "total_usd": round(total_cost, 6),
            "by_agent": agent_cost,
        },
        "intent_distribution": intent_distribution,
    }
