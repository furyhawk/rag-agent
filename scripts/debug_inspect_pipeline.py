#!/usr/bin/env python
"""Debug tool: inspect artifacts produced by the document pipeline on a PDF.

Runs the real pipeline (parse -> describe images -> chunk) on a PDF and dumps
every artifact into a local folder for inspection.

If no ``--pdf`` is given, a representative sample PDF is generated on the fly
(text, a ruled table, an embedded image, repeated header/footer, metadata)
using PyMuPDF, so the whole artifact surface is exercised.

Artifact layout (``--out``, default ``debug_artifacts/``)::

    debug_artifacts/
    ├── input/                       # the PDF that was processed
    ├── document.json                # full Document model (pages, chunks, metadata)
    ├── metadata.json                # DocumentMetadata incl. PDF extras (title/author/toc)
    ├── summary.txt                  # human-readable overview
    ├── pages/
    │   ├── page_001.txt ...         # raw per-page extracted content (as parsed)
    ├── chunks/
    │   ├── chunks.json              # chunk metadata (id, num, page, len, preview, images)
    │   ├── chunk_001.txt ...        # chunk contents, one file per chunk
    └── media/
        └── images/<collection>/<doc_id>/<image_id>.<ext>   # extracted images,
                                                            # persisted via LocalFileStorage
                                                            # (mirrors production layout)

Usage::

    python scripts/debug_inspect_pipeline.py [--pdf path/to/file.pdf]
        [--out debug_artifacts] [--strategy recursive|markdown]
        [--chunk-size 512] [--chunk-overlap 50] [--describe] [--ocr]
        [--preview 400]           # preview length in document.json; 0 = full text
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Allow running as `python scripts/debug_inspect_pipeline.py` without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_agent.core.config import RAGSettings  # noqa: E402
from rag_agent.models.document import Document, DocumentImage  # noqa: E402
from rag_agent.pipeline.file_storage import LocalFileStorage  # noqa: E402
from rag_agent.pipeline.processor import DocumentProcessor  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Sample PDF generation (only used when --pdf is not provided)
# ─────────────────────────────────────────────────────────────────────────────

class _StubImageDescriber:
    """Deterministic stand-in for the LLM vision describer (no network)."""

    async def describe(
        self, image_bytes: bytes, mime_type: str = "image/png"
    ) -> str:
        return (
            f"[debug] generated description: {len(image_bytes)} bytes, "
            f"mime={mime_type}"
        )


def _make_chart_png() -> bytes:
    """Render a small bar-chart as a real embedded raster image (PNG)."""
    import pymupdf

    chart = pymupdf.open()
    page = chart.new_page(width=520, height=340)
    bars = [(40, 120), (115, 210), (190, 150), (265, 270), (340, 95)]
    for x, h in bars:
        page.draw_rect(
            pymupdf.Rect(x, 315 - h, x + 48, 315),
            color=(0.15, 0.35, 0.8),
            fill=(0.15, 0.35, 0.8),
        )
    # axes
    page.draw_line(pymupdf.Point(25, 315), pymupdf.Point(500, 315))
    page.draw_line(pymupdf.Point(25, 20), pymupdf.Point(25, 315))
    pix = page.get_pixmap(dpi=150)
    return pix.tobytes("png")


def _insert_paragraph(
    page: Any, text: str, y: float, fontsize: int = 10, width: float = 495
) -> float:
    """Insert wrapped paragraph text, returning the new y cursor."""
    import pymupdf

    rect = pymupdf.Rect(50, y, 50 + width, 830)
    rc = page.insert_textbox(rect, text, fontsize=fontsize)
    used = rect.height - rc if rc > 0 else rect.height
    return y + used + 8


def _draw_table(page: Any, y0: float) -> None:
    """Draw a ruled 4x4 table so PyMuPDF's find_tables() can detect it."""
    import pymupdf

    x0, x1, x2, x3, x4 = 50, 170, 290, 410, 545
    n_rows = 5
    y = y0
    for _ in range(n_rows):
        page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x4, y))
        y += 22
    page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x4, y))
    for x in (x0, x1, x2, x3, x4):
        page.draw_line(pymupdf.Point(x, y0), pymupdf.Point(x, y))

    rows = [
        ["Metric", "Q1", "Q2", "Total"],
        ["Chunks", "120", "145", "265"],
        ["Pages", "40", "55", "95"],
        ["Images", "8", "12", "20"],
        ["Avg len", "512", "490", "501"],
    ]
    for r, row in enumerate(rows):
        cy = y0 + r * 22 + 15
        for i, cell in enumerate(row):
            page.insert_text(
                pymupdf.Point([x0, x1, x2, x3][i] + 5, cy), cell, fontsize=9
            )


def _generate_sample_pdf(path: Path) -> Path:
    """Create a representative PDF: text, table, image, header/footer, metadata."""
    import pymupdf

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    doc.set_metadata(
        {
            "title": "Sample RAG Pipeline Report",
            "author": "Debug Inspection Tool",
            "subject": "Artifact inspection",
        }
    )
    page_w, page_h = 595, 842

    header_text = "Sample RAG Pipeline Report"
    footer_text = "Confidential - Sample RAG Report"

    def new_page() -> Any:
        page = doc.new_page(width=page_w, height=page_h)
        # Header + footer (repeated on every page -> header/footer detection).
        page.insert_text(pymupdf.Point(50, 32), header_text, fontsize=11)
        page.draw_line(pymupdf.Point(50, 40), pymupdf.Point(545, 40))
        # Footer on its own line; page number on a separate baseline so the
        # footer block is byte-identical across pages -> parser's repeated-
        # content detection removes it from every page.
        page.insert_text(pymupdf.Point(50, 810), footer_text, fontsize=9)
        page.insert_text(
            pymupdf.Point(500, 824), f"Page {doc.page_count}", fontsize=9
        )
        return page

    # ── Page 1: title, intro, table ─────────────────────────────────────
    page = new_page()
    y = _insert_paragraph(
        page,
        "Quarterly Ingestion Report\n\n"
        "This report summarizes document ingestion and retrieval metrics for "
        "the RAG platform over the last quarter. It is used by the debug "
        "pipeline inspector to exercise text extraction, table detection, "
        "image extraction, and chunking in a single pass.",
        70,
        fontsize=12,
    )
    _insert_paragraph(
        page,
        "Pipeline Overview\n\n"
        "The ingestion pipeline parses each uploaded file, optionally describes "
        "embedded images with a vision model, and then splits the extracted "
        "content into overlapping chunks. Chunks are embedded and stored in a "
        "vector database for semantic retrieval. The table below summarizes "
        "the volume processed this quarter.",
        y,
    )
    _draw_table(page, 300)

    # ── Page 2: long body text (exercises multi-chunk splitting) ────────
    page = new_page()
    body = (
        "Chunking Strategy\n\n"
        "The recursive character splitter walks through a list of separators - "
        "paragraph breaks, newlines, sentence punctuation, and words - and "
        "recursively splits the text until each piece is within the target "
        "chunk size. This keeps related sentences together and preserves "
        "natural boundaries wherever possible, which generally produces better "
        "retrieval quality than fixed-size splitting.\n\n"
        "Overlap is deliberately added between consecutive chunks. When a query "
        "spans a chunk boundary, the overlapping tail ensures the relevant "
        "context is present in both chunks, so retrieval does not miss content "
        "that happens to straddle the cut point. The overlap also helps the "
        "reranker compare neighbouring passages without losing continuity.\n\n"
        "Hybrid search combines dense vector similarity with sparse keyword "
        "scoring. Dense embeddings capture semantic similarity, while keyword "
        "matching handles exact terms, identifiers, and rare acronyms that "
        "embeddings may gloss over. Scores from both branches are normalized "
        "and fused before reranking, yielding a single ranked result list.\n\n"
        "Header and footer text is detected by looking for blocks that appear "
        "repeatedly at the top or bottom of most pages. Repeated blocks such as "
        "page numbers, titles, and confidentiality notices are removed before "
        "chunking so they do not pollute the embeddings with boilerplate.\n\n"
        "Tables are converted to markdown so their structure and cell values "
        "survive into the chunk text. Markdown tables render compactly and "
        "remain readable for both the embedding model and the reranker."
    )
    _insert_paragraph(page, body, 70, fontsize=10)

    # ── Page 3: embedded image + caption ────────────────────────────────
    page = new_page()
    _insert_paragraph(
        page,
        "Image Extraction\n\n"
        "Raster images embedded in the PDF are extracted and, when enabled, "
        "described by a vision model. The descriptions are appended to the page "
        "content so that image information becomes searchable through normal "
        "text embeddings.",
        70,
        fontsize=10,
    )
    chart_png = _make_chart_png()
    img_rect = pymupdf.Rect(90, 180, 90 + 415, 180 + 271)
    page.insert_image(img_rect, stream=chart_png)
    _insert_paragraph(
        page,
        "Figure 1: Quarterly chunk volume by service tier. The extracted image "
        "above is a raster asset that the parser will pick up via "
        "page.get_images() and persist alongside the document.",
        470,
        fontsize=10,
    )

    # ── Page 4: closing text ─────────────────────────────────────────────
    page = new_page()
    _insert_paragraph(
        page,
        "Conclusion\n\n"
        "The artifacts produced by this pass - per-page text, extracted tables, "
        "image descriptions, and the final chunk list - are written to the "
        "output directory for inspection. Use the summary and the individual "
        "files to verify that parsing and chunking behave as expected before "
        "embedding and storing the document in the vector store.",
        70,
        fontsize=10,
    )

    doc.save(path)
    doc.close()
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────────────────────────────────────

def _image_summary(image: DocumentImage) -> dict[str, Any]:
    """Image metadata WITHOUT raw bytes (keeps document.json small/readable)."""
    return {
        "image_id": image.image_id,
        "page_num": image.page_num,
        "mime_type": image.mime_type,
        "byte_size": len(image.image_bytes),
        "description": image.description,
    }


def _doc_jsonable(document: Document, preview: int) -> dict[str, Any]:
    """Serialize a Document into a JSON-friendly dict (bytes stripped)."""
    def content_text(text: str) -> str:
        if preview and len(text) > preview:
            return text[:preview] + f"...<truncated {len(text) - preview} chars>"
        return text

    return {
        "id": document.id,
        "num_pages": document.num_pages,
        "num_chunks": document.num_chunks,
        "ingested_at": document.ingested_at.isoformat()
        if document.ingested_at
        else None,
        "metadata": document.metadata.model_dump(mode="json"),
        "pages": [
            {
                "page_id": page.page_id,
                "page_num": page.page_num,
                "char_count": len(page.content),
                "content": content_text(page.content),
                "images": [_image_summary(i) for i in page.images],
            }
            for page in document.pages
        ],
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_num": chunk.chunk_num,
                "page_num": chunk.page_num,
                "page_id": chunk.page_id,
                "char_count": len(chunk.chunk_content),
                "content": content_text(chunk.chunk_content),
                "images": [_image_summary(i) for i in chunk.images],
            }
            for chunk in (document.chunks or [])
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _importable(name: str) -> bool:
    """Return True if a module can be imported (soft dependency check)."""
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _count_raw_tables(pdf_path: Path) -> int:
    """Count tables PyMuPDF can detect directly from the PDF (raw)."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        total = 0
        for page in doc:
            try:
                tables = page.find_tables()
                total += len(tables.tables) if tables else 0
            except Exception:
                pass
        return total
    finally:
        doc.close()


def _count_markdown_tables(document: Document) -> int:
    """Count pages whose extracted content contains markdown-table pipes."""
    return sum(1 for p in document.pages if "|" in p.content)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--pdf", type=Path, default=None,
        help="PDF to process. If omitted, a sample PDF is generated.",
    )
    p.add_argument(
        "--out", type=Path, default=Path("debug_artifacts"),
        help="Output folder for artifacts (default: debug_artifacts).",
    )
    p.add_argument(
        "--strategy", choices=["recursive", "markdown"], default="recursive",
        help="Chunking strategy (default: recursive).",
    )
    p.add_argument("--chunk-size", type=int, default=512)
    p.add_argument("--chunk-overlap", type=int, default=50)
    p.add_argument(
        "--describe", action="store_true",
        help="Attach a stub image describer so image descriptions appear in "
        "page/chunk content (no network call).",
    )
    p.add_argument(
        "--ocr", action="store_true",
        help="Enable OCR fallback for scanned pages (requires an image "
        "describer; no-op without --describe or a real vision LLM).",
    )
    p.add_argument(
        "--preview", type=int, default=400,
        help="Preview length for content in document.json; 0 = full text.",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> int:
    out = args.out
    (out / "input").mkdir(parents=True, exist_ok=True)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    (out / "chunks").mkdir(parents=True, exist_ok=True)

    # 1. Resolve input PDF (copy provided, or generate a sample).
    if args.pdf:
        pdf_path = out / "input" / args.pdf.name
        pdf_path.write_bytes(args.pdf.read_bytes())
        print(f"Using PDF: {args.pdf} (copied to {pdf_path})")
    else:
        pdf_path = _generate_sample_pdf(out / "input" / "sample_report.pdf")
        print(f"Generated sample PDF: {pdf_path}")

    # 2. Run the real pipeline: parse -> describe -> chunk.
    settings = RAGSettings(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        chunking_strategy=args.strategy,
        enable_ocr=args.ocr,
    )
    describer = _StubImageDescriber() if args.describe else None
    processor = DocumentProcessor(settings=settings, image_describer=describer)
    document = await processor.process_file(pdf_path)

    # 3. Persist artifacts.
    (out / "document.json").write_text(
        json.dumps(_doc_jsonable(document, args.preview), indent=2)
    )
    (out / "metadata.json").write_text(
        json.dumps(document.metadata.model_dump(mode="json"), indent=2)
    )

    page_files: list[Path] = []
    for page in document.pages:
        f = out / "pages" / f"page_{page.page_num:03d}.txt"
        f.write_text(page.content if page.content else "(empty page)")
        page_files.append(f)

    chunk_files: list[Path] = []
    chunks_meta: list[dict[str, Any]] = []
    for idx, chunk in enumerate(document.chunks or [], start=1):
        f = out / "chunks" / f"chunk_{idx:03d}.txt"
        f.write_text(chunk.chunk_content)
        chunk_files.append(f)
        chunks_meta.append(
            {
                "idx": idx,
                "chunk_id": chunk.chunk_id,
                "chunk_num": chunk.chunk_num,
                "page_num": chunk.page_num,
                "char_count": len(chunk.chunk_content),
                "file": f.name,
                "preview": chunk.chunk_content[:200],
                "images": [_image_summary(i) for i in chunk.images],
            }
        )
    (out / "chunks" / "chunks.json").write_text(
        json.dumps(chunks_meta, indent=2)
    )

    # Images persisted via LocalFileStorage -> mirrors production layout:
    # <out>/media/images/<collection>/<doc_id>/<image_id>.<ext>
    storage = LocalFileStorage(out / "media")
    saved_images: list[Path] = []
    for page in document.pages:
        for image in page.images:
            if not image.image_bytes:
                continue
            path = await storage.save_image(
                image_id=image.image_id,
                data=image.image_bytes,
                mime_type=image.mime_type,
                collection="debug",
                document_id=document.id,
            )
            saved_images.append(path)

    # 4. Summary.
    lines: list[str] = [
        "Debug artifact inspection",
        "========================",
        "",
        f"Input PDF     : {pdf_path} ({pdf_path.stat().st_size} bytes)",
        f"Content hash  : {document.metadata.content_hash}",
        f"Pipeline      : strategy={settings.chunking_strategy} "
        f"chunk_size={settings.chunk_size} overlap={settings.chunk_overlap} "
        f"ocr={settings.enable_ocr} describe={bool(describer)}",
        f"Document      : id={document.id}",
        f"Pages         : {document.num_pages}",
        f"Chunks        : {document.num_chunks}",
        f"Images        : {len(saved_images)} extracted, "
        f"{len(document.pages)} pages with images",
        "",
        "Pages (per-page extracted content)",
        "---------------------------------",
    ]
    for page in document.pages:
        n_img = len(page.images)
        lines.append(
            f"  page {page.page_num:>3}: {len(page.content):>6} chars"
            + (f", {n_img} image(s)" if n_img else "")
        )

    lines += [
        "",
        "Chunks (final split)",
        "---------------------",
    ]
    for idx, chunk in enumerate(document.chunks or [], start=1):
        lines.append(
            f"  chunk {idx:>3} (num={chunk.chunk_num:>2}, page={chunk.page_num:>2}): "
            f"{len(chunk.chunk_content):>6} chars :: {chunk.chunk_content[:60]!r}"
        )

    lines += [
        "",
        "Saved images (via LocalFileStorage, production layout)",
        "------------------------------------------------------",
    ]
    if saved_images:
        for p in saved_images:
            lines.append(f"  {p.relative_to(out)}")
    else:
        lines.append("  (none extracted)")

    # 5. Diagnostics — surface silent pipeline failures.
    raw_tables = _count_raw_tables(pdf_path)
    md_tables = _count_markdown_tables(document)
    has_marker = _importable("marker")
    lines += [
        "",
        "Diagnostics",
        "------------",
        f"  marker   : {'available' if has_marker else 'MISSING'} (PDF parser)",
    ]
    if raw_tables > 0 and md_tables == 0:
        lines.append(
            f"  WARNING: PyMuPDF found {raw_tables} raw table(s), but 0 markdown "
            "table(s) landed in page content."
        )
        lines.append(
            "    Note: marker (PDF parser) reconstructs tables internally; if "
            "they are missing, check the marker output/version."
        )
    elif raw_tables > 0:
        lines.append(
            f"  OK: {raw_tables} raw table(s) -> {md_tables} page(s) with "
            "markdown tables."
        )
    else:
        lines.append("  No tables detected in the PDF.")

    lines += [
        "",
        "Artifacts written to:",
        f"  {out.resolve()}",
        "  |- document.json",
        "  |- metadata.json",
        "  |- summary.txt",
        f"  |- pages/       ({len(page_files)} file(s))",
        f"  |- chunks/      ({len(chunk_files)} file(s) + chunks.json)",
        f"  |- media/       (images, {len(saved_images)} file(s))",
        f"  |- input/       ({pdf_path.name})",
        "",
    ]

    (out / "summary.txt").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
