"""Document management routes — upload, list, get, delete, retry."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.core.config import SettingsDep
from rag_agent.core.database import open_session
from rag_agent.core.exceptions import BadRequestError
from rag_agent.models.document import DocumentMetadata
from rag_agent.models.ingestion import IngestionResult
from rag_agent.pipeline.file_storage import LocalFileStorage
from rag_agent.services.document_service import DocumentService
from rag_agent.schemas.document import (
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
    RetryResponse,
)
from rag_agent.schemas.search import SearchResponse
from rag_agent.schemas.common import ErrorResponse, MessageResponse

router = APIRouter(tags=["documents"])


@router.post("/api/v1/documents/upload")
async def upload_document(
    settings: SettingsDep,
    file: UploadFile = File(...),
    collection_name: str = Query("documents"),
    replace: bool = Query(True),
    session: AsyncSession = Depends(open_session),
) -> DocumentUploadResponse:
    allowed = {".txt", ".md", ".docx", ".pdf"}
    if not file.filename or file.filename == "":
        raise BadRequestError("No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise BadRequestError(
            f"Unsupported file type: {ext}. Allowed: {sorted(allowed)}"
        )

    file_data = await file.read()
    if len(file_data) > settings.max_upload_bytes:
        raise BadRequestError(
            f"File too large: {len(file_data)} bytes > {settings.max_upload_bytes} limit"
        )

    storage = LocalFileStorage(settings.media_dir)
    storage_path = await storage.save(file.filename, file_data, collection_name)

    doc_service = DocumentService(session)
    response = await doc_service.create_tracking(
        collection_name=collection_name,
        filename=file.filename,
        filesize=len(file_data),
        filetype=ext.lstrip("."),
        storage_path=str(storage_path),
        source_path=str(storage_path),
    )

    await session.commit()
    return response


@router.get("/api/v1/documents")
async def list_documents(
    collection_name: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(open_session),
) -> DocumentListResponse:
    doc_service = DocumentService(session)
    return await doc_service.list_documents(
        collection_name=collection_name,
        status=status,
        page=page,
        per_page=per_page,
    )


@router.get("/api/v1/documents/{doc_id}")
async def get_document(
    doc_id: str,
    session: AsyncSession = Depends(open_session),
) -> DocumentDetail:
    doc_service = DocumentService(session)
    doc = await doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/api/v1/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    session: AsyncSession = Depends(open_session),
) -> MessageResponse:
    doc_service = DocumentService(session)
    deleted = await doc_service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.commit()
    return MessageResponse(message="Document deleted")


@router.post("/api/v1/documents/{doc_id}/retry")
async def retry_document(
    doc_id: str,
    session: AsyncSession = Depends(open_session),
) -> RetryResponse:
    doc_service = DocumentService(session)
    response = await doc_service.retry_document(doc_id)
    await session.commit()
    return response


@router.get("/api/v1/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    session: AsyncSession = Depends(open_session),
) -> FileResponse:
    doc_service = DocumentService(session)
    doc = await doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not Path(doc.storage_path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=doc.storage_path,
        filename=doc.filename,
        media_type="application/octet-stream",
    )
