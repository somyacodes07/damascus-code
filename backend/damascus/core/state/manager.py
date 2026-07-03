"""
State Manager
=============
Maintains authoritative in-memory execution state for active workflows.
Tracks workflow status, node execution, and checkpoints.

The State Manager stores runtime-only state in Redis.
Long-term memory belongs to the Memory Layer, NOT here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from damascus.core.runtime.interface import ExecutionState, ExecutionStatus
from damascus.shared.cache import get_redis

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Redis key prefixes
# ---------------------------------------------------------------------------
_EXECUTION_KEY = "damascus:state:execution:{execution_id}"
_EXECUTION_TTL = 86400 * 7  # 7 days — long-running workflows supported


class StateManager:
    """
    Manages active workflow execution state in Redis.

    Responsibilities:
    - Store and retrieve execution state
    - Track checkpoint references
    - Support pause/resume/cancel signals
    """

    async def save_state(self, state: ExecutionState) -> None:
        """Persist an execution state snapshot to Redis."""
        redis = await get_redis()
        key = _EXECUTION_KEY.format(execution_id=state.execution_id)
        payload = {
            "execution_id": state.execution_id,
            "workflow_id": state.workflow_id,
            "workspace_id": state.workspace_id,
            "status": state.status.value,
            "current_node": state.current_node,
            "shared_state": json.dumps(state.shared_state),
            "started_at": state.started_at.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "error": state.error or "",
        }
        await redis.hset(key, mapping=payload)
        await redis.expire(key, _EXECUTION_TTL)
        log.debug("Saved execution state", execution_id=state.execution_id, status=state.status)

    async def get_state(self, execution_id: str) -> ExecutionState | None:
        """Retrieve execution state from Redis. Returns None if not found."""
        redis = await get_redis()
        key = _EXECUTION_KEY.format(execution_id=execution_id)
        data = await redis.hgetall(key)
        if not data:
            return None

        return ExecutionState(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            workspace_id=data["workspace_id"],
            status=ExecutionStatus(data["status"]),
            current_node=data.get("current_node") or None,
            shared_state=json.loads(data.get("shared_state", "{}")),
            started_at=datetime.fromisoformat(data["started_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error=data.get("error") or None,
        )

    async def update_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        error: str | None = None,
    ) -> None:
        """Update only the status field of an execution."""
        redis = await get_redis()
        key = _EXECUTION_KEY.format(execution_id=execution_id)
        updates: dict[str, str] = {
            "status": status.value,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            updates["error"] = error
        await redis.hset(key, mapping=updates)
        log.info("Updated execution status", execution_id=execution_id, status=status)

    async def delete_state(self, execution_id: str) -> None:
        """Remove execution state (e.g., after archiving)."""
        redis = await get_redis()
        key = _EXECUTION_KEY.format(execution_id=execution_id)
        await redis.delete(key)


# Module-level singleton
state_manager = StateManager()
