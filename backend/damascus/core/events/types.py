"""
Damascus Event Types
====================
Defines all event types published to the NATS event bus.
Events are immutable records of things that happened.

Subject naming convention: damascus.events.{subsystem}.{event_name}
Example: damascus.events.workflow.started

All events are serialized as JSON and published via NATS JetStream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventSubject(str, Enum):
    """NATS subject strings for all Damascus event types."""

    # Workspace events
    WORKSPACE_CREATED = "damascus.events.workspace.created"
    WORKSPACE_UPDATED = "damascus.events.workspace.updated"
    WORKSPACE_DELETED = "damascus.events.workspace.deleted"

    # Workflow lifecycle events
    WORKFLOW_CREATED = "damascus.events.workflow.created"
    WORKFLOW_STARTED = "damascus.events.workflow.started"
    WORKFLOW_PAUSED = "damascus.events.workflow.paused"
    WORKFLOW_RESUMED = "damascus.events.workflow.resumed"
    WORKFLOW_COMPLETED = "damascus.events.workflow.completed"
    WORKFLOW_FAILED = "damascus.events.workflow.failed"
    WORKFLOW_CANCELLED = "damascus.events.workflow.cancelled"

    # Node execution events
    NODE_STARTED = "damascus.events.node.started"
    NODE_COMPLETED = "damascus.events.node.completed"
    NODE_FAILED = "damascus.events.node.failed"

    # Memory events
    MEMORY_STORED = "damascus.events.memory.stored"
    MEMORY_RETRIEVED = "damascus.events.memory.retrieved"

    # Agent events
    AGENT_ASSIGNED = "damascus.events.agent.assigned"
    AGENT_COMPLETED = "damascus.events.agent.completed"

    # Tool events
    TOOL_EXECUTED = "damascus.events.tool.executed"
    TOOL_FAILED = "damascus.events.tool.failed"

    # Evolution events (Phase 2)
    EVOLUTION_CANDIDATE_GENERATED = "damascus.events.evolution.candidate_generated"
    EVOLUTION_EXPERIMENT_STARTED = "damascus.events.evolution.experiment_started"
    EVOLUTION_EXPERIMENT_COMPLETED = "damascus.events.evolution.experiment_completed"

    # Benchmark events (Phase 2)
    BENCHMARK_COMPLETED = "damascus.events.benchmark.completed"

    # Research events (Phase 2)
    RESEARCH_DISCOVERED = "damascus.events.research.discovered"


@dataclass
class DamascusEvent:
    """
    Base event record.
    All events are immutable after creation.
    """
    subject: str
    payload: dict[str, Any]
    workspace_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            import uuid
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"

    def to_json_bytes(self) -> bytes:
        """Serialize to JSON bytes for NATS publish."""
        import json
        return json.dumps({
            "event_id": self.event_id,
            "subject": self.subject,
            "workspace_id": self.workspace_id,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
        }).encode()
