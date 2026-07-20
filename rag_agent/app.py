"""FastAPI application factory with lifespan management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_agent.core.config import get_settings
from rag_agent.core.database import close_engine, init_engine
from rag_agent.core.exceptions import RAGAgentError
from rag_agent.core.logging import get_logger, setup_logging
from rag_agent.core.valkey import close_valkey, init_valkey

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle — startup and shutdown."""
    settings = get_settings()

    # Setup logging
    setup_logging(level=settings.log_level, log_format=settings.log_format)
    logger.info("app.starting", version="0.1.0")

    # Initialize infrastructure
    init_engine(settings.database_url)
    await init_valkey(settings.valkey_url)

    logger.info("app.started")
    yield

    # Shutdown
    logger.info("app.shutting_down")
    await close_valkey()
    await close_engine()
    logger.info("app.stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Initialize logging early
    setup_logging(level=settings.log_level, log_format=settings.log_format)

    app = FastAPI(
        title="RAG Agent",
        description="Production-grade document ingestion and retrieval service",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(RAGAgentError)
    async def rag_error_handler(request: Request, exc: RAGAgentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details,
            },
        )

    # Register routes
    from rag_agent.routes.health import router as health_router
    from rag_agent.routes.collections import router as collections_router
    from rag_agent.routes.documents import router as documents_router
    from rag_agent.routes.search import router as search_router
    from rag_agent.routes.sync import router as sync_router

    app.include_router(health_router)
    app.include_router(collections_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(sync_router)

    return app
