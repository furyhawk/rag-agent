"""Reset all documents and vector data.

Drops all Milvus collections, truncates the tracked_documents table,
and clears Valkey job queues — leaving the database schema intact.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from rag_agent.core.config import get_settings
from rag_agent.core.logging import get_logger, setup_logging
from rag_agent.vectorstore.milvus import MilvusVectorStore

logger = get_logger(__name__)


async def reset_postgres(database_url: str, force: bool = False) -> None:
    """Truncate the tracked_documents table."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        if force:
            # CASCADE also drops dependent rows (e.g. via foreign keys)
            await conn.execute(text("TRUNCATE TABLE tracked_documents CASCADE;"))
        else:
            await conn.execute(text("TRUNCATE TABLE tracked_documents;"))
    await engine.dispose()
    logger.info("postgres.tracked_documents_truncated")


async def reset_milvus(
    milvus_uri: str, milvus_token: str, force: bool = False
) -> None:
    """Drop all Milvus collections."""
    store = MilvusVectorStore(
        milvus_uri=milvus_uri,
        milvus_token=milvus_token,
        embedding_dim=384,  # placeholder, not used for dropping
        embedding_service=None,  # type: ignore[arg-type]
    )
    names = await store.list_collections()
    if not names:
        logger.info("milvus.no_collections_to_drop")
        return
    for name in names:
        await store.delete_collection(name)
        logger.info("milvus.collection_dropped", name=name)
    logger.info("milvus.all_collections_dropped", count=len(names))


async def reset_valkey(valkey_url: str) -> None:
    """Flush Valkey/Redis job queues (db 0 only)."""
    import redis.asyncio as aredis

    client = aredis.from_url(valkey_url)
    await client.flushdb()
    await client.aclose()
    logger.info("valkey.queues_flushed")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset all documents and vector data."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Use CASCADE truncation (bypass foreign-key safety)",
    )
    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        help="Skip resetting the PostgreSQL tracked_documents table",
    )
    parser.add_argument(
        "--skip-milvus",
        action="store_true",
        help="Skip dropping Milvus collections",
    )
    parser.add_argument(
        "--skip-valkey",
        action="store_true",
        help="Skip flushing Valkey job queues",
    )
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(level=settings.log_level, log_format="console")

    logger.info("reset_documents.start", force=args.force)

    if not args.skip_postgres:
        await reset_postgres(settings.database_url, force=args.force)
    else:
        logger.info("reset_documents.skipping_postgres")

    if not args.skip_milvus:
        await reset_milvus(settings.milvus_uri, settings.milvus_token, force=args.force)
    else:
        logger.info("reset_documents.skipping_milvus")

    if not args.skip_valkey:
        await reset_valkey(settings.valkey_url)
    else:
        logger.info("reset_documents.skipping_valkey")

    logger.info("reset_documents.complete")


if __name__ == "__main__":
    asyncio.run(main())
