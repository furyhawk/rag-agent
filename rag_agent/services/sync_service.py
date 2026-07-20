"""Sync service for directory/collection synchronization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.connectors.base import BaseConnector
from rag_agent.core.config import RAGSettings
from rag_agent.db.models.sync_log import SyncLog
from rag_agent.models.document import DocumentMetadata
from rag_agent.pipeline.ingestion import IngestionService
from rag_agent.repositories.sync_log_repo import SyncLogRepository
from rag_agent.services.document_service import DocumentService


class SyncService:
    """Orchestrates collection sync operations."""

    def __init__(
        self,
        session: AsyncSession,
        ingestion_service: IngestionService,
        settings: RAGSettings,
    ) -> None:
        self._session = session
        self._ingestion = ingestion_service
        self._settings = settings
        self._log_repo = SyncLogRepository(session)

    async def sync_local_directory(
        self,
        collection_name: str,
        path: str,
        mode: str = "full",
    ) -> str:
        """Sync a local directory to a collection.

        Args:
            collection_name: Target collection.
            path: Local directory path.
            mode: "full", "new_only", or "update_only".

        Returns:
            Sync log ID.
        """
        from rag_agent.connectors.base import LocalFilesystemConnector

        connector = LocalFilesystemConnector
        log = SyncLog(
            source="local",
            collection_name=collection_name,
            mode=mode,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        await self._log_repo.create(log)
        await self._session.commit()

        try:
            files = await connector.list_files({"path": path})
            total = len(files)

            for file_info in files:
                filepath = Path(file_info["path"])
                meta = DocumentMetadata(
                    filename=filepath.name,
                    filesize=file_info["size"],
                    filetype=filepath.suffix.lstrip("."),
                    source_path=str(filepath),
                    source_type="local",
                )

                result = await self._ingestion.ingest_file(
                    filepath=filepath,
                    collection_name=collection_name,
                    replace=(mode == "full"),
                    source_path=str(filepath),
                )

                # Track result via document service
                doc_service = DocumentService(self._session)
                if result.status == "done":
                    # Create or update tracking record
                    pass  # TODO

            await self._log_repo.update_status(
                log.id,
                status="completed",
                total_files=total,
                ingested=total,
                failed=0,
                skipped=0,
            )
        except Exception as e:
            await self._log_repo.update_status(
                log.id,
                status="failed",
                error_message=str(e),
            )
        await self._session.commit()
        return str(log.id)
