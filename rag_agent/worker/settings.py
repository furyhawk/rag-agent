"""Worker settings and task definitions for ARQ."""

from __future__ import annotations

import asyncio
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


def _release_ml_memory() -> None:
    """Drop process-global ML model refs and run a GC pass.

    Marker caches all its surya models in a module global
    (``rag_agent.parsers.pdf._model_dict``) for the life of the process, which
    pins the worker's RSS at its peak after the first heavy PDF. Clearing it
    between in-process jobs keeps the reachable set small (models are lazily
    reloaded on the next parse). Harmless when models were never loaded, and a
    no-op in subprocess mode where the models live in the child process.
    """
    import gc

    try:
        from rag_agent.parsers import pdf as pdf_module

        pdf_module.release_models()
    except Exception:
        logger.debug("model release skipped", exc_info=True)
    gc.collect()


async def _run_ingestion_in_subprocess(
    doc_id: str,
    collection_name: str,
    storage_path: str,
    filename: str,
) -> "IngestionResult":
    """Run ``ingest_file`` in a separate OS process and return its result.

    Parsing/embedding/inserting a document loads several GB of ML models
    (marker surya, sentence-transformers). Running that work in a child
    process means the memory is returned to the OS the moment the child exits
    — after a successful job, when the parent cancels it on the ARQ
    ``job_timeout``, or when the container memory limit OOM-kills it — instead
    of the long-lived ARQ worker pinning its peak RSS forever.

    The child is ``rag_agent.worker.ingest_runner``; results are exchanged via
    temp JSON files so library output on stdout/stderr can never corrupt them.
    """
    import asyncio
    import json
    import sys
    import tempfile
    import uuid
    from pathlib import Path

    from rag_agent.models.ingestion import IngestionResult, IngestionStatus

    token = uuid.uuid4().hex[:10]
    tmp = Path(tempfile.gettempdir())
    request_path = tmp / f"rag_ingest_{token}_request.json"
    result_path = tmp / f"rag_ingest_{token}_result.json"
    request_path.write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "collection_name": collection_name,
                "storage_path": storage_path,
                "filename": filename,
            }
        )
    )

    logger.info("ingest.subprocess_start", doc_id=doc_id, filename=filename)
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "rag_agent.worker.ingest_runner",
            "--request",
            str(request_path),
            "--result",
            str(result_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async def _pump(stream: asyncio.StreamReader | None) -> None:
            if stream is None:
                return
            async for raw in stream:
                line = raw.decode(errors="replace").rstrip()
                if line.strip():
                    logger.info("ingest.child", doc_id=doc_id, line=line)

        pump = asyncio.ensure_future(_pump(proc.stdout))
        try:
            await proc.wait()
        finally:
            pump.cancel()

        if proc.returncode not in (0, 1) or not result_path.exists():
            tail = (
                result_path.read_text(errors="replace")[-1000:]
                if result_path.exists()
                else "(child produced no result file)"
            )
            return IngestionResult(
                status=IngestionStatus.ERROR,
                document_id=doc_id,
                message=f"Subprocess failed for {filename}",
                error_message=(
                    f"Ingestion subprocess exited rc={proc.returncode}: {tail}"
                ),
            )

        payload = json.loads(result_path.read_text())
        if payload.get("ok"):
            return IngestionResult(**payload["result"])
        return IngestionResult(
            status=IngestionStatus.ERROR,
            document_id=doc_id,
            message=f"Subprocess failed for {filename}",
            error_message=payload.get("error") or "unknown subprocess error",
        )
    except asyncio.CancelledError:
        # ARQ job_timeout fired (or the worker is shutting down): kill the
        # child so its memory is reclaimed immediately rather than letting the
        # heavy job run to completion in the background.
        if proc is not None and proc.returncode is None:
            logger.warning(
                "ingest.subprocess_killed", doc_id=doc_id, filename=filename
            )
            proc.kill()
            await proc.wait()
        raise
    finally:
        for p in (request_path, result_path):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


def _create_worker_engine():
    """Create the ARQ worker's async engine.

    ``pool_pre_ping`` validates a pooled connection on checkout and
    transparently replaces one that Postgres or the network already dropped;
    ``pool_recycle`` proactively refreshes long-lived connections. Both matter
    here because an ingest job can keep the worker busy — and its connections
    idle — for up to ``job_timeout`` (an hour by default). Without them a stale
    connection is handed to the next statement and raises
    ``InterfaceError: connection is closed`` (see ``core.database``, which
    already sets ``pool_pre_ping`` for the API).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


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
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    from rag_agent.core.config import get_settings
    from rag_agent.db.models import TrackedDocument
    from rag_agent.models.ingestion import IngestionResult

    settings = get_settings()

    engine = _create_worker_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _write_status(
        *,
        status: str,
        error_message: str | None = None,
        vector_document_id: str | None = None,
        chunk_count: int | None = None,
        mark_completed: bool = False,
    ) -> bool:
        """Write a document's status on a fresh, short-lived session.

        Each call opens and closes its own session, so no connection is held
        across the long-running ingest. Retries once on a dropped connection:
        ``pool_pre_ping`` catches most stale connections at checkout, but one
        can still die between checkout and commit (e.g. the database restarted
        mid-job).
        """
        for attempt in range(2):
            try:
                async with async_session() as session:
                    doc = await session.get(TrackedDocument, doc_id)
                    if doc is None:
                        return False
                    doc.status = status
                    if error_message is not None:
                        doc.error_message = error_message
                    if vector_document_id is not None:
                        doc.vector_document_id = vector_document_id
                    if chunk_count is not None:
                        doc.chunk_count = chunk_count
                    if mark_completed:
                        doc.completed_at = doc.created_at
                    await session.commit()
                return True
            except Exception:
                if attempt == 1:
                    raise
                logger.warning(
                    "status write failed, retrying on a fresh connection",
                    doc_id=doc_id,
                    status=status,
                    exc_info=True,
                )
        return False

    try:
        # Mark the document as processing, then CLOSE the session before the
        # heavy work starts. Holding a session/connection open across an ingest
        # that can run for up to ``job_timeout`` (an hour by default) leaves it
        # idle long enough for Postgres or the network to close it, which then
        # breaks the final status write with "connection is closed".
        if not await _write_status(status="processing"):
            logger.error("Document not found: %s", doc_id)
            return {"status": "error", "message": f"Document {doc_id} not found"}
        logger.info("Processing document: %s (%s)", filename, doc_id)

        # Run the heavy parse/embed/insert work. By default it runs in a
        # killable subprocess so its memory is reclaimed when the job ends.
        # If subprocess mode is disabled it runs in-process and the ML models
        # are torn down between jobs to avoid ratcheting RSS.
        if settings.worker_run_in_subprocess:
            result: IngestionResult = await _run_ingestion_in_subprocess(
                doc_id=doc_id,
                collection_name=collection_name,
                storage_path=storage_path,
                filename=filename,
            )
        else:
            # NOTE: importing the ingestion pipeline pulls in the heavy ML
            # stack (torch/sentence-transformers/marker). It is imported ONLY
            # in this in-process branch so the long-lived ARQ parent stays
            # small in subprocess mode (the default).
            from rag_agent.pipeline.ingestion import build_ingestion_service

            ingestion = build_ingestion_service(settings)
            try:
                result = await ingestion.ingest_file(
                    filepath=Path(storage_path),
                    collection_name=collection_name,
                    replace=True,
                    source_path=storage_path,
                )
            finally:
                _release_ml_memory()

        # Update document status on a fresh connection.
        if result.status.value == "done":
            await _write_status(
                status="done",
                vector_document_id=result.document_id,
                chunk_count=result.chunk_count,
                mark_completed=True,
            )
            logger.info(
                "Document processed successfully: %s, chunks: %d",
                doc_id,
                result.chunk_count,
            )
        else:
            detailed_error = result.error_message or result.message
            await _write_status(status="error", error_message=detailed_error)
            logger.error(
                "Document processing failed: %s - %s",
                doc_id,
                detailed_error,
            )

        return {
            "status": result.status.value,
            "document_id": result.document_id,
            "chunk_count": result.chunk_count,
            "message": result.message,
        }

    except (Exception, asyncio.CancelledError) as e:
        # Catch asyncio.CancelledError (raised by ARQ on job timeout) so the
        # document status is always recorded instead of getting stuck in
        # "processing".
        is_timeout = isinstance(e, (TimeoutError, asyncio.CancelledError))
        if is_timeout:
            logger.error(
                "Document %s timed out after %ds: %s",
                doc_id, settings.worker_job_timeout, filename,
            )
        else:
            logger.exception("Unexpected error processing document %s: %s", doc_id, e)
        # Record the error on a fresh connection: the failure may itself have
        # been a dropped connection, and retrying reconnects transparently.
        try:
            await _write_status(
                status="error",
                error_message=(
                    f"Timeout after {settings.worker_job_timeout}s"
                    if is_timeout
                    else str(e)
                ),
            )
        except Exception:
            logger.exception("Failed to record error status for document %s", doc_id)
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
    max_jobs: int = settings.worker_max_jobs
    job_timeout: int = settings.worker_job_timeout
    # A document that exceeds ``job_timeout`` is a slow/heavy job, not a
    # transient failure — re-running it just re-peaks the worker's memory
    # (each attempt can take 90+ min on large books). Default: no retries.
    retry_jobs: bool = settings.worker_retry_jobs
    max_tries: int = settings.worker_max_tries
