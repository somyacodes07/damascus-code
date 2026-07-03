"""
Event Bus — NATS pub/sub
=========================
The Event Bus is the nervous system of Damascus.
Subsystems communicate through events rather than direct dependencies.

Benefits:
- loose coupling between subsystems
- easier observability (all events are logged)
- extensibility (add subscribers without changing publishers)
- scalability (multiple subscribers can react to the same event)

Usage:
    from damascus.core.events.bus import event_bus

    # Publish
    await event_bus.publish(EventSubject.WORKFLOW_STARTED, {
        "workspace_id": "ws_abc123",
    }, workspace_id="ws_abc123")

    # Subscribe (typically done at application startup)
    await event_bus.subscribe(EventSubject.WORKFLOW_COMPLETED, my_handler)
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from damascus.core.events.types import DamascusEvent, EventSubject
from damascus.shared.messaging import get_nats

log = structlog.get_logger(__name__)

# Handler type: async function that receives a DamascusEvent
EventHandler = Callable[[DamascusEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Damascus Event Bus.

    Publishes immutable events to NATS JetStream for durable delivery.
    Local handlers can also subscribe in-process for synchronous reactions.
    """

    def __init__(self) -> None:
        self._local_handlers: dict[str, list[EventHandler]] = {}

    async def publish(
        self,
        subject: EventSubject | str,
        payload: dict[str, Any],
        workspace_id: str = "",
    ) -> None:
        """
        Publish an event to NATS.
        Also dispatches to any registered local handlers.
        """
        subject_str = subject.value if isinstance(subject, EventSubject) else subject
        event = DamascusEvent(
            subject=subject_str,
            payload=payload,
            workspace_id=workspace_id,
        )

        log.debug(
            "Publishing event",
            subject=subject_str,
            event_id=event.event_id,
            workspace_id=workspace_id,
        )

        # Publish to NATS (best effort — log failures but don't crash)
        try:
            nc = await get_nats()
            await nc.publish(subject_str, event.to_json_bytes())
        except Exception as exc:
            log.warning(
                "Failed to publish event to NATS",
                subject=subject_str,
                error=str(exc),
            )

        # Dispatch to local in-process handlers
        handlers = self._local_handlers.get(subject_str, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                log.error(
                    "Local event handler raised an error",
                    subject=subject_str,
                    error=str(exc),
                    exc_info=True,
                )

    def subscribe(self, subject: EventSubject | str, handler: EventHandler) -> None:
        """
        Register a local in-process event handler.
        The handler will be called every time the subject is published.
        """
        subject_str = subject.value if isinstance(subject, EventSubject) else subject
        if subject_str not in self._local_handlers:
            self._local_handlers[subject_str] = []
        self._local_handlers[subject_str].append(handler)
        log.debug("Registered event handler", subject=subject_str)

    def unsubscribe(self, subject: EventSubject | str, handler: EventHandler) -> None:
        """Remove a local in-process handler."""
        subject_str = subject.value if isinstance(subject, EventSubject) else subject
        handlers = self._local_handlers.get(subject_str, [])
        self._local_handlers[subject_str] = [h for h in handlers if h is not handler]


# Module-level singleton — import this everywhere
event_bus = EventBus()
