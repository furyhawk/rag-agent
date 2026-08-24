"""Throwaway test: parse a PDF with the OCR models skipped (OCR is disabled anyway)."""
import asyncio
import os
import traceback
import types
from pathlib import Path


class _NoopOCRErrorModel:
    disable_tqdm = False

    def __call__(self, page_texts, batch_size=0):
        return types.SimpleNamespace(labels=["good"] * len(page_texts))


class _NoopRecognitionModel:
    disable_tqdm = False

    def __call__(self, images, *args, **kwargs):
        return [types.SimpleNamespace(text_lines=[]) for _ in images]


def make_model_dict():
    from marker.models import (
        LayoutPredictor,
        TexifyPredictor,
        TableRecPredictor,
        DetectionPredictor,
        InlineDetectionPredictor,
    )

    return {
        "layout_model": LayoutPredictor(),
        "texify_model": TexifyPredictor(),
        "recognition_model": _NoopRecognitionModel(),
        "table_rec_model": TableRecPredictor(),
        "detection_model": DetectionPredictor(),
        "inline_detection_model": InlineDetectionPredictor(),
        "ocr_error_model": _NoopOCRErrorModel(),
    }


import rag_agent.parsers.pdf as pdfmod

pdfmod._get_model_dict = make_model_dict

from rag_agent.parsers.pdf import MarkerPDFParser

# Find a failing PDF in the media dir
MEDIA = "/data/media/rag/documents"
targets = [n for n in os.listdir(MEDIA) if n.lower().endswith(".pdf")]
# Prefer one of the known failing docs
targets.sort(key=lambda n: ("Database Design" in n, len(n)), reverse=True)
path = os.path.join(MEDIA, targets[0])
print("Parsing:", path)


async def run():
    parser = MarkerPDFParser(enable_ocr=False)
    try:
        doc = await parser.parse(Path(path))
        print("PARSED OK pages:", doc.num_pages)
        print("images:", sum(len(p.images) for p in doc.pages))
        print("chunks:", len(doc.chunks or []))
        if doc.chunks:
            print("first chunk (100 chars):", repr(doc.chunks[0].chunk_content[:100]))
    except Exception as e:
        print("PARSE FAILED:", type(e).__name__, repr(e))
        traceback.print_exc()


asyncio.run(run())
