"""Tests for the vendored marker font (offline PDF parsing).

Regression tests for:

    HTTPSConnectionPool(host='models.datalab.to', port=443): Max retries
    exceeded with url: /artifacts/GoNotoCurrent-Regular.ttf (Caused by
    NameResolutionError(...): Failed to resolve 'models.datalab.to' ...)

marker's ``BaseConverter.__init__`` calls ``marker.util.download_font()`` on
every ``PdfConverter`` construction when ``settings.FONT_PATH`` is missing,
downloading ``GoNotoCurrent-Regular.ttf`` from ``models.datalab.to``. In
offline/air-gapped containers that download raises a ``NameResolutionError``
and the whole ingest job fails.

``rag_agent.parsers.pdf`` vendors a copy of the font in ``./fonts`` and sets
the ``FONT_PATH`` env var (marker's ``Settings`` is a pydantic ``BaseSettings``
that reads it) before ``marker`` is imported, so ``download_font()`` finds the
font already present and never performs a network request.
"""

from __future__ import annotations

import os
from pathlib import Path

from rag_agent.parsers import pdf as pdf_parser

VENDORED_FONT = (
    Path(pdf_parser.__file__).resolve().parent / "fonts" / "GoNotoCurrent-Regular.ttf"
)


def test_pdf_parser_sets_font_path_env_var() -> None:
    """Importing the PDF parser must point marker at the vendored font."""
    font_path = os.environ.get("FONT_PATH")
    assert font_path, "FONT_PATH env var should be set on module import"
    assert font_path == str(VENDORED_FONT)


def test_vendored_font_file_exists() -> None:
    """The font referenced by FONT_PATH must actually be present."""
    assert VENDORED_FONT.is_file(), f"Vendored font missing: {VENDORED_FONT}"
    # Font is a real TrueType file (~14.7 MB); guard against truncation.
    assert VENDORED_FONT.stat().st_size > 1_000_000


def test_download_font_would_short_circuit() -> None:
    """Simulate marker.util.download_font's existence check.

    marker only downloads the font when ``settings.FONT_PATH`` does not exist,
    so with the env var pointing at a real file no network call is made.
    """
    font_path = os.environ.get("FONT_PATH")
    assert font_path is not None
    assert os.path.exists(font_path), "FONT_PATH target does not exist"
