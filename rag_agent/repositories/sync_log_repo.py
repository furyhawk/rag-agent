"""Repository for SyncLog CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.db.models.sync_log import SyncLog


class SyncLogRepository:
    """Data access layer for sync logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: SyncLog) -> SyncLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_by_id(self, log_id: uuid.UUID) -> SyncLog | None:
        result = await self._session.execute(
            select(SyncLog).where(SyncLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        collection_name: str | None = None,
        limit: int = 20,
    ) -> list[SyncLog]:
        query = select(SyncLog)
        if collection_name:
            query = query.where(
                SyncLog.collection_name == collection_name
            )
        query = query.order_by(SyncLog.started_at.desc()).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        log_id: uuid.UUID,
        status: str,
        ingested: int = 0,
        failed: int = 0,
        skipped: int = 0,
        total_files: int = 0,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if total_files:
            values["total_files"] = total_files
        if ingested:
            values["ingested"] = ingested
        if failed:
            values["failed"] = failed
        if skipped:
            values["skipped"] = skipped
        if error_message is not None:
            values["error_message"] = error_message
        if status in ("completed", "failed", "cancelled"):
            values["completed_at"] = datetime.now(timezone.utc)
        await self._session.execute(
            update(SyncLog).where(SyncLog.id == log_id).values(**values)
        )
