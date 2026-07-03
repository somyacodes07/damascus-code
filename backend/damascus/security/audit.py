"""
Security Audit Service — V1
==============================
Records audit events for all security-relevant actions.
Every tool execution, memory access, and workspace operation is logged.

V1 storage: PostgreSQL (AuditRecord table)
Phase 2: Immutable tamper-evident audit log with cryptographic chaining.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class AuditOutcome(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    APPROVED = "APPROVED"
    FAILED = "FAILED"


class AuditService:
    """
    Records security audit events.
    V1: Logs to structured logger.
    Phase 2: Persists to tamper-evident PostgreSQL table.
    """

    async def record(
        self,
        *,
        principal_id: str,
        workspace_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: AuditOutcome,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Record an audit event.
        In V1, this writes to the structured log.
        In Phase 2, this persists to the AuditRecord table.
        """
        log.info(
            "AUDIT",
            principal_id=principal_id,
            workspace_id=workspace_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details or {},
        )


# Module-level singleton
audit_service = AuditService()
