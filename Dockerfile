# ── RAG Agent — API & Worker ──────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies for PyMuPDF and other native libs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application source, configuration, and frontend
COPY pyproject.toml .
COPY rag_agent/ rag_agent/
COPY frontend/ frontend/
COPY alembic.ini .

# Install Python dependencies (requires source for hatchling wheel build)
RUN pip install --upgrade pip && \
    pip install .

# Create media directory
RUN mkdir -p /data/media

EXPOSE 8100

# Default: run the API server
CMD ["uvicorn", "rag_agent.app:create_app", "--host", "0.0.0.0", "--port", "8100", "--factory"]
