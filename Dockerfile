# syntax=docker/dockerfile:1.7
# ── Builder stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH=/home/zolvo/.local/bin:$PATH

# Non-root user for runtime safety.
RUN groupadd --system zolvo && \
    useradd --system --gid zolvo --create-home --shell /usr/sbin/nologin zolvo

WORKDIR /app

# Copy installed Python packages from builder.
COPY --from=builder --chown=zolvo:zolvo /root/.local /home/zolvo/.local

# Copy application source.
COPY --chown=zolvo:zolvo src ./src

USER zolvo

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "zolvo.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
