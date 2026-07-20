"""Document domain models.

Extracted and generalized from agent_alpha/backend/services/rag/models.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator


class DocumentImage(BaseModel):
    """An image extracted from a document page."""

    image_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_num: int = 0
    image_bytes: bytes = b""
    description: str = ""
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None


class DocumentPage(BaseModel):
    """Content of a document page."""

    page_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_num: int
    content: str
    parent_doc_id: str | None = None
    images: list[DocumentImage] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    """A chunk derived from a document page."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_num: int = 0
    chunk_content: str
    page_num: int
    page_id: str = ""
    parent_doc_id: str | None = None
    images: list[DocumentImage] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Metadata describing a document's origin and properties."""

    filename: str
    filesize: int
    filetype: str
    source_path: str = ""
    source_type: str = "local"  # local, s3, gdrive, web
    content_hash: str = ""  # SHA-256 for deduplication
    additional_info: dict[str, Any] | None = None


class Document(BaseModel):
    """A document object representing a parsed and chunked file."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pages: list[DocumentPage]
    chunks: list[DocumentChunk] | None = None
    metadata: DocumentMetadata
    ingested_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def num_pages(self) -> int:
        return len(self.pages)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def num_chunks(self) -> int:
        return len(self.chunks) if self.chunks else 0

    @model_validator(mode="after")
    def _connect_pages(self) -> "Document":
        for page in self.pages:
            page.parent_doc_id = self.id
        return self
