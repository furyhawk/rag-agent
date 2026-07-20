"""Repository for TrackedDocument CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.db.models.document import TrackedDocument


class DocumentRepository:
    """Data access layer for tracked documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, doc: TrackedDocument) -> TrackedDocument:
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> TrackedDocument | None:
        result = await self._session.execute(
            select(TrackedDocument).where(TrackedDocument.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        collection_name: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[TrackedDocument]:
        query = select(TrackedDocument)
        if collection_name:
            query = query.where(
                TrackedDocument.collection_name == collection_name
            )
        if status:
            query = query.where(TrackedDocument.status == status)
        query = query.order_by(TrackedDocument.created_at.desc())
        query = query.offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        doc_id: uuid.UUID,
        status: str,
        chunk_count: int = 0,
        vector_document_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if chunk_count:
            values["chunk_count"] = chunk_count
        if vector_document_id:
            values["vector_document_id"] = vector_document_id
        if error_message is not None:
            values["last_error"] = error_message
        if status == "done":
            values["completed_at"] = datetime.now(timezone.utc)
        await self._session.execute(
            update(TrackedDocument)
            .where(TrackedDocument.id == doc_id)
            .values(**values)
        )

    async def increment_retry_count(self, doc_id: uuid.UUID) -> None:
        await self._session.execute(
            update(TrackedDocument)
            .where(TrackedDocument.id == doc_id)
            .values(retry_count=TrackedDocument.retry_count + 1)
        )

    async def delete(self, doc_id: uuid.UUID) -> bool:
        doc = await self.get_by_id(doc_id)
        if doc:
            await self._session.delete(doc)
            return True
        return False

    async def delete_by_collection(self, collection_name: str) -> int:
        from sqlalchemy import delete

        result = await self._session.execute(
            delete(TrackedDocument).where(
                TrackedDocument.collection_name == collection_name
            )
        )
        return result.rowcount  # type: ignore[return-value]

    async def find_by_content_hash(
        self, collection_name: str, content_hash: str
    ) -> TrackedDocument | None:
        result = await self._session.execute(
            select(TrackedDocument).where(
                TrackedDocument.collection_name == collection_name,
                TrackedDocument.content_hash == content_hash,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_source_path(
        self, collection_name: str, source_path: str
    ) -> TrackedDocument | None:
        result = await self._session.execute(
            select(TrackedDocument).where(
                TrackedDocument.collection_name == collection_name,
                TrackedDocument.source_path == source_path,
            )
        )
        return result.scalar_one_or_none()
