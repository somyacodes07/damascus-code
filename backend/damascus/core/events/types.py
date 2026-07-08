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
from datetime import UTC, datetime
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
    AGENT_INVOKED = "damascus.events.agent.invoked"
    AGENT_COMPLETED = "damascus.events.agent.completed"
    AGENT_FAILED = "damascus.events.agent.failed"

    # Team events (Phase 2 — Milestone 2.1)
    TEAM_CREATED = "damascus.events.team.created"
    TEAM_ASSEMBLED = "damascus.events.team.assembled"
    TEAM_COMPLETED = "damascus.events.team.completed"
    TEAM_FAILED = "damascus.events.team.failed"

    # Tool events
    TOOL_EXECUTED = "damascus.events.tool.executed"
    TOOL_FAILED = "damascus.events.tool.failed"

    # MCP events (Phase 2 — Milestone 2.3)
    MCP_SERVER_REGISTERED = "damascus.events.mcp.server_registered"
    MCP_TOOL_DISCOVERED = "damascus.events.mcp.tool_discovered"
    MCP_TOOL_EXECUTED = "damascus.events.mcp.tool_executed"

    # Model routing events (Phase 2 — Milestone 2.2)
    MODEL_ROUTED = "damascus.events.model.routed"
    MODEL_FALLBACK = "damascus.events.model.fallback"
    MODEL_PROVIDER_DEGRADED = "damascus.events.model.provider_degraded"

    # Benchmark events (Phase 2 — Milestone 2.4)
    BENCHMARK_STARTED = "damascus.events.benchmark.started"
    BENCHMARK_COMPLETED = "damascus.events.benchmark.completed"
    BENCHMARK_FAILED = "damascus.events.benchmark.failed"

    # Evolution events (Phase 2 — Milestone 2.5)
    EVOLUTION_OPPORTUNITY_FOUND = "damascus.events.evolution.opportunity_found"
    EVOLUTION_CANDIDATE_GENERATED = "damascus.events.evolution.candidate_generated"
    EVOLUTION_EXPERIMENT_STARTED = "damascus.events.evolution.experiment_started"
    EVOLUTION_EXPERIMENT_COMPLETED = "damascus.events.evolution.experiment_completed"
    EVOLUTION_PROMOTION_PROPOSED = "damascus.events.evolution.promotion_proposed"
    EVOLUTION_PROMOTION_APPROVED = "damascus.events.evolution.promotion_approved"
    EVOLUTION_PROMOTION_REJECTED = "damascus.events.evolution.promotion_rejected"
    EVOLUTION_ROLLBACK = "damascus.events.evolution.rollback"

    # Research events (Phase 2 — Milestone 2.6)
    RESEARCH_STARTED = "damascus.events.research.started"
    RESEARCH_FINDING_DISCOVERED = "damascus.events.research.finding_discovered"
    RESEARCH_COMPLETED = "damascus.events.research.completed"


@dataclass
class DamascusEvent:
    """
    Base event record.
    All events are immutable after creation.
    """

    subject: str
    payload: dict[str, Any]
    workspace_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            import uuid

            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"

    def to_json_bytes(self) -> bytes:
        """Serialize to JSON bytes for NATS publish."""
        import json

        return json.dumps(
            {
                "event_id": self.event_id,
                "subject": self.subject,
                "workspace_id": self.workspace_id,
                "occurred_at": self.occurred_at.isoformat(),
                "payload": self.payload,
            }
        ).encode()
