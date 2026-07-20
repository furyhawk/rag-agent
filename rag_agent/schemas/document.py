"""Document API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    id: str
    filename: str
    collection: str
    status: str
    message: str
    document_id: str | None = None


class DocumentItem(BaseModel):
    """A tracked document in list views."""

    id: str
    collection_name: str
    filename: str
    filesize: int
    filetype: str
    status: str
    chunk_count: int = 0
    source_path: str = ""
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class DocumentDetail(BaseModel):
    """Detailed document view."""

    id: str
    collection_name: str
    filename: str
    filesize: int
    filetype: str
    status: str
    chunk_count: int = 0
    vector_document_id: str | None = None
    storage_path: str
    source_path: str
    source_type: str
    content_hash: str
    error_message: str | None = None
    last_error: str | None = None
    retry_count: int = 0
    created_at: datetime
    completed_at: datetime | None = None


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentItem]
    total: int
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)


class RetryResponse(BaseModel):
    """Response after retrying a failed document."""

    id: str
    status: str
    message: str
