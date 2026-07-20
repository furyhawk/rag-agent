"""Scripts for the RAG agent project."""

from __future__ import annotations

import asyncio
import sys
import time


def wait_for_services(timeout: int = 60) -> None:
    """Wait for all backend services to be ready.

    Args:
        timeout: Maximum wait time in seconds.
    """
    import httpx

    services = [
        ("http://localhost:8100/ready", "API"),
        ("http://localhost:5433/", "PostgreSQL"),
        ("http://localhost:6380/", "Valkey"),
        ("http://localhost:19530/", "Milvus"),
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
