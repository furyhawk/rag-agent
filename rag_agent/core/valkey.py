"""Valkey (Redis-compatible) client singleton."""

from __future__ import annotations

import redis.asyncio as redis

from rag_agent.core.config import get_settings
from rag_agent.core.logging import get_logger

logger = get_logger(__name__)

_client: redis.Redis | None = None


async def init_valkey(valkey_url: str | None = None) -> redis.Redis:
    """Initialize the Valkey client. Called once during app startup."""
    global _client

    url = valkey_url or get_settings().valkey_url
    _client = redis.from_url(url, decode_responses=True)
    # Verify connectivity
    await _client.ping()
    logger.info("valkey.connected", url=url)
    return _client


async def close_valkey() -> None:
    """Close the Valkey client. Called during app shutdown."""
    global _client
    if _client:
        await _client.aclose()
        _client = None
        logger.info("valkey.closed")


def get_valkey() -> redis.Redis:
    """Get the Valkey client singleton."""
    if _client is None:
        raise RuntimeError("Valkey client not initialized. Call init_valkey() first.")
    return _client


async def check_connection() -> bool:
    """Check if Valkey is reachable."""
    try:
        client = get_valkey()
        await client.ping()
        return True
    except Exception:
        return False
