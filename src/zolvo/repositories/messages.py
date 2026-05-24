from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from zolvo.models.domain import Message
from zolvo.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    table_name = "messages"
    model_class = Message

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        direction: str,
        content: str,
        channel: str = "linkedin",
        generated_by_agent: str | None = None,
        confidence_score: Decimal | None = None,
    ) -> Message:
        data: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "conversation_id": str(conversation_id),
            "direction": direction,
            "content": content,
            "channel": channel,
        }
        if generated_by_agent:
            data["generated_by_agent"] = generated_by_agent
        if confidence_score is not None:
            data["confidence_score"] = float(confidence_score)
        return await self.add(data)

    async def get_by_conversation_id(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID, limit: int = 20
    ) -> list[Message]:
        res = (
            await self._table()
            .select("*")
            .eq("tenant_id", str(tenant_id))
            .eq("conversation_id", str(conversation_id))
            .order("sent_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [Message(**row) for row in res.data]
