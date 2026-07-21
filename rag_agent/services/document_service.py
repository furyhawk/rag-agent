"""Service for document lifecycle management."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.db.models.document import TrackedDocument
from rag_agent.repositories.document_repo import DocumentRepository
from rag_agent.schemas.document import (
    DocumentDetail,
    DocumentItem,
    DocumentListResponse,
    DocumentUploadResponse,
    RetryResponse,
)
from rag_agent.worker.dispatcher import TaskDispatcher


class DocumentService:
    """Orchestrates document lifecycle: upload dispatch, tracking, completion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DocumentRepository(session)

    async def create_tracking(
        self,
        collection_name: str,
        filename: str,
        filesize: int,
        filetype: str,
        storage_path: str,
        source_path: str = "",
        source_type: str = "local",
        vector_document_id: str | None = None,
    ) -> DocumentUploadResponse:
        content_hash = hashlib.sha256(open(storage_path, "rb").read()).hexdigest()
        doc = TrackedDocument(
            collection_name=collection_name,
            filename=filename,
            filesize=filesize,
            filetype=filetype,
            status="queued",
            storage_path=str(storage_path),
            source_path=source_path,
            source_type=source_type,
            content_hash=content_hash,
            vector_document_id=vector_document_id,
        )
        await self._repo.create(doc)

        # Enqueue background task for processing
        from rag_agent.core.config import get_settings
        settings = get_settings()
        dispatcher = TaskDispatcher(settings.valkey_url)
        await dispatcher.enqueue(
            "process_document",
            doc_id=str(doc.id),
            collection_name=collection_name,
            storage_path=str(storage_path),
            filename=filename,
        )

        return DocumentUploadResponse(
            id=str(doc.id),
            filename=filename,
            collection=collection_name,
            status="queued",
            message="Document uploaded and queued for processing",
        )

    async def list_documents(
        self,
        collection_name: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> DocumentListResponse:
        docs = await self._repo.list_all(
            collection_name=collection_name,
            status=status,
            offset=(page - 1) * per_page,
            limit=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        items = [
            DocumentItem(
                id=str(d.id),
                collection_name=d.collection_name,
                filename=d.filename,
                filesize=d.filesize,
                filetype=d.filetype,
                status=d.status,
                chunk_count=d.chunk_count,
                source_path=d.source_path,
                error_message=d.error_message,
                created_at=d.created_at,
                completed_at=d.completed_at,
            )
            for d in docs
        ]
        total = await self._repo.count(
            collection_name=collection_name,
            status=status,
        )
        return DocumentListResponse(
            items=items, total=total, page=page, per_page=per_page
        )

    async def get_document(self, doc_id: str) -> DocumentDetail | None:
        doc = await self._repo.get_by_id(uuid.UUID(doc_id))
        if not doc:
            return None
        return DocumentDetail(
            id=str(doc.id),
            collection_name=doc.collection_name,
            filename=doc.filename,
            filesize=doc.filesize,
            filetype=doc.filetype,
            status=doc.status,
            chunk_count=doc.chunk_count,
            vector_document_id=doc.vector_document_id,
            storage_path=doc.storage_path,
            source_path=doc.source_path,
            source_type=doc.source_type,
            content_hash=doc.content_hash,
            error_message=doc.error_message,
            last_error=doc.last_error,
            retry_count=doc.retry_count,
            created_at=doc.created_at,
            completed_at=doc.completed_at,
        )

    async def delete_document(self, doc_id: str) -> bool:
        return await self._repo.delete(uuid.UUID(doc_id))

    async def delete_by_collection(self, collection_name: str) -> int:
        return await self._repo.delete_by_collection(collection_name)

    async def retry_document(self, doc_id: str) -> RetryResponse:
        doc = await self._repo.get_by_id(uuid.UUID(doc_id))
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        await self._repo.update_status(
            doc.id, status="queued", error_message=None
        )
        await self._repo.increment_retry_count(doc.id)
        return RetryResponse(
            id=str(doc.id), status="queued", message="Document re-queued"
        )

    async def complete_ingestion(
        self,
        doc_id: str,
        vector_document_id: str,
        chunk_count: int,
        error_message: str | None = None,
    ) -> None:
        await self._repo.update_status(
            uuid.UUID(doc_id),
            status="done" if not error_message else "error",
            chunk_count=chunk_count,
            vector_document_id=vector_document_id,
            error_message=error_message,
        )

    async def fail_ingestion(
        self, doc_id: str, error_message: str
    ) -> None:
        await self._repo.update_status(
            uuid.UUID(doc_id),
            status="error",
            error_message=error_message,
        )
