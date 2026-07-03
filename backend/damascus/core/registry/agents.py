"""Agent Registry — stores agent definitions, capabilities, performance metrics."""

from __future__ import annotations
import structlog

log = structlog.get_logger(__name__)


class AgentRegistry:
    """Manages agent profile registrations. Backed by PostgreSQL via agents/service.py."""

    async def list_capabilities(self) -> list[str]:
        """Return all known agent capability tags."""
        return []


agent_registry = AgentRegistry()
