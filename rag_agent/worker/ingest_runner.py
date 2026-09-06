"""Standalone subprocess that runs ONE document ingestion job.

The ARQ worker (``rag_agent.worker.settings.process_document``) spawns this
module as a separate OS process when ``WORKER_RUN_IN_SUBPROCESS=true`` (the
default). Isolating the heavy parse/embed/insert work — which loads several GB
of ML models (marker surya, sentence-transformers) — means the memory is
returned to the OS the moment the child exits: after a successful job, when
the parent cancels it on the ARQ ``job_timeout``, or when the container memory
limit OOM-kills it. The long-lived ARQ worker itself stays small.

Contract
--------
* ``--request``: path to a JSON file written by the parent:
  ``{"doc_id", "collection_name", "storage_path", "filename"}``.
* ``--result``:  path this child writes its outcome JSON to:
  ``{"ok": true, "result": {IngestionResult...}}`` or
  ``{"ok": false, "error": "..."}``.

All child logging goes to stdout/stderr (streamed by the parent); the result
is only ever written to the result file, so library output can never corrupt
it. Exit code is always 0 when a result file was written; a non-zero/absent
result file means the child was killed or crashed before finishing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from rag_agent.core.config import get_settings
from rag_agent.core.logging import setup_logging
from rag_agent.pipeline.ingestion import build_ingestion_service


def _run_ingest(
    collection_name: str,
    storage_path: str,
    filename: str,
) -> dict:
    """Build the ingestion service and run it to completion (blocking)."""
    settings = get_settings()
    print(
        f"[ingest-runner] start collection={collection_name} file={filename}",
        flush=True,
    )
    ingestion = build_ingestion_service(settings)
    result = asyncio.run(
        ingestion.ingest_file(
            filepath=Path(storage_path),
            collection_name=collection_name,
            replace=True,
            source_path=storage_path,
        )
    )
    print(f"[ingest-runner] done status={result.status.value}", flush=True)
    return result.model_dump(mode="json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a single rag-agent document ingestion job."
    )
    parser.add_argument("--request", required=True, help="JSON request file path")
    parser.add_argument("--result", required=True, help="JSON result file path")
    args = parser.parse_args(argv)

    # Match the worker's JSON logging so child progress is visible in the same
    # format when the parent streams it through.
    settings = get_settings()
    try:
        setup_logging(level=settings.log_level, log_format=settings.log_format)
    except Exception:
        pass

    request = json.loads(Path(args.request).read_text())
    try:
        result_dict = _run_ingest(
            collection_name=request["collection_name"],
            storage_path=request["storage_path"],
            filename=request["filename"],
        )
        payload: dict = {"ok": True, "result": result_dict}
    except BaseException as exc:  # noqa: BLE001 - report anything to the parent
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    Path(args.result).write_text(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
