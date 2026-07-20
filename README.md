# RAG Agent

Production-grade, self-hosted document ingestion and retrieval service.

## Features

- **Multi-format parsing**: PDF, DOCX, TXT, Markdown with smart layout preservation
- **Chunking strategies**: Recursive character, Markdown headers
- **Image extraction and LLM description**: Makes visual content searchable
- **OCR fallback**: LLM vision for scanned pages
- **Vector storage**: Milvus with cosine similarity search
- **Hybrid retrieval**: BM25 keyword search + vector fusion (RRF)
- **Cross-encoder reranking**: Sentence Transformers for relevance scoring
- **ARQ task queue**: Background processing with retry and backoff
- **SSE status streaming**: Real-time ingestion progress
- **Pluggable connectors**: Local filesystem (ready), S3/Google Drive (pluggable)
- **Deduplication**: Content hash + source path matching
- **Batched embedding**: Configurable batch size with retry
- **Web dashboard**: Responsive dark-themed UI for all operations
- **uv Python manager**: Fast dependency installation and management
- **Makefile**: Simplified task management

## Architecture

```
Upload → Validate → Store → Track (DB) → Queue (ARQ)
  ┌─── Worker ───────────────────────────────────────┐
  │ Parse → Describe images → Chunk → Dedup → Embed → Store (Milvus)
  └──────────────────────────────────────────────────┘
                ↓
          SSE Status Events
                ↓
           Query → Search
                ↓
          Web Dashboard  ←── You are here
```

## Web UI

The project includes a responsive dark-themed web dashboard built with Vue 3
(served as static files from the FastAPI application).

**Pages:**

| Page | Description |
|------|-------------|
| **Dashboard** | System health, collection stats, recent documents |
| **Documents** | Upload (drag & drop), list/filter, delete, retry, download |
| **Collections** | Create, browse, delete vector collections |
| **Search** | Semantic search with reranker, multi-collection mode, score visualization |

**Access the UI at** [`http://localhost:8100/`](http://localhost:8100/) (redirects to `/ui/`).

The frontend is served directly by the API server — no separate build step or
dev server needed. Source lives in the `frontend/` directory.

## Quick Start

### Using uv and Make

```bash
# Install uv (https://github.com/astral-sh/uv)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or create the project
cd /home/user/projects/rag-agent

# Install dependencies with uv
make setup

# Create .env from example
cp .env.example .env
# Edit .env with your settings

# Start the stack
make up

# Wait for services to be ready
make wait

# Upload a document
curl -X POST http://localhost:8100/api/v1/documents/upload \
  -F "file=@example.pdf"

# Search
curl -X POST http://localhost:8100/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue?", "limit": 5}'
```

### Manual uv Commands

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Start API server
uv run uvicorn rag_agent.app:create_app --reload --factory

# Start ARQ worker
uv run arq rag_agent.worker.settings.WorkerSettings
```

## API Endpoints

### Health
- `GET /health` — Liveness
- `GET /ready` — Readiness with dependency checks
- `GET /live` — Minimal liveness

### Collections
- `GET /api/v1/collections` — List collections
- `POST /api/v1/collections?name=...` — Create collection
- `GET /api/v1/collections/{name}` — Collection stats
- `DELETE /api/v1/collections/{name}` — Drop collection

### Documents
- `POST /api/v1/documents/upload` — Upload file (multipart)
- `GET /api/v1/documents` — List tracked documents
- `GET /api/v1/documents/{id}` — Document detail
- `DELETE /api/v1/documents/{id}` — Delete (cascade)
- `POST /api/v1/documents/{id}/retry` — Re-queue failed ingestion
- `GET /api/v1/documents/{id}/download` — Download original

### Search
- `POST /api/v1/search` — Vector search
- `POST /api/v1/search/multi` — Multi-collection search
- `GET /api/v1/collections/{name}/documents/{id}` — Search within a document

### Sync & Connectors
- `POST /api/v1/sync` — Trigger directory sync
- `GET /api/v1/sync/logs` — Sync history
- `GET /api/v1/connectors` — Available connectors
- `GET /api/v1/status` — SSE stream for progress events

## Configuration

See `.env.example` for all environment variables.

Key settings:
- `EMBEDDING_BASE_URL` — OpenAI-compatible embedding endpoint
- `EMBEDDING_MODEL` — Model name (e.g., `all-MiniLM-L6-v2`)
- `MILVUS_URI` — Milvus connection
- `CHUNK_SIZE`, `CHUNK_OVERLAP` — Text chunking
- `ENABLE_HYBRID_SEARCH` — BM25 + vector fusion
- `ENABLE_IMAGE_DESCRIPTION` — LLM vision for images

## Development Tasks

The project includes a comprehensive Makefile for common tasks:

```bash
# Show available tasks
make

# Install dependencies
make setup

# Run tests
make test

# Lint code
make lint

# Format code
make format

# Type checking
make typecheck

# Start Docker stack
make up

# Wait for services
make wait

# Start API server (outside Docker)
make run

# Start ARQ worker (outside Docker)
make worker

# Run database migrations
make migrate

# Clean build artifacts
make clean
```

## Integration with pydantic-deepagents

```python
from rag_agent.client import RAGAgentClient

client = RAGAgentClient(base_url="http://localhost:8100")

# Upload
result = await client.upload_document("report.pdf")

# Search
results = await client.search("quarterly earnings")
```

## Requirements

- **uv** (https://github.com/astral-sh/uv) - Modern Python package installer and resolver
- **Docker** and **Docker Compose** - For running the stack
- **Python 3.12+** - Runtime environment

## License

MIT