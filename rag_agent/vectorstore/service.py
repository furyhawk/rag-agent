"""Vector store service — higher-level collection lifecycle operations."""

from __future__ import annotations

from rag_agent.models.collection import CollectionInfo
from rag_agent.models.common import DocumentInfo
from rag_agent.models.document import Document
from rag_agent.models.search import SearchResult
from rag_agent.vectorstore.base import BaseVectorStore


class VectorStoreService:
    """Convenience wrapper around BaseVectorStore for the application layer."""

    def __init__(self, store: BaseVectorStore) -> None:
        self._store = store

    async def ensure_collection(self, name: str) -> None:
        """Validate name and create collection if needed."""
        self._store.validate_collection_name(name)
        await self._store.ensure_collection(name)

    async def create_collection(self, name: str) -> None:
        """Create a new collection after validation."""
        self._store.validate_collection_name(name)
        await self._store.ensure_collection(name)

    async def insert_document(
        self, collection_name: str, document: Document
    ) -> None:
        await self._store.insert_document(collection_name, document)

    async def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 4,
        filter: str = "",
    ) -> list[SearchResult]:
        return await self._store.search(
            collection_name, query, limit, filter
        )

    async def delete_collection(self, name: str) -> None:
        await self._store.delete_collection(name)

    async def delete_document(
        self, collection_name: str, document_id: str
    ) -> None:
        await self._store.delete_document(collection_name, document_id)

    async def get_collection_info(
        self, collection_name: str
    ) -> CollectionInfo:
        return await self._store.get_collection_info(collection_name)

    async def list_collections(self) -> list[str]:
        return await self._store.list_collections()

    async def get_documents(
        self, collection_name: str
    ) -> list[DocumentInfo]:
        return await self._store.get_documents(collection_name)
