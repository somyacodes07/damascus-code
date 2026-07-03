"""
Redis Connection — Working Memory and Caching
=============================================
Provides the async Redis client used by the Working Memory layer,
task queues, caching, and rate limiting.

Credentials: DAMASCUS_REDIS_URL (see config.py)
"""

from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio import Redis

from damascus.config import settings

# ---------------------------------------------------------------------------
# Module-level client singleton
# ---------------------------------------------------------------------------
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """
    Return the shared async Redis client, connecting if needed.

    Usage:
        redis = await get_redis()
        await redis.set("key", "value", ex=300)
        value = await redis.get("key")
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis.url,
            db=settings.redis.db,
            max_connections=settings.redis.max_connections,
            decode_responses=True,  # Return str instead of bytes
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection. Call on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def ping_redis() -> bool:
    """Check if Redis is reachable. Returns True on success."""
    try:
        client = await get_redis()
        return await client.ping()
    except Exception:
        return False
