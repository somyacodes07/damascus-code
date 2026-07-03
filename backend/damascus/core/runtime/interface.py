"""
Runtime Interface — Abstract Contract
======================================
Defines the interface that all runtime adapters must implement.
Damascus Core depends ONLY on this interface, never on LangGraph-specific code.

This means the entire platform can swap runtimes (LangGraph → another)
by changing a single configuration line.

Concrete implementations live in:
  core/runtime/langgraph/adapter.py  (V1 implementation)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutionState:
    """
    Snapshot of a workflow execution's current state.
    Returned by get_execution_state() and used for checkpointing.
    """
    execution_id: str
    workflow_id: str
    workspace_id: str
    status: ExecutionStatus
    current_node: str | None
    shared_state: dict[str, Any]
    started_at: datetime
    updated_at: datetime
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """
    Full execution trace for observability and evolution analysis.
    Generated on completion or failure.
    """
    execution_id: str
    workflow_id: str
    workspace_id: str
    nodes_executed: list[dict[str, Any]]
    total_duration_ms: int
    token_usage: dict[str, int]
    status: ExecutionStatus
    events: list[dict[str, Any]]


class IRuntime(ABC):
    """
    Abstract runtime interface.

    Every runtime adapter (LangGraph, future runtimes) must implement this.
    Damascus Core calls this interface — never runtime-specific code.
    """

    @abstractmethod
    async def execute_workflow(
        self,
        execution_id: str,
        workflow_definition: dict[str, Any],
        inputs: dict[str, Any],
        workspace_id: str,
    ) -> ExecutionState:
        """
        Start executing a workflow definition with given inputs.
        Returns the initial execution state (usually RUNNING or PENDING).
        """
        ...

    @abstractmethod
    async def pause_workflow(self, execution_id: str) -> ExecutionState:
        """
        Pause a running workflow at the next safe checkpoint.
        Returns the updated state with status=PAUSED.
        """
        ...

    @abstractmethod
    async def resume_workflow(self, execution_id: str) -> ExecutionState:
        """
        Resume a paused workflow from its last checkpoint.
        Returns the updated state with status=RUNNING.
        """
        ...

    @abstractmethod
    async def cancel_workflow(self, execution_id: str) -> ExecutionState:
        """
        Cancel a workflow gracefully, cleaning up resources.
        Returns the final state with status=CANCELLED.
        """
        ...

    @abstractmethod
    async def get_execution_state(self, execution_id: str) -> ExecutionState:
        """Return the current state of a workflow execution."""
        ...

    @abstractmethod
    async def get_execution_trace(self, execution_id: str) -> ExecutionTrace:
        """Return the full execution trace for observability."""
        ...
