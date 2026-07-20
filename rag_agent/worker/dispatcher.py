"""ARQ task dispatcher."""

from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings


class TaskDispatcher:
    """Dispatches tasks to ARQ via Valkey/Redis."""

    def __init__(self, valkey_url: str) -> None:
        from urllib.parse import urlparse
        parsed = urlparse(valkey_url)
        self._settings = RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password or None,
            database=int(parsed.path.lstrip("/") or 0),
        )

    async def enqueue(
        self, task_name: str, **kwargs: object
    ) -> str | None:
        """Enqueue a task via ARQ. Returns job_id."""
        try:
            pool = await create_pool(self._settings)
            job = await pool.enqueue_job(task_name, **kwargs)
            await pool.close()
            return job.job_id if job else None
        except Exception:
            return None

    async def close(self) -> None:
        pass
