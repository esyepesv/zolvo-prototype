from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from supabase import AsyncClient, acreate_client

from zolvo.config import get_settings


@lru_cache
def _get_client_args() -> tuple[str, str]:
    s = get_settings()
    return s.supabase_url, s.supabase_service_role_key


async def get_supabase() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI dependency that yields an async Supabase client (service role)."""
    url, key = _get_client_args()
    client: AsyncClient = await acreate_client(url, key)
    try:
        yield client
    finally:
        await client.auth.sign_out()
