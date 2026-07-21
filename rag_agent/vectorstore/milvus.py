"""Milvus vector store implementation.

Extracted and generalized from agent_alpha/backend/services/rag/vectorstore.py.
"""

from __future__ import annotations

from typing import Any

from pymilvus import AsyncMilvusClient, DataType

from rag_agent.core.logging import get_logger
from rag_agent.embeddings.service import EmbeddingService
from rag_agent.models.collection import CollectionInfo
from rag_agent.models.common import DocumentInfo
from rag_agent.models.document import Document
from rag_agent.models.search import SearchResult
from rag_agent.vectorstore.base import BaseVectorStore

logger = get_logger(__name__)


class MilvusVectorStore(BaseVectorStore):
    """Milvus vector store using AsyncMilvusClient.

    Schema per collection:
    - id: VARCHAR PK (chunk_id, max 100)
    - parent_doc_id: VARCHAR (max 100)
    - content: VARCHAR (max 65535)
    - vector: FLOAT_VECTOR (dim from embedding config)
    - metadata: JSON
    """

    def __init__(
        self,
        milvus_uri: str,
        milvus_token: str,
        embedding_dim: int,
        embedding_service: EmbeddingService,
    ) -> None:
        self._embedding_dim = embedding_dim
        self._embedder = embedding_service
        self._client = AsyncMilvusClient(
            uri=milvus_uri, token=milvus_token or None
        )

    async def ensure_collection(self, name: str) -> None:
        """Create the collection if it does not already exist."""
        if not await self._client.has_collection(name):
            schema = self._client.create_schema(auto_id=False)
            schema.add_field(
                "id", DataType.VARCHAR, is_primary=True, max_length=100
            )
            schema.add_field(
                "parent_doc_id", DataType.VARCHAR, max_length=100
            )
            schema.add_field("content", DataType.VARCHAR, max_length=65535)
            schema.add_field(
                "vector",
                DataType.FLOAT_VECTOR,
                dim=self._embedding_dim,
            )
            schema.add_field("metadata", DataType.JSON)
            await self._client.create_collection(
                name, schema=schema, metric_type="COSINE"
            )
            logger.info("milvus.collection_created", name=name)

        indexes = await self._client.list_indexes(name)
        if not indexes:
            index_params = self._client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )
            await self._client.create_index(
                collection_name=name, index_params=index_params
            )
            logger.info("milvus.index_created", name=name)

        await self._client.load_collection(name)

    async def insert_document(
        self, collection_name: str, document: Document
    ) -> None:
        await self.ensure_collection(collection_name)

        if not document.chunks:
            raise ValueError("Document has no chunks.")

        logger.info(
            "milvus.insert",
            filename=document.metadata.filename,
            collection=collection_name,
            chunks=len(document.chunks),
            dim=self._embedding_dim,
        )

        vectors = self._embedder.embed_document(document)
        data = [
            {
                "id": chunk.chunk_id,
                "parent_doc_id": chunk.parent_doc_id,
                "content": chunk.chunk_content,
                "vector": vectors[i],
                "metadata": self.build_chunk_metadata(chunk, document),
            }
            for i, chunk in enumerate(document.chunks)
        ]
        await self._client.insert(collection_name, data=data)
        await self._client.flush(collection_name)

        logger.info(
            "milvus.flushed",
            collection=collection_name,
            chunks=len(data),
        )

    async def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 4,
        filter: str = "",
    ) -> list[SearchResult]:
        query_vector = self._embedder.embed_query(query)
        results = await self._client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=limit,
            filter=filter,
            output_fields=["content", "parent_doc_id", "metadata"],
        )
        return [
            SearchResult(
                content=hit["entity"]["content"],
                score=hit["distance"],
                metadata=hit["entity"]["metadata"],
                parent_doc_id=hit["entity"]["parent_doc_id"],
            )
            for hit in results[0]
        ]

    async def get_collection_info(
        self, collection_name: str
    ) -> CollectionInfo:
        count = await self._client.get_collection_stats(collection_name)
        return CollectionInfo(
            name=collection_name,
            total_vectors=int(count.get("row_count", 0)),
            dim=self._embedding_dim,
        )

    async def delete_collection(self, collection_name: str) -> None:
        await self._client.drop_collection(collection_name)

    async def delete_document(
        self, collection_name: str, document_id: str
    ) -> None:
        sanitized = self.sanitize_id(document_id)
        await self._client.delete(
            collection_name=collection_name,
            filter=f'parent_doc_id == "{sanitized}"',
        )

    async def get_documents(
        self, collection_name: str
    ) -> list[DocumentInfo]:
        await self.ensure_collection(collection_name)
        results: list[dict[str, Any]] = await self._client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["parent_doc_id", "metadata"],
            limit=10000,
        )
        return self.group_documents(results)

    async def list_collections(self) -> list[str]:
        result: list[str] = await self._client.list_collections()
        return result
