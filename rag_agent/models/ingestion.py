"""Ingestion domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class IngestionStatus(StrEnum):
    """Fine-grained ingestion pipeline status."""

    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    DONE = "done"
    ERROR = "error"


class IngestionProgress(BaseModel):
    """Progress event emitted during ingestion pipeline stages."""

    document_id: str
    status: IngestionStatus
    filename: str
    collection: str
    pages_parsed: int = 0
    total_pages: int = 0
    chunks_created: int = 0
    error_message: str | None = None


class IngestionResult(BaseModel):
    """Result of a completed ingestion operation."""

    status: IngestionStatus = IngestionStatus.QUEUED
    document_id: str | None = None
    message: str | None = None
    error_message: str | None = None
    chunk_count: int = 0
