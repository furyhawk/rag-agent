"""Exception hierarchy for the RAG agent service."""

from __future__ import annotations


class RAGAgentError(Exception):
    """Base exception for all RAG agent errors."""

    status_code: int = 500

    def __init__(self, message: str = "Internal server error", details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(RAGAgentError):
    """Resource not found."""

    status_code = 404

    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, **kwargs)


class BadRequestError(RAGAgentError):
    """Invalid request."""

    status_code = 400

    def __init__(self, message: str = "Bad request", **kwargs):
        super().__init__(message, **kwargs)


class IngestionError(RAGAgentError):
    """Document ingestion failed."""

    status_code = 422

    def __init__(self, message: str = "Ingestion failed", **kwargs):
        super().__init__(message, **kwargs)


class VectorStoreError(RAGAgentError):
    """Vector store operation failed."""

    status_code = 502

    def __init__(self, message: str = "Vector store error", **kwargs):
        super().__init__(message, **kwargs)


class EmbeddingError(RAGAgentError):
    """Embedding generation failed."""

    status_code = 502

    def __init__(self, message: str = "Embedding error", **kwargs):
        super().__init__(message, **kwargs)
