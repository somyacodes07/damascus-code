"""
LangGraph Runtime Adapter — V1 Implementation
==============================================
Implements the IRuntime interface using LangGraph as the execution engine.

IMPORTANT: This file is the ONLY place in Damascus that imports LangGraph.
The rest of the platform uses the IRuntime interface exclusively.
This keeps the architecture independent of LangGraph's internals.

Architecture:
  Damascus Core
       ↓
  IRuntime interface
       ↓
  LangGraphAdapter  ← This file
       ↓
  LangGraph StateGraph
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, TypedDict

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from damascus.core.runtime.interface import (
    ExecutionState,
    ExecutionStatus,
    ExecutionTrace,
    IRuntime,
)
from damascus.shared.cache import get_redis

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared graph state definition
# ---------------------------------------------------------------------------


class WorkflowState(TypedDict):
    """
    The shared state that flows through a LangGraph workflow.
    Every node reads from and writes back to this state.
    """

    execution_id: str
    workspace_id: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    current_node: str
    messages: list[dict[str, Any]]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Adapter implementation
# ---------------------------------------------------------------------------


class LangGraphAdapter(IRuntime):
    """
    LangGraph-backed implementation of IRuntime.

    Translates Damascus workflow definitions into LangGraph StateGraphs,
    executes them with checkpointing via Redis, and maps results back to
    the ExecutionState/ExecutionTrace interface.
    """

    def __init__(self) -> None:
        # In-memory saver for V1. V2 will use Redis-backed saver.
        self._checkpointer = MemorySaver()
        # Active execution graph instances
        self._graphs: dict[str, Any] = {}

    def _build_graph(self, workflow_definition: dict[str, Any]) -> StateGraph:
        """
        Convert a Damascus workflow definition into a LangGraph StateGraph.

        A workflow definition looks like:
        {
          "nodes": [{"id": "...", "type": "AGENT", ...}],
          "edges": [{"from": "...", "to": "..."}]
        }
        """
        graph = StateGraph(WorkflowState)

        # Build nodes
        nodes = workflow_definition.get("nodes", [])
        for node_def in nodes:
            node_id = node_def["id"]

            async def make_node_fn(n_def: dict = node_def):
                async def node_fn(state: WorkflowState) -> WorkflowState:
                    log.info("Executing node", node_id=n_def["id"], node_type=n_def.get("type"))
                    state["current_node"] = n_def["id"]
                    # Actual agent/tool invocation happens in the Agent/Tool layers.
                    # This is a pass-through in Phase 1 scaffold.
                    return state

                return node_fn

            graph.add_node(node_id, asyncio.coroutine(make_node_fn()))

        # Build edges
        edges = workflow_definition.get("edges", [])
        for edge in edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src and dst:
                if dst == "__end__":
                    graph.add_edge(src, END)
                else:
                    graph.add_edge(src, dst)

        # Set entry point
        if nodes:
            graph.set_entry_point(nodes[0]["id"])

        return graph

    async def execute_workflow(
        self,
        execution_id: str,
        workflow_definition: dict[str, Any],
        inputs: dict[str, Any],
        workspace_id: str,
    ) -> ExecutionState:
        """Start executing a workflow and return initial state."""
        log.info(
            "Starting workflow execution", execution_id=execution_id, workspace_id=workspace_id
        )

        graph = self._build_graph(workflow_definition)
        compiled = graph.compile(checkpointer=self._checkpointer)
        self._graphs[execution_id] = compiled

        initial_state: WorkflowState = {
            "execution_id": execution_id,
            "workspace_id": workspace_id,
            "inputs": inputs,
            "outputs": {},
            "current_node": "",
            "messages": [],
            "metadata": {},
        }

        # Kick off async execution (fire and forget for non-blocking API)
        config = {"configurable": {"thread_id": execution_id}}
        asyncio.create_task(compiled.ainvoke(initial_state, config=config))

        now = datetime.now(UTC)
        return ExecutionState(
            execution_id=execution_id,
            workflow_id=workflow_definition.get("id", ""),
            workspace_id=workspace_id,
            status=ExecutionStatus.RUNNING,
            current_node=None,
            shared_state=initial_state,
            started_at=now,
            updated_at=now,
        )

    async def pause_workflow(self, execution_id: str) -> ExecutionState:
        """Pause a running workflow. V1: marks status in Redis."""
        redis = await get_redis()
        await redis.set(f"damascus:execution:{execution_id}:command", "PAUSE", ex=3600)
        now = datetime.now(UTC)
        return ExecutionState(
            execution_id=execution_id,
            workflow_id="",
            workspace_id="",
            status=ExecutionStatus.PAUSED,
            current_node=None,
            shared_state={},
            started_at=now,
            updated_at=now,
        )

    async def resume_workflow(self, execution_id: str) -> ExecutionState:
        """Resume a paused workflow."""
        redis = await get_redis()
        await redis.delete(f"damascus:execution:{execution_id}:command")
        now = datetime.now(UTC)
        return ExecutionState(
            execution_id=execution_id,
            workflow_id="",
            workspace_id="",
            status=ExecutionStatus.RUNNING,
            current_node=None,
            shared_state={},
            started_at=now,
            updated_at=now,
        )

    async def cancel_workflow(self, execution_id: str) -> ExecutionState:
        """Cancel a workflow execution."""
        redis = await get_redis()
        await redis.set(f"damascus:execution:{execution_id}:command", "CANCEL", ex=3600)
        self._graphs.pop(execution_id, None)
        now = datetime.now(UTC)
        return ExecutionState(
            execution_id=execution_id,
            workflow_id="",
            workspace_id="",
            status=ExecutionStatus.CANCELLED,
            current_node=None,
            shared_state={},
            started_at=now,
            updated_at=now,
        )

    async def get_execution_state(self, execution_id: str) -> ExecutionState:
        """Return the current execution state from the checkpointer."""
        config = {"configurable": {"thread_id": execution_id}}
        graph = self._graphs.get(execution_id)
        now = datetime.now(UTC)

        if graph is None:
            return ExecutionState(
                execution_id=execution_id,
                workflow_id="",
                workspace_id="",
                status=ExecutionStatus.FAILED,
                current_node=None,
                shared_state={},
                started_at=now,
                updated_at=now,
                error="Execution graph not found.",
            )

        state = await graph.aget_state(config)
        values = state.values if state else {}
        return ExecutionState(
            execution_id=execution_id,
            workflow_id=values.get("execution_id", ""),
            workspace_id=values.get("workspace_id", ""),
            status=ExecutionStatus.RUNNING,
            current_node=values.get("current_node"),
            shared_state=dict(values),
            started_at=now,
            updated_at=now,
        )

    async def get_execution_trace(self, execution_id: str) -> ExecutionTrace:
        """Return execution trace for observability."""
        return ExecutionTrace(
            execution_id=execution_id,
            workflow_id="",
            workspace_id="",
            nodes_executed=[],
            total_duration_ms=0,
            token_usage={},
            status=ExecutionStatus.COMPLETED,
            events=[],
        )
