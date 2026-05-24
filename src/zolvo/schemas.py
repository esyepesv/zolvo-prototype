from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class IngestRequest(BaseModel):
    tenant_id: uuid.UUID
    full_name: str
    email: str | None = None
    linkedin_url: str | None = None
    company: str | None = None
    role: str | None = None
    source: str = "webhook"
    channel: Literal["linkedin", "email"] = "linkedin"


class IngestResponse(BaseModel):
    lead_id: uuid.UUID
    conversation_id: uuid.UUID
    subject: str
    body: str
    channel: str
    researcher_run_id: uuid.UUID
    copywriter_run_id: uuid.UUID


class ReplyRequest(BaseModel):
    conversation_id: uuid.UUID
    tenant_id: uuid.UUID
    message: str


class ReplyResponse(BaseModel):
    action: Literal["send", "handoff", "escalate"]
    intent: str
    draft: str | None
    confidence_score: float | None
    reason: str
