"""
Workspace Service — Business Logic
====================================
Implements all workspace and workflow CRUD operations.
The service layer sits between the API (HTTP) and the database.

Rules:
- Service methods accept validated Pydantic schemas
- Service methods return domain models or raise DamascusErrors
- Never expose SQLAlchemy models directly to API layer (use Pydantic responses)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.shared.errors import (
    WorkflowNotFoundError,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)
from damascus.workspace.models import (
    ExecutionStatus,
    WorkflowDefinition,
    WorkflowExecution,
    Workspace,
    WorkspaceStatus,
)

log = structlog.get_logger(__name__)


class WorkspaceService:
    """Business logic for workspace and project management."""

    # ------------------------------------------------------------------
    # Workspace CRUD
    # ------------------------------------------------------------------

    async def create_workspace(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str = "",
        owner_id: str,
        settings: dict[str, Any] | None = None,
    ) -> Workspace:
        """Create a new workspace. Raises WorkspaceAlreadyExistsError if name is taken."""
        # Check uniqueness for this owner
        stmt = select(Workspace).where(
            Workspace.owner_id == owner_id,
            Workspace.name == name,
            Workspace.status != WorkspaceStatus.DELETED,
        )
        existing = await session.scalar(stmt)
        if existing:
            raise WorkspaceAlreadyExistsError(name=name, owner_id=owner_id)

        workspace = Workspace(
            name=name,
            description=description,
            owner_id=owner_id,
            settings=settings or {},
        )
        session.add(workspace)
        await session.flush()
        log.info("Created workspace", workspace_id=workspace.id, name=name, owner_id=owner_id)
        return workspace

    async def get_workspace(self, session: AsyncSession, workspace_id: str) -> Workspace:
        """Get a workspace by ID. Raises WorkspaceNotFoundError if missing."""
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None or workspace.status == WorkspaceStatus.DELETED:
            raise WorkspaceNotFoundError(workspace_id=workspace_id)
        return workspace

    async def list_workspaces(
        self,
        session: AsyncSession,
        owner_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Workspace], int]:
        """List workspaces for an owner. Returns (items, total_count)."""
        base_stmt = select(Workspace).where(
            Workspace.owner_id == owner_id,
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await session.scalar(count_stmt) or 0

        stmt = base_stmt.order_by(Workspace.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await session.scalars(stmt)
        return list(result.all()), total

    async def update_workspace(
        self,
        session: AsyncSession,
        workspace_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Workspace:
        """Update workspace fields. Returns the updated workspace."""
        workspace = await self.get_workspace(session, workspace_id)
        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        if settings is not None:
            workspace.settings = settings
        workspace.updated_at = datetime.now(UTC)
        await session.flush()
        return workspace

    async def delete_workspace(self, session: AsyncSession, workspace_id: str) -> None:
        """Soft-delete a workspace (sets status=DELETED)."""
        workspace = await self.get_workspace(session, workspace_id)
        workspace.status = WorkspaceStatus.DELETED
        workspace.updated_at = datetime.now(UTC)
        await session.flush()
        log.info("Deleted workspace", workspace_id=workspace_id)

    # ------------------------------------------------------------------
    # Workflow CRUD
    # ------------------------------------------------------------------

    async def create_workflow(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        created_by: str,
    ) -> WorkflowDefinition:
        """Create a new workflow definition inside a workspace."""
        # Verify workspace exists
        await self.get_workspace(session, workspace_id)

        workflow = WorkflowDefinition(
            workspace_id=workspace_id,
            name=name,
            description=description,
            nodes=nodes or [],
            edges=edges or [],
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            created_by=created_by,
        )
        session.add(workflow)
        await session.flush()
        log.info("Created workflow", workflow_id=workflow.id, name=name, workspace_id=workspace_id)
        return workflow

    async def get_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
    ) -> WorkflowDefinition:
        """Get a workflow definition by ID."""
        workflow = await session.get(WorkflowDefinition, workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id=workflow_id)
        return workflow

    async def list_workflows(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[WorkflowDefinition], int]:
        """List all workflows in a workspace."""
        base_stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.workspace_id == workspace_id,
        )
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await session.scalar(count_stmt) or 0

        stmt = base_stmt.order_by(WorkflowDefinition.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await session.scalars(stmt)
        return list(result.all()), total

    # ------------------------------------------------------------------
    # Workflow Execution
    # ------------------------------------------------------------------

    async def record_execution_start(
        self,
        session: AsyncSession,
        *,
        execution_id: str,
        workflow_id: str,
        workspace_id: str,
        inputs: dict[str, Any],
        initiated_by: str = "user",
    ) -> WorkflowExecution:
        """Record a new workflow execution in the database."""
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            inputs=inputs,
            initiated_by=initiated_by,
            status=ExecutionStatus.RUNNING,
        )
        session.add(execution)
        await session.flush()
        return execution

    async def record_execution_complete(
        self,
        session: AsyncSession,
        execution_id: str,
        outputs: dict[str, Any],
        duration_ms: int,
    ) -> None:
        """Mark an execution as completed."""
        execution = await session.get(WorkflowExecution, execution_id)
        if execution:
            execution.status = ExecutionStatus.COMPLETED
            execution.outputs = outputs
            execution.completed_at = datetime.now(UTC)
            execution.duration_ms = duration_ms
            await session.flush()

    async def record_execution_failed(
        self,
        session: AsyncSession,
        execution_id: str,
        error: str,
    ) -> None:
        """Mark an execution as failed."""
        execution = await session.get(WorkflowExecution, execution_id)
        if execution:
            execution.status = ExecutionStatus.FAILED
            execution.error = error
            execution.completed_at = datetime.now(UTC)
            await session.flush()


# Module-level singleton
workspace_service = WorkspaceService()
