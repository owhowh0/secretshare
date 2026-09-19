# syntax=docker/dockerfile:1.7

# -----------------------------------------------------------------------------
# Stage 1: Dependency builder
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools if packages need compiling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment isolated in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY requirements.txt to maximize Docker layer cache hits
COPY requirements.txt .

# Install dependencies utilizing BuildKit pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Lean runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime dependencies (curl for healthcheck, libpq5 for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Standard Python production environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create unprivileged system user for container security (never run as root)
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --no-create-home appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code with non-root ownership. alembic.ini comes too:
# migrations run on every container start (see CMD).
COPY --chown=appuser:appgroup ./app /app/app
COPY --chown=appuser:appgroup ./alembic.ini /app/alembic.ini

# Drop root privileges
USER appuser

# Expose default HTTP port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Apply pending migrations, then launch FastAPI via uvicorn with proxy headers
# enabled (for reverse proxies like Traefik/Caddy). A failed migration stops the
# container instead of serving with a missing schema. exec makes uvicorn PID 1
# so it receives SIGTERM directly.
CMD ["sh", "-c", "python -m app.db.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
