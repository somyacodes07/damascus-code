"""
NATS Connection — Event Bus
============================
Provides the async NATS client and JetStream context for the Event Bus.
Subsystems publish and subscribe to events through this module.

Credentials: DAMASCUS_NATS_URL (see config.py)
"""

from __future__ import annotations

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from damascus.config import settings

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
_nats_client: NATSClient | None = None
_jetstream: JetStreamContext | None = None


async def get_nats() -> NATSClient:
    """Return the shared NATS client, connecting if needed."""
    global _nats_client
    if _nats_client is None or not _nats_client.is_connected:
        _nats_client = await nats.connect(settings.nats.url)
    return _nats_client


async def get_jetstream() -> JetStreamContext:
    """
    Return the JetStream context for durable pub/sub.

    Usage:
        js = await get_jetstream()
        await js.publish("damascus.events.workflow.started", payload)
    """
    global _jetstream
    if _jetstream is None:
        client = await get_nats()
        _jetstream = client.jetstream()
    return _jetstream


async def close_nats() -> None:
    """Close the NATS connection. Call on application shutdown."""
    global _nats_client, _jetstream
    if _nats_client is not None and _nats_client.is_connected:
        await _nats_client.drain()
        await _nats_client.close()
        _nats_client = None
        _jetstream = None


async def ping_nats() -> bool:
    """Check if NATS is reachable. Returns True on success."""
    try:
        client = await get_nats()
        return client.is_connected
    except Exception:
        return False
