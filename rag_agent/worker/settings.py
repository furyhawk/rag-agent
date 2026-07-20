"""Worker settings and task definitions for ARQ."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def _noop_job(ctx) -> None:
    """Placeholder job so the ARQ worker can start without errors.

    This will be replaced by real task implementations (e.g. document
    ingestion, embedding generation) as they are developed.  It can be
    enqueued via ``TaskDispatcher.enqueue("_noop_job")`` for smoke-test
    purposes.
    """
    logger.info("noop job executed, ctx=%s", ctx)


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

    functions: list = [_noop_job]
    redis_settings: RedisSettings | None = _get_redis_settings()
    max_jobs: int = 4
    job_timeout: int = 600  # 10 minutes per job
    retry_jobs: bool = True
    max_tries: int = 3
