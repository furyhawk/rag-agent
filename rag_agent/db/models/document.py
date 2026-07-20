"""Tracked document ORM model.

Extracted from agent_alpha/backend/db/models/rag_document.py with improvements:
- retry_count for ARQ retries
- source_type for connector expansion
- content_hash for indexed dedup queries
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rag_agent.db.base import Base


class TrackedDocument(Base):
    """Tracks a document through the ingestion pipeline."""

    __tablename__ = "tracked_documents"
    __table_args__ = (
        Index("ix_tracked_documents_collection_status", "collection_name", "status"),
        Index("ix_tracked_documents_content_hash", "content_hash"),
        Index("ix_tracked_documents_source_path", "source_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="documents"
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    filesize: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filetype: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vector_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<TrackedDocument {self.filename!r} status={self.status!r}>"
