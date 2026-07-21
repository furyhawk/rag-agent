"""Wait for all backend services to be ready.

Respects environment variables so it works with both container (docker-compose)
and dev-fast (app-on-host) setups.  Override any service URL via env:

  DATABASE_URL  → extracts Postgres host:port
  VALKEY_URL    → extracts Valkey host:port
  MILVUS_URI    → extracts Milvus host:port
  API_URL       → API readiness endpoint (default http://localhost:8100/ready)
"""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse


def _parse_host_port(url: str, default_port: int) -> str:
    """Extract ``host:port`` from a connection URL, falling back to *default_port*."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    return f"{host}:{port}"


def wait_for_services(timeout: int = 60) -> None:
    """Wait for all backend services to be ready.

    Args:
        timeout: Maximum wait time in seconds.
    """
    import httpx

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

    pg_host_port = _parse_host_port(database_url, 5433)
    valkey_host_port = _parse_host_port(valkey_url, 6380)
    milvus_host_port = _parse_host_port(milvus_uri, 19530)

    services = [
        (api_url, "API"),
        (f"http://{pg_host_port}/", "PostgreSQL"),
        (f"http://{valkey_host_port}/", "Valkey"),
        (f"http://{milvus_host_port}/", "Milvus"),
    ]

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        ready = []
        for url, name in services:
            try:
                response = httpx.get(url, timeout=2.0)
                if response.status_code in (200, 503):
                    ready.append(name)
            except Exception:
                pass
        if len(ready) == len(services):
            print(f"All services ready: {', '.join(ready)}")
            return
        print(f"Waiting for services... ready: {', '.join(ready)}")
        time.sleep(2)

    print("Timeout waiting for services", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_services()
