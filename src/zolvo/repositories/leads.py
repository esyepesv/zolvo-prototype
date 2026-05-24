from __future__ import annotations

import uuid
from typing import Any

from zolvo.models.domain import Lead
from zolvo.repositories.base import BaseRepository

_LEAD_EMBEDDINGS_TABLE = "lead_embeddings"


class LeadRepository(BaseRepository[Lead]):
    table_name = "leads"
    model_class = Lead

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        full_name: str,
        source: str = "manual",
        email: str | None = None,
        linkedin_url: str | None = None,
        company: str | None = None,
        role: str | None = None,
        status: str = "researching",
    ) -> Lead:
        data: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "full_name": full_name,
            "source": source,
            "status": status,
        }
        if email:
            data["email"] = email
        if linkedin_url:
            data["linkedin_url"] = linkedin_url
        if company:
            data["company"] = company
        if role:
            data["role"] = role
        return await self.add(data)

    async def update_enriched_data(self, lead_id: uuid.UUID, enriched_data: dict[str, Any]) -> None:
        await (
            self._table().update({"enriched_data": enriched_data}).eq("id", str(lead_id)).execute()
        )

    async def update_status(self, lead_id: uuid.UUID, status: str) -> None:
        await self._table().update({"status": status}).eq("id", str(lead_id)).execute()

    async def list_by_status(self, tenant_id: uuid.UUID, status: str) -> list[Lead]:
        res = await (
            self._table().select("*").eq("tenant_id", str(tenant_id)).eq("status", status).execute()
        )
        return [Lead(**row) for row in res.data]

    async def get_by_id_and_tenant(self, lead_id: uuid.UUID, tenant_id: uuid.UUID) -> Lead | None:
        res = (
            await self._table()
            .select("*")
            .eq("id", str(lead_id))
            .eq("tenant_id", str(tenant_id))
            .execute()
        )
        if res.data:
            return Lead(**res.data[0])
        return None

    async def save_embedding(
        self,
        *,
        lead_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vector: list[float],
        source_text: str,
        model: str,
    ) -> None:
        await (
            self._client.table(_LEAD_EMBEDDINGS_TABLE)
            .upsert(
                {
                    "lead_id": str(lead_id),
                    "tenant_id": str(tenant_id),
                    "embedding": vector,
                    "source_text": source_text,
                    "model": model,
                },
                on_conflict="lead_id",
            )
            .execute()
        )
