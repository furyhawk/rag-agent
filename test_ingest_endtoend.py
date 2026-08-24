"""End-to-end ingestion test on the patched code (parse -> chunk -> embed -> Milvus)."""
import asyncio
import traceback
from pathlib import Path

from rag_agent.core.config import get_settings
from rag_agent.pipeline.ingestion import IngestionService


async def run() -> None:
    settings = get_settings()
    print("model:", settings.embedding_model, "dim:", settings.embedding_dim)
    ingestion = IngestionService.build(
        settings=settings.rag,
        milvus_uri=settings.milvus_uri,
        milvus_token=settings.milvus_token or "",
        embedding_api_key=settings.embedding_api_key or "",
        embedding_base_url=settings.embedding_base_url or "",
        models_cache_dir=str(settings.models_cache_dir),
        milvus_max_batch_bytes=settings.milvus_max_batch_bytes,
        media_dir=settings.media_dir,
    )

    media = Path(settings.media_dir) / "rag" / "documents"
    pdfs = sorted(media.glob("*.pdf"))
    if not pdfs:
        print("no pdfs found in", media)
        return
    # Prefer one of the previously-failing docs.
    target = next((p for p in pdfs if "Beyond Algorithms" in p.name), pdfs[0])
    print("Ingesting:", target.name)

    try:
        result = await ingestion.ingest_file(
            filepath=target,
            collection_name="test_ingest",
            replace=True,
        )
        print(
            "RESULT status:",
            result.status,
            "doc_id:",
            result.document_id,
            "chunks:",
            result.chunk_count,
            "msg:",
            result.message,
        )
        if result.status == "error":
            print("ERROR:", result.error_message)
    except Exception:
        traceback.print_exc()


asyncio.run(run())
