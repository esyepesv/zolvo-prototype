from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from supabase import AsyncClient

M = TypeVar("M")


class BaseRepository(Generic[M]):
    """Async Supabase repository base."""

    table_name: str
    model_class: type[M]

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _table(self) -> Any:
        return self._client.table(self.table_name)

    def _to_model(self, row: dict[str, Any]) -> M:
        return self.model_class(**row)

    async def get_by_id(self, record_id: uuid.UUID) -> M | None:
        res = await self._table().select("*").eq("id", str(record_id)).execute()
        if res.data:
            return self._to_model(res.data[0])
        return None

    async def add(self, data: dict[str, Any]) -> M:
        res = await self._table().insert(data).execute()
        return self._to_model(res.data[0])
