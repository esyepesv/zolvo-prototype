from __future__ import annotations

import json

import pytest

from zolvo.config import Settings
from zolvo.intent.classifier import IntentClassificationError, IntentClassifier, IntentResult
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.gateway import LLMGateway


def _make_classifier(classification_response: str) -> IntentClassifier:
    fake = FakeLLMProvider(overrides={"classification": classification_response})
    settings = Settings(
        env="test",
        preferred_llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        ollama_api_key="",
    )
    gateway = LLMGateway(settings, extra_providers={"openai": fake})
    return IntentClassifier(gateway)


def _intent_json(intent: str, confidence: float = 0.9, reason: str = "test") -> str:
    return json.dumps(
        {
            "intent": intent,
            "confidence": confidence,
            "reason": reason,
            "should_handoff": intent in {"complaint", "complex_technical", "out_of_scope", "opt_out"},  # noqa: E501
        }
    )


# ─── DoD cases ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_objection_price_does_not_handoff() -> None:
    """DoD: objection_price → should_handoff=False."""
    classifier = _make_classifier(_intent_json("objection_price", reason="El precio es muy alto."))
    result = await classifier.classify(
        "Honestamente su precio está muy por encima de nuestro presupuesto."
    )
    assert result.intent == "objection_price"
    assert result.should_handoff is False
    assert isinstance(result, IntentResult)


@pytest.mark.asyncio
async def test_complaint_triggers_handoff() -> None:
    """DoD: complaint → should_handoff=True."""
    classifier = _make_classifier(_intent_json("complaint", reason="Expresa molestia."))
    result = await classifier.classify("Ya les dije que no me contactaran, esto es muy molesto.")
    assert result.intent == "complaint"
    assert result.should_handoff is True


# ─── All 9 categories ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interested_does_not_handoff() -> None:
    classifier = _make_classifier(_intent_json("interested"))
    result = await classifier.classify(
        "Me parece interesante, ¿pueden contarme más sobre las integraciones?"
    )
    assert result.intent == "interested"
    assert result.should_handoff is False


@pytest.mark.asyncio
async def test_meeting_intent_does_not_handoff() -> None:
    classifier = _make_classifier(_intent_json("meeting_intent"))
    result = await classifier.classify(
        "Sí me gustaría agendar una llamada, ¿cuándo tienen disponibilidad?"
    )
    assert result.intent == "meeting_intent"
    assert result.should_handoff is False


@pytest.mark.asyncio
async def test_opt_out_triggers_handoff() -> None:
    classifier = _make_classifier(_intent_json("opt_out"))
    result = await classifier.classify(
        "Por favor elimínenme de su lista, no quiero más correos."
    )
    assert result.intent == "opt_out"
    assert result.should_handoff is True


@pytest.mark.asyncio
async def test_complex_technical_triggers_handoff() -> None:
    classifier = _make_classifier(_intent_json("complex_technical"))
    result = await classifier.classify(
        "¿Su API soporta mTLS con certificados ECC P-384 para el endpoint de webhooks?"
    )
    assert result.intent == "complex_technical"
    assert result.should_handoff is True


@pytest.mark.asyncio
async def test_out_of_scope_triggers_handoff() -> None:
    classifier = _make_classifier(_intent_json("out_of_scope"))
    result = await classifier.classify("¿Cuánto cuesta un boleto de avión a Cancún?")
    assert result.intent == "out_of_scope"
    assert result.should_handoff is True


# ─── Edge cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_intent_falls_back_to_out_of_scope() -> None:
    """If LLM returns an unknown category, default to out_of_scope."""
    classifier = _make_classifier(
        json.dumps({"intent": "categoria_inventada", "confidence": 0.3, "reason": "raro"})
    )
    result = await classifier.classify("Mensaje cualquiera")
    assert result.intent == "out_of_scope"
    assert result.should_handoff is True


@pytest.mark.asyncio
async def test_non_json_response_raises_error() -> None:
    classifier = _make_classifier("No pude clasificar este mensaje.")
    with pytest.raises(IntentClassificationError):
        await classifier.classify("Hola")


@pytest.mark.asyncio
async def test_confidence_is_preserved() -> None:
    classifier = _make_classifier(_intent_json("interested", confidence=0.95))
    result = await classifier.classify("Muy interesante propuesta.")
    assert result.confidence == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_classify_with_context() -> None:
    classifier = _make_classifier(_intent_json("objection_timing"))
    result = await classifier.classify(
        message="Ahora no es buen momento, contáctenme en Q3.",
        context="Turno anterior: enviamos mensaje inicial de presentación.",
    )
    assert result.intent == "objection_timing"
    assert result.should_handoff is False
