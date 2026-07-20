"""Base document parser interface."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from rag_agent.models.document import Document, DocumentMetadata


class BaseDocumentParser(ABC):
    """Abstract base class for document parsing strategies."""

    SUPPORTED_EXTENSIONS: set[str] = set()

    def is_file_existing(self, filepath: Path) -> bool:
        """Check if file exists at the given path."""
        return filepath.exists()

    def is_extension_allowed(self, filepath: Path) -> bool:
        """Check whether document extension is allowed for parsing."""
        return (
            filepath.suffix.lower() in self.SUPPORTED_EXTENSIONS
            and self.is_file_existing(filepath)
        )

    def get_document_metadata(self, filepath: Path) -> DocumentMetadata:
        """Collect metadata about a document file."""
        content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        return DocumentMetadata(
            filename=filepath.name,
            filesize=filepath.stat().st_size,
            filetype=filepath.suffix.lstrip("."),
            source_path=str(filepath.resolve()),
            content_hash=content_hash,
        )

    @abstractmethod
    async def parse(self, filepath: Path) -> Document:
        """Parse a file into a Document object."""
        ...
