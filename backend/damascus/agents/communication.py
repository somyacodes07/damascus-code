"""
Agent Communication — Typed Inter-Agent Messaging
===================================================
Provides structured, observable communication between agents executing
within the same workflow.

Architecture constraint AG-005: Agent communication occurs through
workflow state and typed messages — no hidden peer-to-peer channels.

Message flow:
  Agent A produces a typed message → written to workflow shared state
  → Agent B reads messages from its communication channel → processes

All messages are persisted in workflow state for observability,
replay, and evolution analysis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Message Types
# ---------------------------------------------------------------------------


class MessageType(str, Enum):
    """Typed message categories for inter-agent communication."""

    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    PROPOSAL = "PROPOSAL"
    EVIDENCE = "EVIDENCE"
    CRITIQUE = "CRITIQUE"
    DECISION_REQUEST = "DECISION_REQUEST"
    ESCALATION = "ESCALATION"
    STATUS = "STATUS"


# ---------------------------------------------------------------------------
# Message Contract
# ---------------------------------------------------------------------------


@dataclass
class AgentMessage:
    """
    A typed, traceable message between agent nodes in a workflow.

    Messages are scoped to a workflow execution and must be observable
    by the runtime and observability layer.
    """

    sender_node_id: str
    recipient_node_id: str  # or channel name for broadcast
    message_type: MessageType
    payload: dict[str, Any]
    workflow_execution_id: str

    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage in workflow shared state."""
        return {
            "message_id": self.message_id,
            "sender_node_id": self.sender_node_id,
            "recipient_node_id": self.recipient_node_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "workflow_execution_id": self.workflow_execution_id,
            "created_at": self.created_at.isoformat(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """Deserialize from workflow shared state."""
        return cls(
            message_id=data["message_id"],
            sender_node_id=data["sender_node_id"],
            recipient_node_id=data["recipient_node_id"],
            message_type=MessageType(data["message_type"]),
            payload=data["payload"],
            workflow_execution_id=data["workflow_execution_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            schema_version=data.get("schema_version", "1.0"),
        )


# ---------------------------------------------------------------------------
# Communication Channel
# ---------------------------------------------------------------------------


class CommunicationChannel:
    """
    Manages message exchange between agents through workflow shared state.

    Each workflow execution has a communication channel stored under the
    key 'agent_messages' in the shared state dict.

    Enforces:
      - Message budget limits (prevent infinite loops)
      - Size bounds per message
      - Observable message history
    """

    STATE_KEY = "agent_messages"
    DEFAULT_MESSAGE_BUDGET = 50
    MAX_PAYLOAD_SIZE_BYTES = 32_768  # 32 KB

    def __init__(
        self,
        shared_state: dict[str, Any],
        message_budget: int = DEFAULT_MESSAGE_BUDGET,
    ) -> None:
        self._state = shared_state
        self._budget = message_budget
        # Initialize messages list if not present
        if self.STATE_KEY not in self._state:
            self._state[self.STATE_KEY] = []

    @property
    def messages(self) -> list[dict[str, Any]]:
        """All messages in this channel."""
        return self._state[self.STATE_KEY]

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def budget_remaining(self) -> int:
        return max(0, self._budget - self.message_count)

    def send(self, message: AgentMessage) -> None:
        """
        Send a message to the channel.

        Raises:
            MessageBudgetExceededError: if budget is exhausted
            MessageTooLargeError: if payload exceeds size limit
        """
        import json

        # Check budget
        if self.message_count >= self._budget:
            from damascus.shared.errors import MessageBudgetExceededError

            raise MessageBudgetExceededError(
                budget=self._budget, execution_id=message.workflow_execution_id
            )

        # Check size
        payload_bytes = len(json.dumps(message.payload).encode())
        if payload_bytes > self.MAX_PAYLOAD_SIZE_BYTES:
            from damascus.shared.errors import MessageTooLargeError

            raise MessageTooLargeError(
                size_bytes=payload_bytes, max_bytes=self.MAX_PAYLOAD_SIZE_BYTES
            )

        self.messages.append(message.to_dict())
        log.debug(
            "Agent message sent",
            message_id=message.message_id,
            sender=message.sender_node_id,
            recipient=message.recipient_node_id,
            type=message.message_type.value,
        )

    def receive(self, recipient_node_id: str) -> list[AgentMessage]:
        """
        Read all messages addressed to a specific node.
        Messages are NOT removed — they persist for observability.
        """
        return [
            AgentMessage.from_dict(m)
            for m in self.messages
            if m["recipient_node_id"] == recipient_node_id
        ]

    def receive_by_type(
        self, recipient_node_id: str, message_type: MessageType
    ) -> list[AgentMessage]:
        """Read messages for a recipient filtered by type."""
        return [
            msg for msg in self.receive(recipient_node_id)
            if msg.message_type == message_type
        ]

    def get_conversation(
        self, node_a: str, node_b: str
    ) -> list[AgentMessage]:
        """
        Get the full conversation between two nodes, ordered by creation time.
        """
        return sorted(
            [
                AgentMessage.from_dict(m)
                for m in self.messages
                if (m["sender_node_id"] in (node_a, node_b)
                    and m["recipient_node_id"] in (node_a, node_b))
            ],
            key=lambda m: m.created_at,
        )

    def history(self) -> list[AgentMessage]:
        """Full message history, ordered by creation time."""
        return sorted(
            [AgentMessage.from_dict(m) for m in self.messages],
            key=lambda m: m.created_at,
        )
