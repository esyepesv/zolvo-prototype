from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from zolvo.models.domain import AgentRun
from zolvo.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    table_name = "agent_runs"
    model_class = AgentRun

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        agent_name: str,
        conversation_id: uuid.UUID | None = None,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: Decimal | None = None,
        latency_ms: int | None = None,
        decision_trace: dict[str, Any] | None = None,
    ) -> AgentRun:
        data: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "agent_name": agent_name,
        }
        if conversation_id:
            data["conversation_id"] = str(conversation_id)
        if input_payload:
            data["input_payload"] = input_payload
        if output_payload:
            data["output_payload"] = output_payload
        if llm_provider:
            data["llm_provider"] = llm_provider
        if llm_model:
            data["llm_model"] = llm_model
        if tokens_in is not None:
            data["tokens_in"] = tokens_in
        if tokens_out is not None:
            data["tokens_out"] = tokens_out
        if cost_usd is not None:
            data["cost_usd"] = float(cost_usd)
        if latency_ms is not None:
            data["latency_ms"] = latency_ms
        if decision_trace:
            data["decision_trace"] = decision_trace
        return await self.add(data)
