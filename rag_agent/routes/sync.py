"""Sync and status streaming routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.core.config import SettingsDep
from rag_agent.core.database import open_session
from rag_agent.schemas.common import MessageResponse
from rag_agent.services.status_service import StatusService
from rag_agent.services.sync_service import SyncService

router = APIRouter(tags=["sync"])


@router.post("/api/v1/sync")
async def trigger_sync(
    settings: SettingsDep,
    session: AsyncSession = Depends(open_session),
    collection_name: str = Query("documents"),
    path: str = Query(...),
    mode: str = Query("full"),
) -> MessageResponse:
    from rag_agent.connectors.base import LocalFilesystemConnector
    from rag_agent.core.config import RAGSettings
    from rag_agent.pipeline.ingestion import IngestionService

    sync_service = SyncService(
        session=session,
        ingestion_service=IngestionService.build(
            settings.rag,
            settings.milvus_uri,
            settings.milvus_token,
            embedding_api_key=settings.embedding_api_key,
            embedding_base_url=settings.embedding_base_url,
        ),
        settings=RAGSettings(),
    )
    log_id = await sync_service.sync_local_directory(
        collection_name=collection_name,
        path=path,
        mode=mode,
    )
    return MessageResponse(message=f"Sync triggered, log_id={log_id}")


@router.get("/api/v1/sync/logs")
async def list_sync_logs(
    collection_name: str | None = Query(None),
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(open_session),
) -> list:
    from rag_agent.repositories.sync_log_repo import SyncLogRepository

    repo = SyncLogRepository(session)
    logs = await repo.list_logs(
        collection_name=collection_name, limit=limit
    )
    return [
        {
            "id": str(l.id),
            "source": l.source,
            "collection_name": l.collection_name,
            "status": l.status,
            "mode": l.mode,
            "total_files": l.total_files,
            "ingested": l.ingested,
            "failed": l.failed,
            "skipped": l.skipped,
            "error_message": l.error_message,
            "started_at": l.started_at,
            "completed_at": l.completed_at,
        }
        for l in logs
    ]


@router.get("/api/v1/connectors")
async def list_connectors() -> list[dict]:
    from rag_agent.connectors.base import CONNECTOR_REGISTRY

    return [
        {
            "type": cls.CONNECTOR_TYPE,
            "display_name": cls.DISPLAY_NAME,
            "config_schema": cls.CONFIG_SCHEMA,
        }
        for cls in CONNECTOR_REGISTRY.values()
    ]


@router.get("/api/v1/status")
async def status_stream(
    settings: SettingsDep,
) -> Any:
    from rag_agent.core.valkey import get_valkey
    from rag_agent.services.status_service import StatusService

    valkey = get_valkey()
    service = StatusService(valkey, settings)
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        service.stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
