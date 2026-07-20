"""Health check endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rag_agent.core.database import check_connection as check_db
from rag_agent.core.valkey import check_connection as check_valkey

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — always returns 200."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/live")
async def liveness() -> dict:
    """Minimal liveness probe for container orchestrators."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — checks all dependencies."""
    checks: dict[str, dict] = {}
    overall = True

    # PostgreSQL
    start = time.monotonic()
    if await check_db():
        checks["postgres"] = {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }
    else:
        checks["postgres"] = {"status": "unhealthy", "error": "connection failed"}
        overall = False

    # Valkey
    start = time.monotonic()
    if await check_valkey():
        checks["valkey"] = {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }
    else:
        checks["valkey"] = {"status": "unhealthy", "error": "connection failed"}
        overall = False

    # Milvus (lightweight check — just import and try to connect)
    start = time.monotonic()
    try:
        from rag_agent.core.config import get_settings

        settings = get_settings()
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token or None)
        client.list_collections()
        client.close()
        checks["milvus"] = {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }
    except Exception as e:
        checks["milvus"] = {"status": "unhealthy", "error": str(e)}
        overall = False

    status_code = 200 if overall else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if overall else "degraded",
            "checks": checks,
        },
    )
