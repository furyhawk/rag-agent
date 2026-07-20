"""Tests for document upload endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.schemas.document import DocumentUploadResponse


class TestDocumentUpload:
    """Test document upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_valid_txt_file(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test uploading a valid .txt file."""
        # Create a test file
        test_content = b"Test document content"
        files = {"file": ("test.txt", test_content, "text/plain")}
        data = {"collection_name": "test_collection", "replace": "true"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert "filename" in data
        assert data["filename"] == "test.txt"
        assert "collection_name" in data
        assert data["collection_name"] == "test_collection"
        assert "filetype" in data
        assert data["filetype"] == "txt"
        assert "filesize" in data
        assert data["filesize"] == len(test_content)

        # Verify document was created in database
        doc = await db_session.get(Document, data["document_id"])
        assert doc is not None
        assert doc.filename == "test.txt"
        assert doc.collection_name == "test_collection"
        assert doc.filesize == len(test_content)

    @pytest.mark.asyncio
    async def test_upload_valid_pdf_file(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test uploading a valid .pdf file."""
        test_content = b"%PDF-1.4\nTest PDF content"
        files = {"file": ("test.pdf", test_content, "application/pdf")}
        data = {"collection_name": "documents"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["filetype"] == "pdf"

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, client: AsyncClient):
        """Test uploading an unsupported file type."""
        files = {"file": ("test.exe", b"malicious content", "application/octet-stream")}
        data = {"collection_name": "test"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Unsupported file type" in data["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_filename(self, client: AsyncClient):
        """Test uploading with empty filename."""
        files = {"file": ("", b"content", "text/plain")}
        data = {"collection_name": "test"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_upload_without_file(self, client: AsyncClient):
        """Test upload endpoint without file parameter."""
        data = {"collection_name": "test"}

        response = await client.post("/api/v1/documents/upload", data=data)

        # Should fail because file is required
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, client: AsyncClient, settings):
        """Test uploading a file that exceeds size limit."""
        # Create file larger than max_upload_bytes
        large_content = b"x" * (settings.max_upload_bytes + 1)
        files = {"file": ("large.txt", large_content, "text/plain")}
        data = {"collection_name": "test"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    @pytest.mark.asyncio
    async def test_upload_with_default_collection(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test upload without specifying collection_name (should use default)."""
        test_content = b"Test content"
        files = {"file": ("test.txt", test_content, "text/plain")}

        # Don't specify collection_name - should use default "documents"
        response = await client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["collection_name"] == "documents"
        assert data["filename"] == "test.txt"

    @pytest.mark.asyncio
    async def test_upload_replace_flag(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that replace flag is accepted."""
        test_content = b"Test content"
        files = {"file": ("test.txt", test_content, "text/plain")}
        data = {"replace": "true"}

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"

