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
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
DOCKER_IMAGE ?= docker.io/your-org/verity-rag
DOCKER_TAG ?= $(shell date +%Y%m%d-%H%M%S)

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
	@echo "setup         - Install Python dependencies with uv"
	@echo "setup-local-ml - Install optional local embedding/reranker ML deps"
	@echo "setup-local-omni - Install local omni embedding deps (jina v5 omni)"
	@echo "test          - Run test suite"
	@echo "lint          - Run linters (ruff)"
	@echo "format        - Format code (ruff format)"
	@echo "typecheck     - Run type checking (mypy)"
	@echo ""
	@echo "── Container Stack ───────────────────────────────────────────"
	@echo "up            - Start full container stack"
	@echo "up-local-ml   - Start stack with worker local-ml only (api lean)"
	@echo "up-local-ml-full - Start stack with local-ml for both api and worker"
	@echo "down          - Stop container stack"
	@echo "down-local-ml - Stop stack launched with local-ml override"
	@echo "logs          - Show service logs"
	@echo "logs-local-ml - Show logs for stack launched with local-ml override"
	@echo "ps            - Show running containers"
	@echo "ps-local-ml   - Show containers for stack launched with local-ml override"
	@echo ""
	@echo "── Dev-Fast (no app containers) ─────────────────────────────"
	@echo "dev-up        - Start ONLY data infra (Postgres, Valkey, Milvus)"
	@echo "dev-down      - Stop data infra containers"
	@echo "dev-logs      - Show data infra logs"
	@echo "dev-fast      - Run API directly with hot-reload + .env.dev"
	@echo "dev-fast-worker - Run worker directly with .env.dev"
	@echo "dev-migrate   - Run Alembic migrations against local infra"
	@echo "dev-create-tables - Create tables directly (no Alembic)"
	@echo "dev-reset-docs - Clear all documents (dev env)"
	@echo "dev-reset-docs-force - Clear all documents with CASCADE"
	@echo "dev-setup     - Create media dir + run migrations"
	@echo ""
	@echo "── Build & Publish ──────────────────────────────────────────"
	@echo "build         - Build Python package (wheel + sdist)"
	@echo "publish       - Build + publish to PyPI"
	@echo "publish-docker - Build + publish multi-arch image (amd64+arm64)"
	@echo ""
	@echo "── Local Commands ───────────────────────────────────────────"
	@echo "worker        - Start ARQ worker (outside Docker)"
	@echo "run           - Start API server (outside Docker)"
	@echo "migrate       - Run Alembic migrations"
	@echo "migrate-container - Run Alembic migrations inside API container"
	@echo "wait          - Wait for services to be ready"
	@echo "reset-docs    - Clear all documents from DB, Milvus, and queues"
	@echo "reset-docs-force - Same + CASCADE truncation"
	@echo "clean         - Clean build artifacts and __pycache__"
	@echo ""
	@echo "── Shell Access ─────────────────────────────────────────────"
	@echo "shell         - Open shell in API container"
	@echo "db-shell      - Open PostgreSQL shell (container)"
	@echo "valkey-cli    - Open Valkey CLI (container)"
	@echo "milvus-cli    - Open Milvus CLI (container)"
	@echo "──────────────────────────────────────────────────────────────"
	@echo "Example: make dev-up && make dev-setup && make dev-fast"

# ── Python Dependencies ──────────────────────────────────────────
setup:
	@echo "📦 Installing Python dependencies with uv..."
	uv sync --extra dev

setup-local-ml:
	@echo "🧠 Installing optional local ML dependencies..."
	uv sync --extra dev --extra local-ml

setup-local-omni:
	@echo "🧠 Installing local omni embedding deps (jina-embeddings-v5-omni)..."
	uv sync --extra dev --extra local-ml

.PHONY: setup setup-local-ml setup-local-omni

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

up-local-ml:
	@echo "🐳 Starting stack with worker local-ml only (api lean)..."
	LOCAL_ML_API=false LOCAL_ML_WORKER=true COMPOSE_PARALLEL_LIMIT=1 \
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local-ml.yml up -d --build

up-local-ml-full:
	@echo "🐳 Starting stack with local-ml for api and worker..."
	LOCAL_ML_API=true LOCAL_ML_WORKER=true COMPOSE_PARALLEL_LIMIT=1 \
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local-ml.yml up -d --build

down:
	@echo "⏹️  Stopping container stack..."
	$(COMPOSE) down

down-local-ml:
	@echo "⏹️  Stopping local-ml override container stack..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local-ml.yml down

logs:
	@echo "📋 Showing service logs..."
	$(COMPOSE) logs -f --tail=100

logs-local-ml:
	@echo "📋 Showing local-ml override service logs..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local-ml.yml logs -f --tail=100

ps:
	@echo "📋 Showing running containers..."
	$(COMPOSE) ps

ps-local-ml:
	@echo "📋 Showing running containers (local-ml override)..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local-ml.yml ps

.PHONY: up up-local-ml up-local-ml-full down down-local-ml logs logs-local-ml ps ps-local-ml

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

migrate-container:
	@echo "🔄 Running database migrations inside API container..."
	$(COMPOSE) exec api alembic upgrade head

wait:
	@echo "⏳ Waiting for services to be ready..."
	python scripts/wait_for_services.py

reset-docs:
	@echo "🗑️  Clearing all documents from DB, Milvus, and Valkey..."
	uv run python scripts/reset_documents.py

reset-docs-force:
	@echo "🗑️  Force-clearing all documents (CASCADE truncation)..."
	uv run python scripts/reset_documents.py --force

.PHONY: run worker migrate migrate-container wait reset-docs reset-docs-force

# ── Dev-Fast (data infra in containers, app on host) ─────────────
DEV_COMPOSE_SERVICES := postgres valkey milvus-etcd milvus-minio milvus

dev-up:
	@echo "🐳 Starting data infrastructure (Postgres, Valkey, Milvus)..."
	$(COMPOSE) up -d $(DEV_COMPOSE_SERVICES)
	@echo ""
	@echo "⏳ Waiting for services to be ready..."
	@$(MAKE) wait 2>/dev/null || echo "⚠️  wait script may fail if API not running; check 'make dev-logs'"
	@echo ""
	@echo "📋 Next steps:"
	@echo "   make dev-setup    # create media dir + run migrations"
	@echo "   make dev-fast     # start API with hot-reload"

dev-down:
	@echo "⏹️  Stopping data infrastructure..."
	$(COMPOSE) down

dev-logs:
	@echo "📋 Showing data infra logs..."
	$(COMPOSE) logs -f --tail=100 $(DEV_COMPOSE_SERVICES)

# Helper: source .env.dev directly so variables are set in the current shell.
# This avoids glob-expansion issues with values like CORS_ORIGINS=["*"].
# (set -a ensures all sourced variables are exported to the environment)
DEV_ENV := set -a; . .env.dev; set +a;

dev-setup:
	@echo "📁 Creating local media directory..."
	@mkdir -p .dev-media
	@echo "🔄 Running database migrations..."
	$(DEV_ENV) uv run alembic upgrade head
	@echo "✅ Dev environment ready!"

dev-migrate:
	@echo "🔄 Running database migrations..."
	$(DEV_ENV) uv run alembic revision --autogenerate -m "Auto-generated migration"
	$(DEV_ENV) uv run alembic upgrade head

dev-create-tables:
	@echo "🏗️  Creating database tables directly..."
	$(DEV_ENV) uv run python scripts/create_tables.py

dev-reset-docs:
	@echo "🗑️  Clearing all documents from DB, Milvus, and Valkey (dev)..."
	$(DEV_ENV) uv run python scripts/reset_documents.py

dev-reset-docs-force:
	@echo "🗑️  Force-clearing all documents (dev, CASCADE)..."
	$(DEV_ENV) uv run python scripts/reset_documents.py --force

dev-fast: dev-setup
	@echo "🚀 Starting API server (hot-reload, no container)..."
	$(DEV_ENV) uv run uvicorn rag_agent.app:create_app \
		--reload \
		--factory \
		--host 0.0.0.0 \
		--port 8100

dev-fast-worker: dev-setup
	@echo "⚡ Starting ARQ worker (no container)..."
	$(DEV_ENV) uv run arq rag_agent.worker.settings.WorkerSettings

.PHONY: dev-up dev-down dev-logs dev-setup dev-migrate dev-create-tables dev-reset-docs dev-reset-docs-force dev-fast dev-fast-worker

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

# ── Build & Publish ───────────────────────────────────────────────
build:
	@echo "📦 Building Python package (wheel + sdist)..."
	rm -rf dist/ && uv build

publish: build
	@echo "🚀 Publishing to PyPI..."
	uv publish

publish-docker:
	@echo "🐳 Building and publishing multi-arch image for $(DOCKER_PLATFORMS)..."
	@echo "📌 Image: $(DOCKER_IMAGE)"
	@echo "🏷️  Tag: $(DOCKER_TAG)"
	@if [ "$(DOCKER_IMAGE)" = "docker.io/your-org/verity-rag" ]; then \
		echo "ERROR: Set DOCKER_IMAGE to your registry path, e.g. DOCKER_IMAGE=docker.io/<user-or-org>/verity-rag"; \
		exit 1; \
	fi
	@if [ "$(CONTAINER_RUNTIME)" = "docker" ]; then \
		docker buildx inspect rag-agent-multiarch >/dev/null 2>&1 || docker buildx create --name rag-agent-multiarch --use; \
		docker buildx use rag-agent-multiarch; \
		docker buildx build \
			--platform $(DOCKER_PLATFORMS) \
			-t $(DOCKER_IMAGE):latest \
			-t $(DOCKER_IMAGE):$(DOCKER_TAG) \
			--push \
			.; \
	elif [ "$(CONTAINER_RUNTIME)" = "podman" ]; then \
		podman build \
			--platform $(DOCKER_PLATFORMS) \
			--manifest $(DOCKER_IMAGE):$(DOCKER_TAG) \
			.; \
		podman manifest push --all $(DOCKER_IMAGE):$(DOCKER_TAG) docker://$(DOCKER_IMAGE):$(DOCKER_TAG); \
		podman manifest push --all $(DOCKER_IMAGE):$(DOCKER_TAG) docker://$(DOCKER_IMAGE):latest; \
	else \
		echo "ERROR: Unsupported CONTAINER_RUNTIME=$(CONTAINER_RUNTIME)"; \
		exit 1; \
	fi

.PHONY: build publish publish-docker

# ── Clean ────────────────────────────────────────────────────────
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache dist/

.PHONY: clean

# ── Default Target ────────────────────────────────────────────────
.DEFAULT_GOAL := help