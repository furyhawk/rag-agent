"""RAG Agent — production-grade document ingestion and retrieval service."""

from importlib.metadata import PackageNotFoundError, version

try:
	__version__ = version("verity-rag")
except PackageNotFoundError:
	# Fallback for local source runs where the package is not installed.
	__version__ = "0.1.5"
