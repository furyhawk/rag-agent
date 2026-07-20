# ── RAG Agent Makefile ───────────────────────────────────────────
# Common tasks for development and deployment
# Requires: Podman or Docker (with compose), uv (https://github.com/astral-sh/uv)

SHELL := /bin/bash
export PYTHONPATH := $(PWD)

# ── Container Runtime ────────────────────────────────────────────
# Auto-detect: prefers podman, falls back to docker.
# Override with:  make CONTAINER_RUNTIME=docker up
CONTAINER_RUNTIME ?= $(shell if command -v podman &>/dev/null; then echo podman; elif command -v docker &>/dev/null; then echo docker; else echo docker; fi)
COMPOSE := $(CONTAINER_RUNTIME) compose

# ── Environment ──────────────────────────────────────────────────
ifeq ($(shell uname -s),Darwin)
	USER_ID := 501
	GROUP_ID := 20
else
	USER_ID := $(shell id -u)
	GROUP_ID := $(shell id -g)
endif

# ── Help ────────────────────────────────────────────────────────
help:
	@echo "RAG Agent Development Tasks"
	@echo "──────────────────────────────────────────────────────────────"
	@echo "setup       - Install Python dependencies with uv"
	@echo "test        - Run test suite"
	@echo "lint        - Run linters (ruff)"
	@echo "format      - Format code (ruff format)"
	@echo "typecheck   - Run type checking (mypy)"
	@echo "up          - Start container stack (podman or docker)"
	@echo "down        - Stop container stack"
	@echo "logs        - Show service logs"
	@echo "ps          - Show running containers"
	@echo "worker      - Start ARQ worker (outside Docker)"
	@echo "run         - Start API server (outside Docker)"
	@echo "migrate     - Run Alembic migrations"
	@echo "wait        - Wait for services to be ready"
	@echo "clean       - Clean build artifacts and __pycache__"
	@echo "shell       - Open shell in API container"
	@echo "db-shell    - Open PostgreSQL shell"
	@echo "valkey-cli  - Open Valkey CLI"
	@echo "milvus-cli  - Open Milvus CLI"
	@echo "──────────────────────────────────────────────────────────────"
	@echo "Example: make setup && make up && make wait"

# ── Python Dependencies ──────────────────────────────────────────
setup:
	@echo "📦 Installing Python dependencies with uv..."
	uv sync --all-extras

.PHONY: setup

# ── Testing ──────────────────────────────────────────────────────
test:
	@echo "🧪 Running test suite..."
	uv run pytest tests/ -v

.PHONY: test

# ── Linting and Formatting ───────────────────────────────────────
lint:
	@echo "🔍 Running linters..."
	uv run ruff check .

format:
	@echo "✏️  Formatting code..."
	uv run ruff format .

typecheck:
	@echo "✅ Running type checking..."
	uv run mypy rag_agent/

.PHONY: lint format typecheck

# ── Container Stack ──────────────────────────────────────────────
up:
	@echo "🐳 Starting container stack with $(CONTAINER_RUNTIME)..."
	$(COMPOSE) up -d

down:
	@echo "⏹️  Stopping container stack..."
	$(COMPOSE) down

logs:
	@echo "📋 Showing service logs..."
	$(COMPOSE) logs -f --tail=100

ps:
	@echo "📋 Showing running containers..."
	$(COMPOSE) ps

.PHONY: up down logs ps

# ── Development ──────────────────────────────────────────────────
run:
	@echo "🚀 Starting API server..."
	uv run uvicorn rag_agent.app:create_app --reload --factory --host 0.0.0.0 --port 8100

worker:
	@echo "⚡ Starting ARQ worker..."
	uv run arq rag_agent.worker.settings.WorkerSettings

migrate:
	@echo "🔄 Running database migrations..."
	uv run alembic revision --autogenerate -m "Auto-generated migration"
	uv run alembic upgrade head

wait:
	@echo "⏳ Waiting for services to be ready..."
	python scripts/wait_for_services.py

.PHONY: run worker migrate wait

# ── Shell Access ─────────────────────────────────────────────────
shell:
	@echo "🐚 Opening shell in API container..."
	$(COMPOSE) exec api bash

db-shell:
	@echo "🐘 Opening PostgreSQL shell..."
	$(COMPOSE) exec postgres psql -U rag rag

valkey-cli:
	@echo "⚡ Opening Valkey CLI..."
	$(COMPOSE) exec valkey valkey-cli

milvus-cli:
	@echo "🔍 Opening Milvus CLI..."
	$(COMPOSE) exec milvus milvus_cli

.PHONY: shell db-shell valkey-cli milvus-cli

# ── Clean ────────────────────────────────────────────────────────
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache

.PHONY: clean

# ── Default Target ────────────────────────────────────────────────
.DEFAULT_GOAL := help