"""Base vector store interface."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from rag_agent.models.collection import CollectionInfo
from rag_agent.models.common import DocumentInfo
from rag_agent.models.document import Document, DocumentChunk
from rag_agent.models.search import SearchResult

_COLLECTION_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
_RESERVED_COLLECTION_NAMES = frozenset({"all"})


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    async def insert_document(
        self, collection_name: str, document: Document
    ) -> None:
        """Embed and store document chunks."""
        ...

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 4,
        filter: str = "",
    ) -> list[SearchResult]:
        """Retrieve similar chunks based on a text query."""
        ...

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """Remove a collection and all its data."""
        ...

    @abstractmethod
    async def delete_document(
        self, collection_name: str, document_id: str
    ) -> None:
        """Remove all chunks associated with a document ID."""
        ...

    @abstractmethod
    async def get_collection_info(
        self, collection_name: str
    ) -> CollectionInfo:
        """Return metadata and stats about a collection."""
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """Return list of all collection names."""
        ...

    @abstractmethod
    async def get_documents(
        self, collection_name: str
    ) -> list[DocumentInfo]:
        """Return list of unique documents in a collection."""
        ...

    def validate_collection_name(self, name: str) -> None:
        """Validate collection name format.

        Raises:
            ValueError: If name is invalid or reserved.
        """
        if not _COLLECTION_NAME_RE.match(name):
            raise ValueError(
                "Collection name must start with a letter and contain only "
                "letters, numbers, and underscores (max 64 chars)"
            )
        if name.lower() in _RESERVED_COLLECTION_NAMES:
            raise ValueError(f"'{name}' is a reserved collection name")

    def build_chunk_metadata(
        self, chunk: DocumentChunk, document: Document
    ) -> dict[str, Any]:
        """Build metadata dict for a chunk stored in the vector DB."""
        meta = {
            "page_num": chunk.page_num,
            "chunk_num": chunk.chunk_num,
            "has_images": bool(chunk.images),
            "image_count": len(chunk.images),
            **document.metadata.model_dump(),
        }
        return meta

    @staticmethod
    def sanitize_id(document_id: str) -> str:
        """Sanitize document_id to prevent filter injection."""
        return document_id.replace('"', "").replace("\\", "")

    @staticmethod
    def group_documents(results: list[dict[str, Any]]) -> list[DocumentInfo]:
        """Group query results by parent_doc_id into DocumentInfo list."""
        doc_map: dict[str, dict[str, Any]] = {}
        for item in results:
            doc_id = item.get("parent_doc_id")
            metadata = item.get("metadata", {})
            if doc_id and doc_id not in doc_map:
                doc_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": metadata.get("filename"),
                    "filesize": metadata.get("filesize"),
                    "filetype": metadata.get("filetype"),
                    "additional_info": {
                        "source_path": metadata.get("source_path", ""),
                        "content_hash": metadata.get("content_hash", ""),
                        **(metadata.get("additional_info") or {}),
                    },
                    "chunk_count": 0,
                }
            if doc_id:
                doc_map[doc_id]["chunk_count"] += 1
        return [
            DocumentInfo(
                document_id=d["document_id"],
                filename=d.get("filename"),
                filesize=d.get("filesize"),
                filetype=d.get("filetype"),
                chunk_count=d["chunk_count"],
                additional_info=d.get("additional_info"),
            )
            for d in doc_map.values()
        ]
