from __future__ import annotations

import os

# Set ENV before any module-level imports cache Settings via lru_cache.
os.environ["ENV"] = "test"
os.environ.setdefault("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from zolvo.config import get_settings  # noqa: E402

get_settings.cache_clear()
