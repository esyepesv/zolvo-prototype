from __future__ import annotations

import uuid

from zolvo.models.domain import Conversation
from zolvo.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    table_name = "conversations"
    model_class = Conversation

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: str = "linkedin",
        status: str = "researching",
    ) -> Conversation:
        data = {
            "tenant_id": str(tenant_id),
            "lead_id": str(lead_id),
            "channel": channel,
            "status": status,
        }
        return await self.add(data)

    async def get_by_lead_id(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Conversation]:
        res = (
            await self._table()
            .select("*")
            .eq("tenant_id", str(tenant_id))
            .eq("lead_id", str(lead_id))
            .execute()
        )
        return [Conversation(**row) for row in res.data]

    async def get_by_status(
        self, tenant_id: uuid.UUID, status: str
    ) -> list[Conversation]:
        res = (
            await self._table()
            .select("*")
            .eq("tenant_id", str(tenant_id))
            .eq("status", status)
            .execute()
        )
        return [Conversation(**row) for row in res.data]

    async def update_status(self, conversation_id: uuid.UUID, status: str) -> None:
        await self._table().update({"status": status}).eq("id", str(conversation_id)).execute()
