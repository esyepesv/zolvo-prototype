from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def set_test_env() -> None:
    """Force test environment so Settings picks up safe defaults."""
    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
