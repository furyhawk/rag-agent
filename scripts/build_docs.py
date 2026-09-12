#!/usr/bin/env python3
"""Assemble the MkDocs source tree that is published to GitHub Pages.

The documentation has a single source of truth in the repository root:

    README.md    -> docs/index.md     (site Home page)
    plans/*.md   -> docs/plans/*.md   (design notes)

Both destinations are generated, git-ignored, and rewritten on every docs
build, so the published site can never drift from the README or the plan notes.

Usage (from the repository root)::

    uv run --no-project --with mkdocs-material python scripts/build_docs.py
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PLANS_DIR = ROOT / "plans"
INDEX_MD = DOCS_DIR / "index.md"
PLANS_OUT = DOCS_DIR / "plans"

# Repo-relative targets that become invalid once a file moves inside docs_dir.
PATH_REWRITES: tuple[tuple[str, str], ...] = (
    ("](docs/screenshots/", "](screenshots/"),
    ('src="docs/screenshots/', 'src="screenshots/'),
)

# Markdown image targets, used to catch broken screenshot references early.
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def clean() -> None:
    """Remove previously generated pages so deleted files do not linger."""
    for path in (PLANS_OUT, INDEX_MD):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def build_index() -> tuple[Path, list[str]]:
    """Publish README.md as the Home page and report broken image targets."""
    source = ROOT / "README.md"
    if not source.is_file():
        raise SystemExit(f"error: {source} not found")

    text = source.read_text(encoding="utf-8")
    for old, new in PATH_REWRITES:
        text = text.replace(old, new)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_MD.write_text(text, encoding="utf-8")

    missing = [
        target
        for target in IMAGE_RE.findall(text)
        if not target.startswith(("http://", "https://", "data:", "#"))
        and not (DOCS_DIR / target).is_file()
    ]
    return INDEX_MD, missing


def build_plans() -> list[Path]:
    """Mirror plans/*.md into docs/plans/ so MkDocs auto-navigates them."""
    if not PLANS_DIR.is_dir():
        return []

    written: list[Path] = []
    for source in sorted(PLANS_DIR.rglob("*.md")):
        destination = PLANS_OUT / source.relative_to(PLANS_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(destination)
    return written


def main() -> int:
    clean()
    index, missing = build_index()
    plans = build_plans()

    print(f"docs: wrote {index.relative_to(ROOT)}")
    for path in plans:
        print(f"docs: wrote {path.relative_to(ROOT)}")
    if not plans:
        print("docs: no plans/*.md found, skipping design notes")

    if missing:
        print("\ndocs: error - referenced images were not found:", file=sys.stderr)
        for target in missing:
            print(f"  - {target}", file=sys.stderr)
        return 1

    print(f"docs: home page + {len(plans)} design note(s) ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
