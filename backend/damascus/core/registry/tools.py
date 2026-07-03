"""Tool Registry — stores tool definitions, permissions, capabilities."""

from __future__ import annotations
import structlog

log = structlog.get_logger(__name__)


class ToolRegistry:
    """Manages tool registrations. Backed by PostgreSQL via tools/service.py."""

    async def get_available_tools(self, workspace_id: str) -> list[dict]:
        """Return all tools available in a workspace."""
        return []


tool_registry = ToolRegistry()
