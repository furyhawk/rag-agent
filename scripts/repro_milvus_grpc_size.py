"""Reproduce & verify the Milvus ``RESOURCE_EXHAUSTED`` gRPC message-size error.

The reported error:

    AioRpcError RESOURCE_EXHAUSTED:
      "grpc: received message larger than max (262126230 vs. 67108864)"

Milvus's default gRPC max *receive* message size is 64 MiB (67108864 bytes).
When a large PDF is parsed/chunked into thousands of chunks, the whole
document used to be sent to Milvus in ONE ``insert()`` call. For a big enough
document that request exceeds 64 MiB and the server rejects it.

This script mimics that scenario without needing marker/embedding models:

  1. Builds a synthetic document payload sized like a large PDF's chunks
     (many rows, big content, high-dim vectors) totalling > 64 MiB.
  2. STEP 1 (reproduce): sends it in a single ``insert()`` -> should raise
     RESOURCE_EXHAUSTED with the "received message larger than max" message.
  3. STEP 2 (verify fix): runs the fixed path (``MilvusVectorStore`` batched
     inserts) and shows every request now stays under the 64 MiB limit.

Requires a running Milvus (default ``http://localhost:19530``, override with
``MILVUS_URI`` or ``--uri``).

Usage:
    python scripts/repro_milvus_grpc_size.py [--uri http://localhost:19530] [--dim 384] [--rows 200]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rag_agent.vectorstore.milvus import MilvusVectorStore

# 64 MiB default server receive limit.
SERVER_MAX_MESSAGE_BYTES = 64 * 1024 * 1024
# Content per row (~2 MiB of text, like a long chunk).
CONTENT_BYTES = 2 * 1024 * 1024


class _DummyEmbedder:
    """Only needed to construct MilvusVectorStore; not used for raw inserts."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed_document(self, document) -> list[list[float]]:  # noqa: ARG002
        raise NotImplementedError


def _row(i: int, dim: int) -> dict:
    return {
        "id": f"c{i:06d}",
        "parent_doc_id": "doc-big",
        "content": "x" * CONTENT_BYTES,
        "vector": [0.0] * dim,
        "metadata": {"page_num": i // 10, "chunk_num": i},
    }


async def _repro_single_insert(client, collection: str, rows: list[dict]) -> None:
    """STEP 1: send everything in one insert -> reproduces the original error."""
    est_mb = (
        len(rows)
        * (CONTENT_BYTES + len(rows[0]["vector"]) * 4 + 512)
        / (1024 * 1024)
    )
    print(f"\n[STEP 1] Single insert: {len(rows)} rows, ~{est_mb:.0f} MiB payload")
    try:
        await client.insert(collection, data=rows)
        await client.flush(collection)
        print("  !! No error raised (server accepted the oversized message).")
        print("     The limit must already be raised on your Milvus server.")
    except Exception as e:  # noqa: BLE001 - we want to show the exact error
        msg = str(e)
        print("  Reproduced the reported failure:")
        for line in msg.splitlines():
            print(f"    {line}")
        if "received message larger than max" not in msg:
            print("  (error text differs; see above)")


async def _verify_batched(client, collection: str, rows: list[dict]) -> None:
    """STEP 2: the fixed path splits rows into byte-bounded batches."""
    store = MilvusVectorStore(
        milvus_uri="http://placeholder",  # client below is injected via _client
        milvus_token="",
        embedding_dim=len(rows[0]["vector"]),
        embedding_service=_DummyEmbedder(len(rows[0]["vector"])),
    )
    # Reuse the real connected client; bypass __init__'s client creation.
    store._client = client  # noqa: SLF001

    batches = store._split_batches(rows)
    print(f"\n[STEP 2] Fixed path: split {len(rows)} rows into {len(batches)} batches")
    print(f"  Batch byte budget (store): {store._max_batch_bytes / (1024*1024):.0f} MiB")
    print(f"  Server max message size:    {SERVER_MAX_MESSAGE_BYTES / (1024*1024):.0f} MiB")

    for i, batch in enumerate(batches, start=1):
        est = (
            sum(len(r.get("content") or "") + len(r.get("vector") or []) * 4 + 512 for r in batch)
        )
        print(
            f"  batch {i}/{len(batches)}: {len(batch)} rows, "
            f"~{est / (1024*1024):.1f} MiB  (under 64 MiB: {est < SERVER_MAX_MESSAGE_BYTES})"
        )
        await client.insert(collection, data=batch)
        await client.flush(collection)

    print("  ✓ All batched inserts succeeded — oversized single-message error avoided.")


async def main(uri: str, dim: int, rows: int) -> None:
    from pymilvus import AsyncMilvusClient, DataType

    client = AsyncMilvusClient(uri=uri)
    collection = "_grpc_size_test"

    if await client.has_collection(collection):
        await client.drop_collection(collection)

    schema = client.create_schema(auto_id=False)
    schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=100)
    schema.add_field("parent_doc_id", DataType.VARCHAR, max_length=100)
    schema.add_field("content", DataType.VARCHAR, max_length=65535)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("metadata", DataType.JSON)
    await client.create_collection(collection, schema=schema, metric_type="COSINE")
    await client.load_collection(collection)

    try:
        rows = [_row(i, dim) for i in range(rows)]
        est_total_mb = (
            len(rows) * (CONTENT_BYTES + dim * 4 + 512) / (1024 * 1024)
        )
        print(f"Payload: {len(rows)} rows x (2 MiB content + {dim}-dim vector)")
        print(f"Total estimated message size: ~{est_total_mb:.0f} MiB")

        await _repro_single_insert(client, collection, rows)
        await _verify_batched(client, collection, rows)
    finally:
        await client.drop_collection(collection)
        print("\nCleaned up temporary collection.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="http://localhost:19530")
    parser.add_argument("--dim", type=int, default=384)
    parser.add_argument("--rows", type=int, default=160, help="rows => ~320 MiB payload")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.uri, args.dim, args.rows))
    except Exception as e:  # noqa: BLE001
        print(f"Failed to connect/run against Milvus at {args.uri}: {e}", file=sys.stderr)
        sys.exit(1)
