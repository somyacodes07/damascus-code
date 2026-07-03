"""
Lifecycle Manager
==================
Manages workflow lifecycle transitions.
Ensures all transitions are valid and auditable.

Transitions:
  Created → Validated → Scheduled → Running → Completed
                                            ↘ Paused → Running
                                            ↘ Failed
                                            ↘ Cancelled
                                            ↘ Archived
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from damascus.core.events.bus import event_bus
from damascus.core.events.types import EventSubject
from damascus.core.runtime.interface import ExecutionStatus, IRuntime
from damascus.core.state.manager import state_manager
from damascus.shared.errors import ExecutionNotFoundError, WorkflowNotRunningError

log = structlog.get_logger(__name__)


class LifecycleManager:
    """
    Manages workflow execution lifecycle.
    Called by the API layer to start, pause, resume, and cancel workflows.
    """

    def __init__(self, runtime: IRuntime) -> None:
        self._runtime = runtime

    async def start_workflow(
        self,
        workflow_definition: dict[str, Any],
        inputs: dict[str, Any],
        workspace_id: str,
    ) -> str:
        """
        Start a workflow execution.
        Returns the execution_id.
        """
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        log.info("Starting workflow", execution_id=execution_id, workspace_id=workspace_id)

        execution_state = await self._runtime.execute_workflow(
            execution_id=execution_id,
            workflow_definition=workflow_definition,
            inputs=inputs,
            workspace_id=workspace_id,
        )
        await state_manager.save_state(execution_state)

        await event_bus.publish(
            EventSubject.WORKFLOW_STARTED,
            {"execution_id": execution_id, "workflow_id": workflow_definition.get("id", "")},
            workspace_id=workspace_id,
        )

        return execution_id

    async def pause_workflow(self, execution_id: str, workspace_id: str) -> None:
        """Pause a running workflow."""
        state = await state_manager.get_state(execution_id)
        if state is None:
            raise ExecutionNotFoundError(execution_id=execution_id)
        if state.status not in (ExecutionStatus.RUNNING,):
            raise WorkflowNotRunningError(execution_id=execution_id)

        await self._runtime.pause_workflow(execution_id)
        await state_manager.update_status(execution_id, ExecutionStatus.PAUSED)
        await event_bus.publish(
            EventSubject.WORKFLOW_PAUSED,
            {"execution_id": execution_id},
            workspace_id=workspace_id,
        )

    async def resume_workflow(self, execution_id: str, workspace_id: str) -> None:
        """Resume a paused workflow."""
        state = await state_manager.get_state(execution_id)
        if state is None:
            raise ExecutionNotFoundError(execution_id=execution_id)

        await self._runtime.resume_workflow(execution_id)
        await state_manager.update_status(execution_id, ExecutionStatus.RUNNING)
        await event_bus.publish(
            EventSubject.WORKFLOW_RESUMED,
            {"execution_id": execution_id},
            workspace_id=workspace_id,
        )

    async def cancel_workflow(self, execution_id: str, workspace_id: str) -> None:
        """Cancel a workflow execution."""
        await self._runtime.cancel_workflow(execution_id)
        await state_manager.update_status(execution_id, ExecutionStatus.CANCELLED)
        await event_bus.publish(
            EventSubject.WORKFLOW_CANCELLED,
            {"execution_id": execution_id},
            workspace_id=workspace_id,
        )


# Runtime is injected at application startup; lazy-initialized here
_lifecycle_manager: LifecycleManager | None = None


def get_lifecycle_manager() -> LifecycleManager:
    """Return the singleton lifecycle manager."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        from damascus.core.runtime.langgraph.adapter import LangGraphAdapter
        _lifecycle_manager = LifecycleManager(runtime=LangGraphAdapter())
    return _lifecycle_manager
