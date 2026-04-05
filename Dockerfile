# ── AutiBloom Platform – Production Dockerfile ──────────────────────
FROM python:3.13-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by psycopg2 and general build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# ── Install Python dependencies ────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# ── Copy application code ──────────────────────────────────────────
COPY . .

# ── Copy and prepare entrypoint script ─────────────────────────────
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Switch to non-root user ────────────────────────────────────────
RUN chown -R appuser:appgroup /app
USER appuser

# ── Expose the port Gunicorn will listen on ────────────────────────
EXPOSE 8000

# ── Default entrypoint ─────────────────────────────────────────────
ENTRYPOINT ["/app/entrypoint.sh"]

