"""Unit tests for Milvus insert batching.

Regression tests for the RESOURCE_EXHAUSTED gRPC error seen when ingesting a
large PDF that chunks into many rows:

    AioRpcError RESOURCE_EXHAUSTED:
      "grpc: received message larger than max (262126230 vs. 67108864)"

Milvus's default gRPC max receive message size is 64 MiB (67108864 bytes).
Sending the whole document's vectors in ONE insert() call exceeds that and
the server rejects the request. `MilvusVectorStore.insert_document` now
splits the rows into byte-bounded batches so each request stays under the
limit.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from rag_agent.models.document import (
    Document,
    DocumentChunk,
    DocumentMetadata,
    DocumentPage,
)
from rag_agent.vectorstore.milvus import MilvusVectorStore

DIM = 384


class FakeEmbedder:
    """Returns a zero vector per chunk; dim matches the store config."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim

    def embed_document(self, document: Document) -> list[list[float]]:
        n = len(document.chunks or [])
        return [[0.1] * self.dim for _ in range(n)]


class FakeMilvusClient:
    """Minimal AsyncMilvusClient stand-in that records insert/flush calls."""

    def __init__(self) -> None:
        self.inserts: list[list[dict]] = []
        self.flush_calls = 0
        self.created = False

    async def has_collection(self, name: str) -> bool:
        return self.created

    def create_schema(self, auto_id: bool = False) -> object:
        class _Schema:
            def add_field(self, *args, **kwargs) -> None:  # noqa: ARG002
                pass

        return _Schema()

    async def create_collection(self, *args, **kwargs) -> None:  # noqa: ARG002
        self.created = True

    async def list_indexes(self, name: str) -> list:  # noqa: ARG002
        return []

    def prepare_index_params(self) -> object:
        class _IndexParams:
            def add_index(self, *args, **kwargs) -> None:  # noqa: ARG002
                pass

        return _IndexParams()

    async def create_index(self, *args, **kwargs) -> None:  # noqa: ARG002
        pass

    async def load_collection(self, name: str) -> None:  # noqa: ARG002
        pass

    async def insert(self, collection_name: str, data: list[dict]) -> None:  # noqa: ARG002
        self.inserts.append(list(data))

    async def flush(self, collection_name: str) -> None:  # noqa: ARG002
        self.flush_calls += 1


def _make_store(max_batch_bytes: int, fake: FakeMilvusClient) -> MilvusVectorStore:
    with patch(
        "rag_agent.vectorstore.milvus.AsyncMilvusClient",
        return_value=fake,
    ):
        store = MilvusVectorStore(
            milvus_uri="http://localhost:19530",
            milvus_token="",
            embedding_dim=DIM,
            embedding_service=FakeEmbedder(DIM),
            max_batch_bytes=max_batch_bytes,
        )
    return store


def _make_document(n_chunks: int, content_len: int) -> Document:
    chunks = [
        DocumentChunk(
            chunk_id=f"c{i:05d}",
            chunk_num=i,
            chunk_content="x" * content_len,
            page_num=i // 10,
            parent_doc_id="doc-big",
        )
        for i in range(n_chunks)
    ]
    return Document(
        pages=[DocumentPage(page_num=0, content="")],
        chunks=chunks,
        metadata=DocumentMetadata(
            filename="big.pdf",
            filesize=100 * 1024 * 1024,
            filetype="application/pdf",
        ),
    )


def _estimated_batch_bytes(rows: list[dict]) -> int:
    """Recompute the same byte estimate _split_batches uses."""
    total = 0
    for row in rows:
        total += (
            len(row.get("content") or "")
            + len(row.get("vector") or []) * 4
            + len(str(row.get("metadata") or {}))
            + 512
        )
    return total


@pytest.mark.asyncio
async def test_insert_document_splits_oversized_payload_into_batches() -> None:
    """A payload bigger than the budget must be split across multiple inserts."""
    fake = FakeMilvusClient()
    batch_bytes = 300_000  # deliberately small budget to force many batches
    store = _make_store(batch_bytes, fake)

    doc = _make_document(n_chunks=300, content_len=2000)
    await store.insert_document("documents", doc)

    # Must have used more than one insert call.
    assert len(fake.inserts) > 1, "expected multiple insert batches"
    # Every row was sent exactly once.
    assert sum(len(b) for b in fake.inserts) == 300
    # Every batch stays within the store's effective byte budget (the store
    # clamps the configured value to [1 MiB, 64 MiB]).
    for batch in fake.inserts:
        assert _estimated_batch_bytes(batch) <= store._max_batch_bytes
    # One flush per batch.
    assert fake.flush_calls == len(fake.inserts)


@pytest.mark.asyncio
async def test_small_document_uses_single_insert() -> None:
    """A small document must keep the previous single-insert behaviour."""
    fake = FakeMilvusClient()
    store = _make_store(MilvusVectorStore.DEFAULT_MAX_BATCH_BYTES, fake)

    doc = _make_document(n_chunks=10, content_len=200)
    await store.insert_document("documents", doc)

    assert len(fake.inserts) == 1
    assert len(fake.inserts[0]) == 10
    assert fake.flush_calls == 1


def test_split_batches_under_default_budget() -> None:
    """Reproduce the reported scenario: ~250 MB single message > 64 MiB limit.

    Without batching this document's rows would form a single ~250 MB gRPC
    message that the Milvus server rejects. With the default budget the rows
    must be split so each batch stays under 64 MiB.
    """
    store = _make_store(MilvusVectorStore.DEFAULT_MAX_BATCH_BYTES, FakeMilvusClient())
    rows = [
        {
            "id": f"c{i:05d}",
            "parent_doc_id": "doc-big",
            "content": "x" * (2 * 1024 * 1024),  # 2 MiB of text per row
            "vector": [0.0] * DIM,
            "metadata": {},
        }
        for i in range(120)  # ~250 MiB total payload
    ]

    batches = store._split_batches(rows)

    assert len(batches) > 1, "expected the 250 MB payload to be split"
    assert sum(len(b) for b in batches) == len(rows)
    for batch in batches:
        assert _estimated_batch_bytes(batch) <= 64 * 1024 * 1024
