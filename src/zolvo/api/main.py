from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI

from zolvo.config import get_settings
from zolvo.observability.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    settings = get_settings()
    configure_logging(settings)
    logger.info("startup", env=settings.env)
    yield
    logger.info("shutdown")


app = FastAPI(title="Zolvo AI Sales Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "env": settings.env}
