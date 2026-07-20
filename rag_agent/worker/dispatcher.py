"""ARQ task dispatcher."""

from __future__ import annotations

import redis.asyncio as redis


class TaskDispatcher:
    """Dispatches tasks to ARQ via Valkey/Redis."""

    def __init__(self, valkey_url: str) -> None:
        self._pool = redis.ConnectionPool.from_url(valkey_url)

    async def enqueue(
        self, task_name: str, **kwargs: object
    ) -> str | None:
        """Enqueue a task via ARQ. Returns job_id."""
        try:
            from arq import create_pool

            pool = await create_pool(self._pool)
            job = await pool.enqueue_job(task_name, **kwargs)
            return job.job_id if job else None
        except Exception:
            return None

    async def close(self) -> None:
        await self._pool.aclose()
