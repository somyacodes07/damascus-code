"""
Security Approval Service — V1
================================
Manages human approval requests for high-risk operations.

When an agent wants to execute a HIGH or CRITICAL risk tool,
it must request approval. The approval request is stored
and waits for human confirmation before execution proceeds.

V1: Approval state stored in Redis.
Phase 2: Full approval workflow with notification, escalation, and audit trail.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

from damascus.shared.cache import get_redis

log = structlog.get_logger(__name__)

_APPROVAL_KEY = "damascus:approval:{approval_id}"
_APPROVAL_TTL = 3600  # 1 hour to respond


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalService:
    """
    Manages human approval requests for risky operations.
    """

    async def request_approval(
        self,
        *,
        workspace_id: str,
        principal_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        execution_id: str,
        reason: str,
    ) -> str:
        """
        Create an approval request and return the approval_id.
        The caller must wait for the approval to be APPROVED before proceeding.
        """
        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        redis = await get_redis()
        key = _APPROVAL_KEY.format(approval_id=approval_id)
        payload = {
            "approval_id": approval_id,
            "workspace_id": workspace_id,
            "principal_id": principal_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "execution_id": execution_id,
            "reason": reason,
            "status": ApprovalStatus.PENDING,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis.set(key, json.dumps(payload), ex=_APPROVAL_TTL)
        log.info(
            "Approval requested",
            approval_id=approval_id,
            tool=tool_name,
            workspace_id=workspace_id,
        )
        return approval_id

    async def get_status(self, approval_id: str) -> ApprovalStatus:
        """Check the current status of an approval request."""
        redis = await get_redis()
        key = _APPROVAL_KEY.format(approval_id=approval_id)
        raw = await redis.get(key)
        if raw is None:
            return ApprovalStatus.EXPIRED
        data = json.loads(raw)
        return ApprovalStatus(data["status"])

    async def approve(self, approval_id: str, approver_id: str) -> None:
        """Approve a pending request."""
        await self._update_status(approval_id, ApprovalStatus.APPROVED, approver_id)
        log.info("Approval granted", approval_id=approval_id, approver=approver_id)

    async def reject(self, approval_id: str, approver_id: str) -> None:
        """Reject a pending request."""
        await self._update_status(approval_id, ApprovalStatus.REJECTED, approver_id)
        log.info("Approval rejected", approval_id=approval_id, approver=approver_id)

    async def _update_status(
        self, approval_id: str, status: ApprovalStatus, approver_id: str
    ) -> None:
        redis = await get_redis()
        key = _APPROVAL_KEY.format(approval_id=approval_id)
        raw = await redis.get(key)
        if raw:
            data = json.loads(raw)
            data["status"] = status
            data["approver_id"] = approver_id
            data["resolved_at"] = datetime.now(timezone.utc).isoformat()
            await redis.set(key, json.dumps(data), ex=_APPROVAL_TTL)


# Module-level singleton
approval_service = ApprovalService()
