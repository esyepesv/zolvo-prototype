#!/usr/bin/env bash
# verify.sh — Verificación de estado al final de cada hito.
# Uso: bash scripts/verify.sh [hito_número]
#
# Sin argumento: corre todos los checks disponibles según hitos completados.
# Con argumento: corre los checks del hito indicado y todos los anteriores.

set -euo pipefail

HITO=${1:-"all"}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ─── Colores ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; EXIT_CODE=1; }
info() { echo -e "${BLUE}→  $1${NC}"; }
section() { echo -e "\n${YELLOW}══ $1 ══${NC}"; }

EXIT_CODE=0

# ─── Activar entorno virtual ──────────────────────────────────────────────────
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo -e "${YELLOW}⚠️  No se encontró .venv. Usando Python del sistema.${NC}"
fi

# Cargar .env si existe
if [ -f ".env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 0 — siempre corren
# ═══════════════════════════════════════════════════════════════════════════════
section "HITO 0 — Setup base"

info "ruff check ."
if ruff check . --quiet 2>/dev/null; then
  pass "ruff check: sin errores"
else
  fail "ruff check: encontró errores"
fi

info "ruff format --check ."
if ruff format --check . --quiet 2>/dev/null; then
  pass "ruff format: todos los archivos formateados"
else
  fail "ruff format: archivos sin formatear"
fi

info "pytest -q"
if pytest -q --tb=short 2>/dev/null; then
  pass "pytest: todos los tests pasan"
else
  fail "pytest: hay tests fallando"
fi

info "uvicorn /health (prueba funcional)"
PYTHONPATH=src uvicorn zolvo.api.main:app --port 18765 --log-level critical &
UVICORN_PID=$!
sleep 2

HEALTH_RESPONSE=$(curl -s http://localhost:18765/health 2>/dev/null || echo "ERROR")
kill "$UVICORN_PID" 2>/dev/null
wait "$UVICORN_PID" 2>/dev/null || true

if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
  pass "GET /health → $HEALTH_RESPONSE"
else
  fail "GET /health falló: $HEALTH_RESPONSE"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 1 — LLM Gateway
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HITO" == "all" || "$HITO" -ge 1 ]] 2>/dev/null; then
  if [ -f "src/zolvo/llm/gateway.py" ]; then
    section "HITO 1 — LLM Gateway"

    info "Importar LLMGateway"
    if PYTHONPATH=src python3 -c "from zolvo.llm.gateway import LLMGateway; print('import OK')" 2>/dev/null | grep -q "import OK"; then
      pass "LLMGateway importable"
    else
      fail "LLMGateway no importa correctamente"
    fi

    info "FakeLLMProvider devuelve respuesta"
    if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.llm.fake_provider import FakeLLMProvider
from zolvo.llm.base import LLMRequest
provider = FakeLLMProvider()
req = LLMRequest(prompt='test', task_type='classification')
result = asyncio.run(provider.complete(req))
assert result.content, 'respuesta vacía'
print('fake OK')
" 2>/dev/null | grep -q "fake OK"; then
      pass "FakeLLMProvider funciona"
    else
      fail "FakeLLMProvider falló"
    fi

    if [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
      info "LLMGateway con proveedor real (classification)"
      if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.llm.gateway import LLMGateway
from zolvo.config import get_settings
gw = LLMGateway(get_settings())
result = asyncio.run(gw.complete(task_type='classification', prompt='Responde solo: ok'))
assert result.content, 'respuesta vacía'
print('gateway real OK')
" 2>/dev/null | grep -q "gateway real OK"; then
        pass "LLMGateway con proveedor real"
      else
        fail "LLMGateway con proveedor real falló"
      fi
    else
      echo -e "${YELLOW}⚠️  OMITIDO: prueba con proveedor real (no hay API key en .env)${NC}"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 2 — Repositorios
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HITO" == "all" || "$HITO" -ge 2 ]] 2>/dev/null; then
  if [ -f "src/zolvo/repositories/leads.py" ]; then
    section "HITO 2 — Repositorios"

    info "Importar repositorios"
    if PYTHONPATH=src python3 -c "
from zolvo.repositories.leads import LeadRepository
from zolvo.repositories.conversations import ConversationRepository
print('repos OK')
" 2>/dev/null | grep -q "repos OK"; then
      pass "Repositorios importables"
    else
      fail "Repositorios no importan"
    fi

    if [ -n "${DATABASE_URL:-}" ]; then
      info "LeadRepository create + get_by_id contra Supabase"
      if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.repositories.leads import LeadRepository
from zolvo.config import get_settings
async def test():
    repo = LeadRepository(get_settings())
    lead = await repo.create(
        tenant_id='00000000-0000-0000-0000-000000000001',
        full_name='Test Lead Verify', company='Acme MX', source='test')
    fetched = await repo.get_by_id(lead.id, tenant_id=lead.tenant_id)
    assert fetched.id == lead.id
    print('repo integration OK')
asyncio.run(test())
" 2>/dev/null | grep -q "repo integration OK"; then
        pass "LeadRepository create + get_by_id"
      else
        fail "LeadRepository integration test falló"
      fi
    else
      echo -e "${YELLOW}⚠️  OMITIDO: test integración Supabase (no hay DATABASE_URL en .env)${NC}"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 5 — Intent Classifier
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HITO" == "all" || "$HITO" -ge 5 ]] 2>/dev/null; then
  if [ -f "src/zolvo/intent/classifier.py" ]; then
    section "HITO 5 — Intent Classifier"

    info "Clasificar mensaje de objeción de precio"
    if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.intent.classifier import IntentClassifier
from zolvo.llm.fake_provider import FakeLLMProvider
clf = IntentClassifier(provider=FakeLLMProvider(overrides={'classify': 'objection_price'}))
result = asyncio.run(clf.classify('Su precio es muy alto'))
assert result.intent == 'objection_price'
assert not result.should_handoff
print('classifier OK')
" 2>/dev/null | grep -q "classifier OK"; then
      pass "IntentClassifier: objection_price sin handoff"
    else
      fail "IntentClassifier falló"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 8 — Confidence Gate
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HITO" == "all" || "$HITO" -ge 8 ]] 2>/dev/null; then
  if [ -f "src/zolvo/agents/evaluator.py" ]; then
    section "HITO 8 — Confidence Gate"

    info "Draft malo → rechazado"
    if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.agents.evaluator import Evaluator
from zolvo.llm.fake_provider import FakeLLMProvider
ev = Evaluator(provider=FakeLLMProvider(overrides={'evaluate': '0.2'}))
result = asyncio.run(ev.evaluate(draft='ERROR ERROR', context={}))
assert not result.should_send
print('evaluator reject OK')
" 2>/dev/null | grep -q "evaluator reject OK"; then
      pass "Evaluator: draft malo rechazado"
    else
      fail "Evaluator: draft malo no fue rechazado"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKS HITO 9 — Orchestrator happy path
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HITO" == "all" || "$HITO" -ge 9 ]] 2>/dev/null; then
  if [ -f "src/zolvo/orchestrator/orchestrator.py" ]; then
    section "HITO 9 — Orchestrator (happy path)"

    if [ -n "${DATABASE_URL:-}" ] && { [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; }; then
      info "reply.received → pipeline completo"
      if PYTHONPATH=src python3 -c "
import asyncio
from zolvo.orchestrator.orchestrator import Orchestrator
from zolvo.config import get_settings
async def test():
    orc = Orchestrator(get_settings())
    result = await orc.process_reply(
        conversation_id='00000000-0000-0000-0000-000000000099',
        message='Me interesa el producto, ¿tienen precios?',
        tenant_id='00000000-0000-0000-0000-000000000001')
    assert result is not None
    print('orchestrator OK')
asyncio.run(test())
" 2>/dev/null | grep -q "orchestrator OK"; then
        pass "Orchestrator happy path end-to-end"
      else
        fail "Orchestrator happy path falló"
      fi
    else
      echo -e "${YELLOW}⚠️  OMITIDO: happy path (requiere DATABASE_URL + API key)${NC}"
    fi
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
if [ $EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}══════════════════════════════════════${NC}"
  echo -e "${GREEN}  ✅ TODOS LOS CHECKS PASARON          ${NC}"
  echo -e "${GREEN}══════════════════════════════════════${NC}"
else
  echo -e "${RED}══════════════════════════════════════${NC}"
  echo -e "${RED}  ❌ HAY CHECKS FALLANDO               ${NC}"
  echo -e "${RED}  Revisa los errores arriba             ${NC}"
  echo -e "${RED}══════════════════════════════════════${NC}"
fi

exit $EXIT_CODE
