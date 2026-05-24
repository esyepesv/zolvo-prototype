from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Lead(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    source: str = "manual"
    full_name: str
    email: str | None = None
    linkedin_url: str | None = None
    company: str | None = None
    role: str | None = None
    enriched_data: dict[str, Any] | None = None
    status: str = "researching"
    owner_id: uuid.UUID | None = None
    created_at: datetime | None = None


class Conversation(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    channel: str = "linkedin"
    started_at: datetime | None = None
    status: str = "researching"
    current_stage: str | None = None
    loss_reason: str | None = None


class Message(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str  # "inbound" | "outbound"
    channel: str = "linkedin"
    content: str
    generated_by_agent: str | None = None
    confidence_score: Decimal | None = None
    human_reviewed: bool = False
    sent_at: datetime | None = None


class AgentRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    agent_name: str
    conversation_id: uuid.UUID | None = None
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: Decimal | None = None
    latency_ms: int | None = None
    decision_trace: dict[str, Any] | None = None
    created_at: datetime | None = None


class EventOutbox(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    aggregate_id: uuid.UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime | None = None
    attempts: int = 0
    created_at: datetime | None = None


class ConversationSummary(BaseModel):
    """Maps to conversation_summaries_embeddings table."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID
    tenant_id: uuid.UUID
    summary_text: str | None = None
    outcome: str | None = None
    loss_reason: str | None = None
    model_used: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class MemoryMatch:
    """DTO returned by long-term similarity search."""

    source: str  # "lead_embedding" | "conversation_summary"
    source_id: uuid.UUID
    text: str
    similarity: float
    metadata: dict[str, Any] = dc_field(default_factory=dict)
