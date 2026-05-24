from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from zolvo.llm.gateway import LLMGateway
from zolvo.models.domain import MemoryMatch, Message
from zolvo.repositories.messages import MessageRepository

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "summarizer.txt"
_SUMMARY_TABLE = "conversation_summaries_embeddings"


class MemoryService:
    """Dual memory: short-term textual + long-term semantic (ADR-07).

    Short-term: last N messages from the current conversation (textual, no vectorization).
    Long-term: similarity search over lead_embeddings and conversation_summaries_embeddings
    via pgvector RPC functions.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        gateway: LLMGateway,
        supabase_client: object,
    ) -> None:
        self._message_repo = message_repo
        self._gateway = gateway
        self._client = supabase_client

    async def get_short_term(
        self,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        n: int = 15,
    ) -> list[Message]:
        """Return the last *n* messages from a conversation, ordered by sent_at ASC."""
        return await self._message_repo.get_by_conversation_id(tenant_id, conversation_id, limit=n)

    async def get_long_term(
        self,
        query_embedding: list[float],
        tenant_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[MemoryMatch]:
        """Similarity search across lead_embeddings and conversation_summaries."""
        params = {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "filter_tenant_id": str(tenant_id),
        }

        lead_matches = await self._rpc("match_lead_embeddings", params)
        summary_matches = await self._rpc("match_conversation_summaries", params)

        results: list[MemoryMatch] = []

        for row in lead_matches:
            results.append(
                MemoryMatch(
                    source="lead_embedding",
                    source_id=uuid.UUID(row["lead_id"]),
                    text=row.get("source_text", ""),
                    similarity=float(row.get("similarity", 0.0)),
                    metadata={"id": row["id"]},
                )
            )

        for row in summary_matches:
            results.append(
                MemoryMatch(
                    source="conversation_summary",
                    source_id=uuid.UUID(row["conversation_id"]),
                    text=row.get("summary_text", ""),
                    similarity=float(row.get("similarity", 0.0)),
                    metadata={
                        "id": row["id"],
                        "outcome": row.get("outcome"),
                    },
                )
            )

        results.sort(key=lambda m: m.similarity, reverse=True)
        return results[:top_k]

    async def summarize_and_index(
        self,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Summarize a conversation via LLM, embed the summary, and persist it."""
        messages = await self._message_repo.get_by_conversation_id(
            tenant_id, conversation_id, limit=200
        )
        if not messages:
            log.warning(
                "memory.summarize.no_messages",
                conversation_id=str(conversation_id),
            )
            return

        conversation_text = _format_messages(messages)
        prompt = _load_prompt().replace("{conversation}", conversation_text)

        llm_response = await self._gateway.complete(
            task_type="generation_standard",
            prompt=prompt,
            max_tokens=512,
            temperature=0.3,
        )
        summary_text = llm_response.content.strip()

        embed_response = await self._gateway.embed(summary_text)

        await (
            self._client.table(_SUMMARY_TABLE)  # type: ignore[union-attr]
            .upsert(
                {
                    "conversation_id": str(conversation_id),
                    "tenant_id": str(tenant_id),
                    "embedding": embed_response.vector,
                    "summary_text": summary_text,
                    "model_used": embed_response.model,
                },
                on_conflict="conversation_id",
            )
            .execute()
        )

        log.info(
            "memory.summarize.done",
            conversation_id=str(conversation_id),
            summary_len=len(summary_text),
            model=llm_response.model,
        )

    # ── helpers ───────────────────────────────────────────────────────────

    async def _rpc(self, fn_name: str, params: dict) -> list[dict]:
        """Call a Supabase RPC function and return the result rows."""
        res = await self._client.rpc(fn_name, params).execute()  # type: ignore[union-attr]
        return res.data if res.data else []


def _format_messages(messages: list[Message]) -> str:
    """Format a list of messages into a readable conversation transcript."""
    lines: list[str] = []
    for msg in messages:
        role = "PROSPECT" if msg.direction == "inbound" else "AGENTE"
        lines.append(f"[{role}]: {msg.content}")
    return "\n".join(lines)


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")
