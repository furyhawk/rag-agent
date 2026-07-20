"""Worker settings and task definitions for ARQ."""

from __future__ import annotations

import logging

from rag_agent.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def _noop_job(ctx) -> None:
    """Placeholder job so the ARQ worker can start without errors.

    This will be replaced by real task implementations (e.g. document
    ingestion, embedding generation) as they are developed.  It can be
    enqueued via ``TaskDispatcher.enqueue("_noop_job")`` for smoke-test
    purposes.
    """
    logger.info("noop job executed, ctx=%s", ctx)


class WorkerSettings:
    """ARQ worker configuration."""

    functions: list = [_noop_job]
    max_jobs: int = 4
    job_timeout: int = 600  # 10 minutes per job
    retry_jobs: bool = True
    max_tries: int = 3
