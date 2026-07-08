"""
Unit Tests — Multi-Agent Teams (Milestone 2.1)
================================================
Tests for agent roles, team definitions, inter-agent communication,
and performance tracking.
"""

from __future__ import annotations

import pytest

from damascus.agents.communication import (
    AgentMessage,
    CommunicationChannel,
    MessageType,
)
from damascus.agents.models import AgentRole, AgentStatus, TeamStatus


# ---------------------------------------------------------------------------
# Agent Role Tests
# ---------------------------------------------------------------------------


class TestAgentRole:
    def test_standard_roles_exist(self) -> None:
        """All documented role types are present."""
        assert AgentRole.PLANNER == "PLANNER"
        assert AgentRole.RESEARCHER == "RESEARCHER"
        assert AgentRole.ARCHITECT == "ARCHITECT"
        assert AgentRole.CODER == "CODER"
        assert AgentRole.REVIEWER == "REVIEWER"
        assert AgentRole.EVALUATOR == "EVALUATOR"
        assert AgentRole.CUSTOM == "CUSTOM"

    def test_role_is_string_enum(self) -> None:
        """Roles serialize as plain strings for JSONB storage."""
        assert str(AgentRole.PLANNER) == "AgentRole.PLANNER"
        assert AgentRole.PLANNER.value == "PLANNER"


class TestTeamStatus:
    def test_team_statuses(self) -> None:
        assert TeamStatus.ACTIVE == "ACTIVE"
        assert TeamStatus.DISABLED == "DISABLED"
        assert TeamStatus.ARCHIVED == "ARCHIVED"


# ---------------------------------------------------------------------------
# Agent Communication Tests
# ---------------------------------------------------------------------------


class TestAgentMessage:
    def test_create_message(self) -> None:
        msg = AgentMessage(
            sender_node_id="node_a",
            recipient_node_id="node_b",
            message_type=MessageType.REQUEST,
            payload={"question": "What architecture should we use?"},
            workflow_execution_id="exec_123",
        )
        assert msg.sender_node_id == "node_a"
        assert msg.recipient_node_id == "node_b"
        assert msg.message_type == MessageType.REQUEST
        assert msg.message_id.startswith("msg_")
        assert msg.schema_version == "1.0"

    def test_message_serialization_roundtrip(self) -> None:
        original = AgentMessage(
            sender_node_id="researcher",
            recipient_node_id="coder",
            message_type=MessageType.EVIDENCE,
            payload={"findings": ["fact1", "fact2"]},
            workflow_execution_id="exec_456",
        )
        data = original.to_dict()
        restored = AgentMessage.from_dict(data)

        assert restored.message_id == original.message_id
        assert restored.sender_node_id == original.sender_node_id
        assert restored.recipient_node_id == original.recipient_node_id
        assert restored.message_type == original.message_type
        assert restored.payload == original.payload
        assert restored.workflow_execution_id == original.workflow_execution_id

    def test_all_message_types_exist(self) -> None:
        expected = {
            "REQUEST", "RESPONSE", "PROPOSAL", "EVIDENCE",
            "CRITIQUE", "DECISION_REQUEST", "ESCALATION", "STATUS",
        }
        actual = {t.value for t in MessageType}
        assert actual == expected


class TestCommunicationChannel:
    def test_send_and_receive(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state)

        msg = AgentMessage(
            sender_node_id="planner",
            recipient_node_id="coder",
            message_type=MessageType.REQUEST,
            payload={"task": "implement auth"},
            workflow_execution_id="exec_001",
        )
        channel.send(msg)

        received = channel.receive("coder")
        assert len(received) == 1
        assert received[0].payload["task"] == "implement auth"

        # Other agent should get no messages
        assert len(channel.receive("reviewer")) == 0

    def test_message_budget_enforcement(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state, message_budget=3)

        for i in range(3):
            channel.send(AgentMessage(
                sender_node_id="a",
                recipient_node_id="b",
                message_type=MessageType.STATUS,
                payload={"step": i},
                workflow_execution_id="exec_budget",
            ))

        # 4th message should fail
        from damascus.shared.errors import MessageBudgetExceededError

        with pytest.raises(MessageBudgetExceededError):
            channel.send(AgentMessage(
                sender_node_id="a",
                recipient_node_id="b",
                message_type=MessageType.STATUS,
                payload={"step": 3},
                workflow_execution_id="exec_budget",
            ))

    def test_message_size_limit(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state)

        # Create a payload that exceeds 32KB
        huge_payload = {"data": "x" * 40_000}

        from damascus.shared.errors import MessageTooLargeError

        with pytest.raises(MessageTooLargeError):
            channel.send(AgentMessage(
                sender_node_id="a",
                recipient_node_id="b",
                message_type=MessageType.RESPONSE,
                payload=huge_payload,
                workflow_execution_id="exec_big",
            ))

    def test_receive_by_type(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state)

        channel.send(AgentMessage(
            sender_node_id="researcher",
            recipient_node_id="coder",
            message_type=MessageType.EVIDENCE,
            payload={"finding": "use async"},
            workflow_execution_id="exec_filter",
        ))
        channel.send(AgentMessage(
            sender_node_id="reviewer",
            recipient_node_id="coder",
            message_type=MessageType.CRITIQUE,
            payload={"issue": "missing tests"},
            workflow_execution_id="exec_filter",
        ))

        evidence = channel.receive_by_type("coder", MessageType.EVIDENCE)
        assert len(evidence) == 1
        assert evidence[0].payload["finding"] == "use async"

        critiques = channel.receive_by_type("coder", MessageType.CRITIQUE)
        assert len(critiques) == 1

    def test_conversation_between_nodes(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state)

        channel.send(AgentMessage(
            sender_node_id="a",
            recipient_node_id="b",
            message_type=MessageType.REQUEST,
            payload={"q": "design?"},
            workflow_execution_id="exec_conv",
        ))
        channel.send(AgentMessage(
            sender_node_id="b",
            recipient_node_id="a",
            message_type=MessageType.RESPONSE,
            payload={"a": "microservices"},
            workflow_execution_id="exec_conv",
        ))
        channel.send(AgentMessage(
            sender_node_id="c",
            recipient_node_id="a",
            message_type=MessageType.STATUS,
            payload={"note": "unrelated"},
            workflow_execution_id="exec_conv",
        ))

        conv = channel.get_conversation("a", "b")
        assert len(conv) == 2  # excludes c's message

    def test_history_ordering(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state)

        for i in range(5):
            channel.send(AgentMessage(
                sender_node_id="a",
                recipient_node_id="b",
                message_type=MessageType.STATUS,
                payload={"step": i},
                workflow_execution_id="exec_hist",
            ))

        history = channel.history()
        assert len(history) == 5
        # Messages should be in chronological order
        for i in range(len(history) - 1):
            assert history[i].created_at <= history[i + 1].created_at

    def test_budget_remaining(self) -> None:
        state: dict = {}
        channel = CommunicationChannel(state, message_budget=10)
        assert channel.budget_remaining == 10

        channel.send(AgentMessage(
            sender_node_id="a",
            recipient_node_id="b",
            message_type=MessageType.STATUS,
            payload={},
            workflow_execution_id="exec_rem",
        ))
        assert channel.budget_remaining == 9

    def test_state_persistence(self) -> None:
        """Messages are stored in the shared state dict for workflow checkpointing."""
        state: dict = {}
        channel = CommunicationChannel(state)

        channel.send(AgentMessage(
            sender_node_id="a",
            recipient_node_id="b",
            message_type=MessageType.PROPOSAL,
            payload={"plan": "step1"},
            workflow_execution_id="exec_persist",
        ))

        # State dict should have the messages
        assert CommunicationChannel.STATE_KEY in state
        assert len(state[CommunicationChannel.STATE_KEY]) == 1

        # Another channel reading the same state should see the messages
        channel2 = CommunicationChannel(state)
        assert channel2.message_count == 1
