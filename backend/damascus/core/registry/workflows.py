"""
Workflow Registry
=================
Stores and retrieves workflow definitions, versions, and metadata.
Workflows are first-class assets — they live here with full history.

The Registry is a discovery system, NOT a memory system.
Long-term results belong to the Memory Layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.shared.errors import WorkflowNotFoundError

log = structlog.get_logger(__name__)


class WorkflowRegistry:
    """
    Manages workflow definitions in PostgreSQL.
    Used by the Runtime to look up workflow blueprints before execution.
    """

    async def register(
        self,
        session: AsyncSession,
        workspace_id: str,
        name: str,
        description: str,
        definition: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        """Register a new workflow definition."""
        import uuid

        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        log.info("Registering workflow", workflow_id=workflow_id, name=name)

        # In V1, we store this as a plain dict; the WorkflowDefinition ORM model
        # is defined in workspace/models.py and persisted there.
        return {
            "id": workflow_id,
            "workspace_id": workspace_id,
            "name": name,
            "description": description,
            "definition": definition,
            "version": 1,
            "created_by": created_by,
            "created_at": datetime.now(UTC).isoformat(),
        }

    async def get(
        self,
        session: AsyncSession,
        workflow_id: str,
    ) -> dict[str, Any]:
        """Retrieve a workflow definition by ID."""
        # Actual DB lookup is implemented in workspace/service.py via ORM
        raise WorkflowNotFoundError(workflow_id=workflow_id)

    async def list_for_workspace(
        self,
        session: AsyncSession,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """List all workflows belonging to a workspace."""
        return []


# Module-level singleton
workflow_registry = WorkflowRegistry()
