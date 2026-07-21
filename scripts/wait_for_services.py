"""Wait for all backend services to be ready.

Uses protocol-appropriate health checks for each service rather than
raw HTTP (PostgreSQL and Valkey don't speak HTTP).  Respects environment
variables for port configurability:

  DATABASE_URL  → Postgres connection string (default: container port 5433)
  VALKEY_URL    → Valkey connection string   (default: container port 6380)
  MILVUS_URI    → Milvus gRPC URI            (default: port 19530)
  API_URL       → API readiness endpoint     (default: http://localhost:8100/ready)
"""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse


def _parse_host_port(url: str, default_port: int) -> tuple[str, int]:
    """Extract ``(host, port)`` from a connection URL."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    return host, port


def _check_postgres(database_url: str) -> bool:
    """Check PostgreSQL readiness via asyncpg."""
    try:
        import asyncio
        import asyncpg

        host, port = _parse_host_port(database_url, 5433)

        async def _try() -> bool:
            try:
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user="rag",
                    password="rag",
                    database="rag",
                    timeout=3.0,
                )
                await conn.close()
                return True
            except Exception:
                return False

        return asyncio.run(_try())
    except ImportError:
        return False


def _check_valkey(valkey_url: str) -> bool:
    """Check Valkey / Redis readiness via ping."""
    try:
        import redis.asyncio as redis
        import asyncio

        async def _try() -> bool:
            try:
                client = redis.from_url(valkey_url, decode_responses=True)
                await client.ping()
                await client.aclose()
                return True
            except Exception:
                return False

        return asyncio.run(_try())
    except ImportError:
        return False


def _check_milvus(milvus_uri: str) -> bool:
    """Check Milvus readiness by connecting to the gRPC port (19530).

    Uses pymilvus to list collections — a lightweight operation that verifies
    the server is alive.  Falls back to a simple TCP port check if pymilvus
    is not available.
    """
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=milvus_uri)
        client.list_collections()
        client.close()
        return True
    except Exception:
        pass

    # Fallback: check if the TCP port is open
    try:
        import socket

        host, port = _parse_host_port(milvus_uri, 19530)
        sock = socket.create_connection((host, port), timeout=3.0)
        sock.close()
        return True
    except Exception:
        return False


def _check_api(api_url: str) -> bool:
    """Check API server readiness via its /ready endpoint."""
    try:
        import httpx

        resp = httpx.get(api_url, timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def wait_for_services(timeout: int = 60) -> None:
    """Wait for all backend services to be ready.

    Args:
        timeout: Maximum wait time in seconds.
    """
    # Read connection info from environment (set via .env / .env.dev)
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://rag:rag@localhost:5433/rag"
    )
    valkey_url = os.environ.get(
        "VALKEY_URL", "redis://localhost:6380/0"
    )
    milvus_uri = os.environ.get(
        "MILVUS_URI", "http://localhost:19530"
    )
    api_url = os.environ.get(
        "API_URL", "http://localhost:8100/ready"
    )

    checks: list[tuple[str, str, object]] = [
        ("PostgreSQL", database_url, _check_postgres),
        ("Valkey",     valkey_url,  _check_valkey),
        ("Milvus",     milvus_uri,  _check_milvus),
        ("API",        api_url,     _check_api),
    ]

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        ready: list[str] = []
        for name, url, check_fn in checks:
            if check_fn(url):
                ready.append(name)

        if len(ready) == len(checks):
            print(f"All services ready: {', '.join(ready)}")
            return

        print(f"Waiting for services... ready: {', '.join(ready)}")
        time.sleep(3)

    print("Timeout waiting for services", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_services()
