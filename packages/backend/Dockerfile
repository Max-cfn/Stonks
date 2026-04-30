# Stonks Backend — Multi-stage Dockerfile (FastAPI, production)
# Target: < 200 MB
#
# Usage:
#   docker build -t stonks-backend -f packages/backend/Dockerfile .
#   docker run -p 8000:8000 --env-file .env stonks-backend

# ── Stage 1: Build ───────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Copy dependency files only (layer caching)
COPY packages/backend/pyproject.toml packages/backend/README.md ./
COPY packages/shared-types/ ../shared-types/

# Install dependencies in a virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    uv pip install --no-cache -r <(sed -n '/dependencies/,/]/p' pyproject.toml | grep '"' | sed 's/[",]//g' | awk '{$1=$1};1') && \
    uv pip install --no-cache uvicorn[standard]

# ── Stage 2: Production runtime ──────────────────────────────────────
FROM python:3.12-slim-bookworm

# Security: run as non-root
RUN groupadd -r stonks && useradd -r -g stonks stonks

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY packages/backend/src/ /app/src/
COPY packages/backend/alembic.ini /app/
COPY packages/backend/alembic/ /app/alembic/

# Set Python path
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER stonks

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "stonks_backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
