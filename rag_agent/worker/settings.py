"""Worker settings and task definitions for ARQ."""

from __future__ import annotations

from rag_agent.core.config import Settings, get_settings


class WorkerSettings:
    """ARQ worker configuration."""

    functions: list = []
    max_jobs: int = 4
    job_timeout: int = 600  # 10 minutes per job
    retry_jobs: bool = True
    max_tries: int = 3
