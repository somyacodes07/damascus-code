"""
Working Memory — Redis-backed
==============================
Working memory holds the active state of running workflow executions.
It is fast, temporary, and scoped to execution context.

Working memory is NOT long-term memory.
It holds data only while a workflow is active.
After completion, relevant data is promoted to Episodic or Semantic memory.

Key patterns:
  damascus:working:{workspace_id}:{execution_id}:{key}  → execution-scoped values
  damascus:working:{workspace_id}:context               → workspace context
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from damascus.shared.cache import get_redis

log = structlog.get_logger(__name__)

_WORKING_MEMORY_TTL = 3600 * 24  # 24 hours max for active workflow data


class WorkingMemory:
    """
    Manages transient execution-scoped memory in Redis.
    """

    async def set(
        self,
        workspace_id: str,
        execution_id: str,
        key: str,
        value: Any,
        ttl: int = _WORKING_MEMORY_TTL,
    ) -> None:
        """Store a value in working memory for a workflow execution."""
        redis = await get_redis()
        redis_key = f"damascus:working:{workspace_id}:{execution_id}:{key}"
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await redis.set(redis_key, serialized, ex=ttl)
        log.debug(
            "Set working memory", workspace_id=workspace_id, execution_id=execution_id, key=key
        )

    async def get(
        self,
        workspace_id: str,
        execution_id: str,
        key: str,
    ) -> Any | None:
        """Retrieve a value from working memory."""
        redis = await get_redis()
        redis_key = f"damascus:working:{workspace_id}:{execution_id}:{key}"
        raw = await redis.get(redis_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def delete(self, workspace_id: str, execution_id: str, key: str) -> None:
        """Remove a key from working memory."""
        redis = await get_redis()
        redis_key = f"damascus:working:{workspace_id}:{execution_id}:{key}"
        await redis.delete(redis_key)

    async def clear_execution(self, workspace_id: str, execution_id: str) -> None:
        """
        Remove all working memory keys for a completed execution.
        Called when a workflow finishes to free Redis memory.
        """
        redis = await get_redis()
        pattern = f"damascus:working:{workspace_id}:{execution_id}:*"
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
        log.debug("Cleared working memory", workspace_id=workspace_id, execution_id=execution_id)

    async def get_all(self, workspace_id: str, execution_id: str) -> dict[str, Any]:
        """Return all working memory values for an execution as a dict."""
        redis = await get_redis()
        pattern = f"damascus:working:{workspace_id}:{execution_id}:*"
        prefix_len = len(f"damascus:working:{workspace_id}:{execution_id}:")
        keys = await redis.keys(pattern)
        result: dict[str, Any] = {}
        for key in keys:
            short_key = key[prefix_len:]
            raw = await redis.get(key)
            if raw:
                try:
                    result[short_key] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    result[short_key] = raw
        return result


# Module-level singleton
working_memory = WorkingMemory()
