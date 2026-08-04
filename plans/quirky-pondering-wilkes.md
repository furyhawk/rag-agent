# RAG-Agent: Production-Grade Document Ingestion Service

## Context

You have a mature RAG system in **agent_alpha** (`/home/user/projects/agent_alpha/backend/services/rag/`) with Milvus, multi-format parsing, hybrid search, and cross-encoder reranking. The **rag-agent** project is greenfield — this plan extracts agent_alpha's battle-tested patterns into a standalone, production-grade ingestion service that any pydantic-deepagents agent can call via HTTP API.

**Key improvements over agent_alpha**: ARQ task queue (replacing `asyncio.create_task`), batched embedding with retry/backoff, fine-grained SSE progress events, structured logging via structlog, proper dependency injection, and a clean connector plugin system.

---

## Project Structure

```
rag-agent/
├── pyproject.toml
├── Dockerfile
├── Dockerfile.worker
├── docker-compose.yml
├── .env.example
├── alembic.ini
├── rag_agent/
│   ├── __init__.py
│   ├── app.py                    # FastAPI app factory + lifespan
│   ├── core/
│   │   ├── config.py             # pydantic-settings: Settings
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   ├── valkey.py             # Valkey client singleton
│   │   ├── exceptions.py         # Exception hierarchy
│   │   ├── logging.py            # structlog setup
│   │   └── deps.py               # FastAPI DI providers
│   ├── models/                   # Pydantic domain models
│   │   ├── document.py           # Document, DocumentPage, DocumentChunk, DocumentMetadata
│   │   ├── search.py             # SearchResult, SearchRequest
│   │   ├── ingestion.py          # IngestionStatus, IngestionProgress
│   │   ├── collection.py         # CollectionInfo
│   │   └── common.py             # DocumentInfo, PaginationParams
│   ├── db/                       # SQLAlchemy ORM + Alembic
│   │   ├── base.py
│   │   ├── models/
│   │   │   ├── document.py       # TrackedDocument (adds retry_count, content_hash, indexes)
│   │   │   └── sync_log.py       # SyncLog
│   │   └── migrations/
│   ├── repositories/
│   │   ├── document_repo.py      # TrackedDocument CRUD
│   │   └── sync_log_repo.py
│   ├── parsers/                  # Strategy pattern (from agent_alpha/services/rag/documents.py)
│   │   ├── base.py               # BaseDocumentParser ABC
│   │   ├── text.py               # .txt, .md
│   │   ├── docx.py               # .docx via python-docx
│   │   ├── pdf.py                # .pdf via PyMuPDF (text+tables+images+OCR)
│   │   └── registry.py           # PARSER_REGISTRY: ext -> parser
│   ├── chunkers/
│   │   ├── base.py               # BaseChunker ABC
│   │   ├── recursive.py          # RecursiveCharacterTextSplitter
│   │   └── markdown.py           # MarkdownHeaderTextSplitter
│   ├── embeddings/
│   │   ├── base.py               # BaseEmbeddingProvider ABC
│   │   ├── openai_compat.py      # OpenAI-compatible (works with vLLM/Ollama)
│   │   └── service.py            # EmbeddingService: batching + dim validation
│   ├── vectorstore/
│   │   ├── base.py               # BaseVectorStore ABC
│   │   ├── milvus.py             # MilvusVectorStore (AsyncMilvusClient)
│   │   └── service.py            # Collection lifecycle, metadata building
│   ├── rerankers/
│   │   ├── base.py               # BaseReranker ABC
│   │   ├── cross_encoder.py      # CrossEncoder (ms-marco-MiniLM-L6-v2)
│   │   └── service.py            # RerankService orchestrator
│   ├── connectors/               # Plugin system (from agent_alpha/rag/connectors.py)
│   │   ├── base.py               # BaseConnector ABC + CONNECTOR_REGISTRY
│   │   └── local.py              # LocalFilesystemConnector
│   ├── pipeline/
│   │   ├── processor.py          # DocumentProcessor: parse -> describe -> chunk
│   │   ├── ingestion.py          # IngestionService: full pipeline with dedup
│   │   ├── image_describer.py    # LLM vision for extracted images
│   │   └── file_storage.py       # LocalFileStorage
│   ├── retrieval/
│   │   ├── service.py            # RetrievalService: vector -> BM25 -> rerank -> filter -> dedup
│   │   └── bm25.py               # BM25Okapi keyword search
│   ├── worker/
│   │   ├── settings.py           # ARQ WorkerSettings
│   │   ├── tasks.py              # ingest_document_task, sync_collection_task
│   │   └── dispatcher.py         # Enqueue wrapper
│   ├── routes/
│   │   ├── health.py             # /health, /ready, /live
│   │   ├── collections.py        # /api/v1/collections CRUD
│   │   ├── documents.py          # /api/v1/documents: upload, list, get, delete, retry
│   │   ├── search.py             # /api/v1/search
│   │   ├── sync.py               # /api/v1/sync
│   │   ├── connectors.py         # /api/v1/connectors
│   │   └── status.py             # /api/v1/status (SSE)
│   ├── schemas/                  # API wire-format models
│   │   ├── document.py
│   │   ├── collection.py
│   │   ├── search.py
│   │   ├── sync.py
│   │   └── common.py             # ErrorResponse, PaginatedResponse
│   └── services/
│       ├── document_service.py   # Document lifecycle orchestration
│       ├── sync_service.py       # Sync orchestration
│       └── status_service.py     # SSE via Valkey pub/sub
├── tests/
│   ├── conftest.py
│   ├── unit/                     # No external deps
│   ├── integration/              # Requires Docker services
│   └── api/                      # FastAPI TestClient
└── scripts/
    ├── wait_for_services.py
    └── seed_test_data.py
```

---

## Ingestion Pipeline

```
Upload -> Validate -> Store File -> DB Track (queued) -> ARQ Enqueue
  ┌─── ARQ Worker ───────────────────────────────────────────────┐
  │ [1] Parse     — Route to parser by ext (PyMuPDF/docx/text)   │
  │ [2] Describe  — LLM vision for extracted images (optional)    │
  │ [3] Chunk     — RecursiveCharacter or Markdown splitter        │
  │ [4] Dedup     — Check by source_path then content_hash (SHA-256)│
  │ [5] Embed     — Batched OpenAI-compatible API (100/batch)      │
  │ [6] Store     — Milvus insert + flush                          │
  │ [7] Complete  — DB update (status=done, chunk_count=N)         │
  └──────────────────────────────────────────────────────────────┘
Each stage emits IngestionProgress to Valkey pub/sub -> SSE stream
```

**Improvements over agent_alpha**:
- **Batched embedding**: agent_alpha sends all chunks in one call — new design batches at 100
- **Retry with backoff**: 3 retries, 1s base / 30s max delay on all external calls
- **Fine-grained progress**: `QUEUED → PARSING → CHUNKING → EMBEDDING → STORING → DONE` (agent_alpha only has coarse `PROCESSING/ADDING/DONE`)
- **Indexed dedup**: DB index on `content_hash` instead of linear scan

---

## Retrieval Pipeline

```
Query -> Embed -> Milvus cosine search (limit × fetch_multiplier)
  -> [optional] BM25 + RRF fusion (k=60)
  -> [optional] CrossEncoder rerank
  -> Score filter (min_score)
  -> Dedup (per parent_doc_id:chunk_num)
  -> Truncate to limit
```

Multi-collection search runs each collection independently, tags results with `collection` metadata, merges and deduplicates.

---

## API Design

All endpoints prefixed with `/api/v1/`. JSON envelope: `{"data": ...}` / `{"error": "...", "details": {...}}`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness (always 200) |
| GET | `/ready` | Readiness (checks Milvus, PG, Valkey) |
| POST | `/api/v1/documents/upload` | Upload file (multipart) |
| POST | `/api/v1/documents/upload/{collection}` | Upload to specific collection |
| GET | `/api/v1/documents` | List tracked documents (filterable) |
| GET | `/api/v1/documents/{id}` | Document detail |
| DELETE | `/api/v1/documents/{id}` | Cascade delete (DB + Milvus + file) |
| POST | `/api/v1/documents/{id}/retry` | Re-queue failed ingestion |
| GET | `/api/v1/documents/{id}/download` | Download original file |
| GET | `/api/v1/collections` | List collections |
| POST | `/api/v1/collections?name=...` | Create collection |
| GET | `/api/v1/collections/{name}` | Collection stats |
| DELETE | `/api/v1/collections/{name}` | Drop collection |
| POST | `/api/v1/search` | Vector search |
| POST | `/api/v1/search/multi` | Multi-collection search |
| POST | `/api/v1/sync` | Trigger directory sync |
| GET | `/api/v1/sync/logs` | Sync history |
| GET | `/api/v1/connectors` | List available connectors |
| GET | `/api/v1/status` | SSE stream for ingestion progress |

---

## Infrastructure (Docker Compose)

| Service | Image | Port | Role |
|---------|-------|------|------|
| `api` | Custom (Python 3.12) | 8100 | FastAPI application |
| `worker` | Same image | — | ARQ worker process |
| `postgres` | `postgres:16-alpine` | 5433 | Document tracking DB |
| `valkey` | `valkey/valkey:8-alpine` | 6379 | Cache + pub/sub + ARQ queue |
| `milvus` | `milvusdb/milvus:v2.5.4` | 19530 | Vector database (standalone) |
| `milvus-etcd` | `quay.io/coreos/etcd:v3.5.18` | 2379 | Milvus metadata |
| `milvus-minio` | `minio/minio:latest` | 9000 | Milvus object storage |

Shared volumes: `media_data` (uploaded files), `model_cache` (sentence-transformers models), `postgres_data`, `milvus_data`.

---

## ARQ Worker Config

```python
class WorkerSettings:
    functions = [ingest_document_task, sync_collection_task]
    max_jobs = 4           # concurrent ingestion tasks
    job_timeout = 600      # 10 min per document
    retry_jobs = True
    max_tries = 3
    # on_startup: build IngestionService singleton in worker process
    # on_job_start: bind structlog context (job_id, doc_id)
```

---

## DB Schema Improvements (over agent_alpha)

`tracked_documents` table adds:
- `retry_count: int` (default 0) — tracks ARQ retries
- `last_error: str | None` — most recent error message
- `source_type: str` — local/s3/gdrive/web (for connector expansion)
- `content_hash: str` — SHA-256 for dedup queries
- Indexes on `(collection_name, status)`, `(content_hash,)`, `(source_path,)`

---

## pydantic-deepagents Integration

A thin `RAGAgentClient` (httpx-based) wraps the API. A `create_rag_toolset()` factory produces a pydantic-ai `FunctionToolset` with tools:
- `rag_search(query, collection, limit)` — search the knowledge base
- `rag_upload(file_path, collection)` — upload a document
- `rag_status(doc_id)` — check ingestion status
- `rag_list_collections()` — list available collections

Agents pass this toolset to `create_deep_agent(toolsets=[create_rag_toolset("http://rag-agent:8100")])`.

---

## Key Dependencies

```
fastapi, uvicorn[standard], python-multipart
pydantic, pydantic-settings
sqlalchemy[asyncio], asyncpg, alembic
redis (Valkey protocol), arq
pymilvus, pymupdf, python-docx
langchain-text-splitters, openai (compatible client)
sentence-transformers, rank-bm25
structlog, httpx
```

---

## Implementation Order

1. **Foundation** (config, models, DB, Docker Compose infra, health endpoints)
2. **Parsing + Chunking** (parsers, chunkers, DocumentProcessor, unit tests)
3. **Embedding + Vector Store** (OpenAI-compat provider, Milvus adapter, integration test)
4. **Ingestion Pipeline** (IngestionService, file storage, document API routes)
5. **Task Queue** (ARQ worker, task definitions, worker Dockerfile)
6. **Search + Retrieval** (RetrievalService, BM25, reranker, search routes)
7. **Status + Sync** (SSE streaming, local connector, sync routes)
8. **Hardening** (retry/backoff, graceful degradation, input validation, integration tests, pydantic-deepagents client library)

---

## Source Files to Extract From

| rag-agent module | agent_alpha source |
|---|---|
| `parsers/pdf.py` | `backend/services/rag/documents.py` (PyMuPDFParser class) |
| `parsers/docx.py`, `text.py` | `backend/services/rag/documents.py` (DocxDocumentParser, TextDocumentParser) |
| `chunkers/recursive.py` | `backend/services/rag/documents.py` (`_create_splitter`) |
| `embeddings/openai_compat.py` | `backend/services/rag/embeddings.py` (OpenAIEmbeddingProvider) |
| `vectorstore/milvus.py` | `backend/services/rag/vectorstore.py` (MilvusVectorStore) |
| `retrieval/service.py` | `backend/services/rag/retrieval.py` (RetrievalService) |
| `rerankers/cross_encoder.py` | `backend/services/rag/reranker.py` (CrossEncoderReranker) |
| `pipeline/ingestion.py` | `backend/services/rag/ingestion.py` (IngestionService) |
| `pipeline/image_describer.py` | `backend/services/rag/image_describer.py` (PydanticAIImageDescriber) |
| `connectors/base.py` | `backend/rag/connectors.py` (BaseConnector + CONNECTOR_REGISTRY) |
| `db/models/document.py` | `backend/db/models/rag_document.py` (RAGDocument) |
| `services/status_service.py` | `backend/services/rag_status.py` (SSE streaming) |
| `worker/tasks.py` | `backend/worker/tasks/rag_tasks.py` (task functions) |
| `core/config.py` | `backend/services/rag/config.py` (RAGSettings, EMBEDDING_DIMENSIONS) |

---

## Verification

1. `docker-compose up` — all 7 services healthy
2. `curl http://localhost:8100/ready` — all dependency checks pass
3. Upload a PDF: `curl -X POST http://localhost:8100/api/v1/documents/upload -F "file=@test.pdf"`
4. Monitor SSE: `curl -N http://localhost:8100/api/v1/status` — see progress events
5. Verify in DB: `GET /api/v1/documents` — document shows status=done with chunk_count
6. Search: `POST /api/v1/search` with a query about the PDF content — get relevant chunks back
7. Run test suite: `pytest tests/ -v`
