"""Unit tests for Events."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from damascus.core.events.bus import EventBus
from damascus.core.events.types import DamascusEvent, EventSubject


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_publish_calls_local_handlers(bus):
    """Publishing an event should call registered local handlers."""
    received_events = []

    async def handler(event: DamascusEvent) -> None:
        received_events.append(event)

    bus.subscribe(EventSubject.WORKFLOW_STARTED, handler)

    with patch("damascus.shared.messaging.get_nats", new_callable=AsyncMock) as mock_nats:
        mock_nats.return_value.publish = AsyncMock()
        await bus.publish(
            EventSubject.WORKFLOW_STARTED,
            {"execution_id": "exec_test"},
            workspace_id="ws_001",
        )

    assert len(received_events) == 1
    assert received_events[0].payload["execution_id"] == "exec_test"
    assert received_events[0].workspace_id == "ws_001"


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(bus):
    """Unsubscribing should prevent the handler from being called."""
    received = []

    async def handler(event: DamascusEvent) -> None:
        received.append(event)

    bus.subscribe(EventSubject.WORKSPACE_CREATED, handler)
    bus.unsubscribe(EventSubject.WORKSPACE_CREATED, handler)

    with patch("damascus.shared.messaging.get_nats", new_callable=AsyncMock) as mock_nats:
        mock_nats.return_value.publish = AsyncMock()
        await bus.publish(EventSubject.WORKSPACE_CREATED, {}, workspace_id="ws_001")

    assert len(received) == 0


@pytest.mark.asyncio
async def test_publish_nats_failure_does_not_crash(bus):
    """NATS failures should be logged but not raise an exception."""
    with patch("damascus.shared.messaging.get_nats", side_effect=Exception("NATS down")):
        # Should not raise
        await bus.publish(EventSubject.WORKFLOW_FAILED, {"error": "test"}, workspace_id="ws_001")


def test_event_has_unique_ids():
    """Each event should have a unique event_id."""
    evt1 = DamascusEvent(subject="test", payload={}, workspace_id="ws_001")
    evt2 = DamascusEvent(subject="test", payload={}, workspace_id="ws_001")
    assert evt1.event_id != evt2.event_id
    assert evt1.event_id.startswith("evt_")


def test_event_serializes_to_json_bytes():
    """Event should serialize cleanly to JSON bytes."""
    import json
    evt = DamascusEvent(
        subject=EventSubject.MEMORY_STORED.value,
        payload={"memory_id": "mem_abc"},
        workspace_id="ws_001",
    )
    data = json.loads(evt.to_json_bytes())
    assert data["event_id"] == evt.event_id
    assert data["subject"] == evt.subject
    assert data["payload"]["memory_id"] == "mem_abc"
