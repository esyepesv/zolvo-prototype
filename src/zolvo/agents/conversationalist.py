from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog

from zolvo.agents.base import AgentBase
from zolvo.intent.classifier import IntentResult
from zolvo.llm.gateway import LLMGateway
from zolvo.memory.service import MemoryService
from zolvo.models.domain import MemoryMatch, Message
from zolvo.repositories.agent_runs import AgentRunRepository

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "conversationalist.txt"

_INTENT_GUIDANCE: dict[str, str] = {
    "interested": (
        "El prospecto muestra interés genuino. Profundiza con 1-2 preguntas de calificación "
        "(presupuesto, autoridad, necesidad, timing). No presiones, explora con curiosidad."
    ),
    "objection_price": (
        "El prospecto objeta el precio. Reencuadra el valor en términos de impacto en su negocio. "
        "Pregunta qué presupuesto manejan y qué impacto tendría resolver el problema. "
        "No cedes en precio directamente."
    ),
    "objection_authority": (
        "El prospecto no es el decisor final. Valida su rol y ofrece materiales ejecutivos para "
        "su equipo. Pregunta si puedes agendar una llamada breve con quien sí decide."
    ),
    "objection_timing": (
        "El prospecto dice que no es el momento. Valida su situación actual. Planta una semilla "
        "de valor con un insight relevante a su industria. Propón retomar en 30 días."
    ),
    "meeting_intent": (
        "El prospecto quiere agendar una reunión o llamada. Confirma su disposición, propón "
        "2-3 opciones concretas de horario (mañana o esta semana) y especifica la agenda "
        "de la llamada: 20 min, enfocado en entender su situación actual."
    ),
    "out_of_scope": (
        "El mensaje está fuera del contexto comercial. Redirige amablemente hacia la "
        "conversación original con una pregunta relevante."
    ),
    "complex_technical": (
        "El prospecto hace preguntas técnicas muy específicas. Reconoce la pregunta, menciona "
        "que la respuesta precisa requiere involucrar a un experto técnico y ofrece conectarlos."
    ),
    "complaint": (
        "El prospecto expresa frustración. Disculpate brevemente sin defensividad, valida su "
        "experiencia y ofrece resolver el problema específico que menciona."
    ),
    "opt_out": (
        "El prospecto quiere retirarse. Respeta su decisión con gracia, agradece su tiempo y "
        "deja la puerta abierta para el futuro sin insistir."
    ),
}


@dataclass(frozen=True)
class ConversationalistResult:
    conversation_id: uuid.UUID
    draft_message: str
    intent_handled: str
    agent_run_id: uuid.UUID


class ConversationalistAgent(AgentBase):
    """Generates multi-turn replies using dual memory and intent-aware guidance."""

    def __init__(
        self,
        gateway: LLMGateway,
        memory_service: MemoryService,
        agent_run_repo: AgentRunRepository,
    ) -> None:
        super().__init__(gateway)
        self._memory_service = memory_service
        self._agent_run_repo = agent_run_repo

    @property
    def agent_name(self) -> str:
        return "conversationalist"

    async def run(
        self,
        *,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        latest_message: str,
        intent_result: IntentResult,
    ) -> ConversationalistResult:
        t0 = time.monotonic()

        embed_response = await self._gateway.embed(latest_message)
        short_term = await self._memory_service.get_short_term(conversation_id, tenant_id)
        long_term = await self._memory_service.get_long_term(
            embed_response.vector, tenant_id=tenant_id, top_k=3
        )

        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(
            short_term_context=_format_short_term(short_term) or "Sin mensajes previos.",
            long_term_context=_format_long_term(long_term) or "Sin contexto previo disponible.",
            latest_message=latest_message,
            intent=intent_result.intent,
            intent_guidance=_INTENT_GUIDANCE.get(
                intent_result.intent, "Responde de forma profesional y útil."
            ),
        )

        response = await self._gateway.complete(
            task_type="generation_standard",
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)
        agent_run = await self._agent_run_repo.create(
            tenant_id=tenant_id,
            agent_name=self.agent_name,
            conversation_id=conversation_id,
            input_payload={"latest_message": latest_message, "intent": intent_result.intent},
            output_payload={"draft": response.content},
            llm_provider=response.provider,
            llm_model=response.model,
            tokens_in=response.tokens_in + embed_response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd + embed_response.cost_usd,
            latency_ms=latency_ms,
        )

        log.info(
            "conversationalist.completed",
            conversation_id=str(conversation_id),
            intent=intent_result.intent,
            cost_usd=round(response.cost_usd + embed_response.cost_usd, 6),
            latency_ms=latency_ms,
        )

        return ConversationalistResult(
            conversation_id=conversation_id,
            draft_message=response.content,
            intent_handled=intent_result.intent,
            agent_run_id=agent_run.id,
        )


def _format_short_term(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = "PROSPECT" if msg.direction == "inbound" else "AGENTE"
        lines.append(f"[{role}]: {msg.content}")
    return "\n".join(lines)


def _format_long_term(matches: list[MemoryMatch]) -> str:
    if not matches:
        return ""
    lines: list[str] = []
    for m in matches:
        lines.append(f"- [{m.source}] (sim {m.similarity:.2f}): {m.text[:200]}")
    return "\n".join(lines)
