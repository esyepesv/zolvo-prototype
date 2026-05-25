from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from zolvo.api.routes.agents import router as agents_router
from zolvo.api.routes.events import router as events_router
from zolvo.api.routes.operator import router as operator_router
from zolvo.config import get_settings
from zolvo.observability.logging import configure_logging

_STATIC_DIR = Path(__file__).parent / "static"

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    settings = get_settings()
    configure_logging(settings)
    logger.info("startup", env=settings.env)
    yield
    logger.info("shutdown")


app = FastAPI(title="Zolvo AI Sales Engine", version="0.1.0", lifespan=lifespan)

app.include_router(agents_router)
app.include_router(events_router)
app.include_router(operator_router)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "env": settings.env}


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page() -> FileResponse:
    """Operator dashboard (HTML) — consumes GET /operator/dashboard JSON."""
    return FileResponse(_STATIC_DIR / "dashboard.html")
