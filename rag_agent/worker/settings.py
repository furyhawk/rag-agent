"""Worker settings and task definitions for ARQ."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from arq.connections import RedisSettings

from rag_agent.core.config import get_settings
from rag_agent.core.logging import get_logger, setup_logging

# Initialize structured logging for the worker process
settings = get_settings()
setup_logging(level=settings.log_level, log_format=settings.log_format)

logger = get_logger(__name__)


async def _noop_job(ctx) -> None:
    """Placeholder job so the ARQ worker can start without errors.

    This will be replaced by real task implementations (e.g. document
    ingestion, embedding generation) as they are developed.  It can be
    enqueued via ``TaskDispatcher.enqueue("_noop_job")`` for smoke-test
    purposes.
    """
    logger.info("noop job executed, ctx=%s", ctx)


async def process_document(
    ctx: dict,
    doc_id: str,
    collection_name: str,
    storage_path: str,
    filename: str,
) -> dict:
    """Process a document: chunk, embed, and store in vector database.

    Args:
        ctx: Job context from ARQ.
        doc_id: UUID of the TrackedDocument record.
        collection_name: Target Milvus collection.
        storage_path: Path to the stored file.
        filename: Original filename.

    Returns:
        dict with status and document_id.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from rag_agent.db.base import Base
    from rag_agent.db.models import TrackedDocument
    from rag_agent.pipeline.ingestion import IngestionService
    from rag_agent.core.config import get_settings

    settings = get_settings()

    # Create async engine and session
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Update status to processing
            doc = await session.get(TrackedDocument, doc_id)
            if not doc:
                logger.error("Document not found: %s", doc_id)
                return {"status": "error", "message": f"Document {doc_id} not found"}

            doc.status = "processing"
            await session.commit()
            logger.info("Processing document: %s (%s)", filename, doc_id)

            # Build ingestion service
            ingestion = IngestionService.build(
                settings=settings.rag,
                milvus_uri=settings.milvus_uri,
                milvus_token=settings.milvus_token or "",
                embedding_api_key=settings.embedding_api_key or "",
                embedding_base_url=settings.embedding_base_url or "",
                models_cache_dir=str(settings.models_cache_dir),
            )

            # Process the file
            filepath = Path(storage_path)
            result = await ingestion.ingest_file(
                filepath=filepath,
                collection_name=collection_name,
                replace=True,
                source_path=storage_path,
            )

            # Update document status
            if result.status.value == "done":
                doc.status = "done"
                doc.vector_document_id = result.document_id
                doc.chunk_count = result.chunk_count
                doc.completed_at = doc.created_at
                logger.info(
                    "Document processed successfully: %s, chunks: %d",
                    doc_id,
                    result.chunk_count,
                )
            else:
                doc.status = "error"
                doc.error_message = result.message
                logger.error("Document processing failed: %s - %s", doc_id, result.message)

            await session.commit()

            return {
                "status": result.status.value,
                "document_id": result.document_id,
                "chunk_count": result.chunk_count,
                "message": result.message,
            }

        except Exception as e:
            logger.exception("Unexpected error processing document %s: %s", doc_id, e)
            # Try to update status to error
            try:
                doc = await session.get(TrackedDocument, doc_id)
                if doc:
                    doc.status = "error"
                    doc.error_message = str(e)
                    await session.commit()
            except Exception:
                pass
            return {"status": "error", "message": str(e)}
        finally:
            await engine.dispose()


def _get_redis_settings() -> RedisSettings:
    """Parse RedisSettings from VALKEY_URL environment variable."""
    valkey_url = os.environ.get("VALKEY_URL", "redis://localhost:6379/0")
    parsed = urlparse(valkey_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or 0),
    )


class WorkerSettings:
    """ARQ worker configuration."""

    functions: list = [_noop_job, process_document]
    redis_settings: RedisSettings | None = _get_redis_settings()
    max_jobs: int = 4
    job_timeout: int = 600  # 10 minutes per job
    retry_jobs: bool = True
    max_tries: int = 3
