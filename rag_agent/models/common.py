"""Shared domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Summary information about a stored document."""

    document_id: str
    filename: str | None = None
    filesize: int | None = None
    filetype: str | None = None
    chunk_count: int = 0
    additional_info: dict[str, Any] | None = None


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
