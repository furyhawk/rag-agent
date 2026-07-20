"""Base chunker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag_agent.models.document import DocumentChunk, DocumentPage


class BaseChunker(ABC):
    """Abstract base class for text chunking strategies."""

    @abstractmethod
    def chunk_page(
        self, page: DocumentPage, parent_doc_id: str
    ) -> list[DocumentChunk]:
        """Split a document page into chunks.

        Args:
            page: The document page to chunk.
            parent_doc_id: The parent document's ID.

        Returns:
            List of DocumentChunk objects.
        """
        ...
