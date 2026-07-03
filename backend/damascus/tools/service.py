"""
Tool Service — Tool Registry and Execution
===========================================
Manages available tools and dispatches execution requests.
"""

from __future__ import annotations

from typing import Any

import structlog

from damascus.core.events.bus import event_bus
from damascus.core.events.types import EventSubject
from damascus.tools.interface import Tool, ToolResult
from damascus.tools.native.filesystem import FilesystemTool
from damascus.tools.native.terminal import TerminalTool

log = structlog.get_logger(__name__)


class ToolService:
    """
    Manages the tool registry and executes tool calls.
    V1: Native tools only (terminal, filesystem).
    Phase 2: MCP tool integration.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        # Register V1 native tools
        for tool in [TerminalTool(), FilesystemTool()]:
            self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level,
                "requires_approval": t.requires_approval,
                "schema": t.get_schema(),
            }
            for t in self._tools.values()
        ]

    async def execute(
        self,
        *,
        tool_name: str,
        workspace_id: str,
        execution_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool and publish an event."""
        tool = self.get_tool(tool_name)
        if tool is None:
            return ToolResult(success=False, output="", error=f"Tool not found: {tool_name}")

        log.info("Executing tool", tool=tool_name, workspace_id=workspace_id)
        result = await tool.execute(**kwargs)

        event_subject = EventSubject.TOOL_EXECUTED if result.success else EventSubject.TOOL_FAILED
        await event_bus.publish(
            event_subject,
            {"tool": tool_name, "execution_id": execution_id, "success": result.success},
            workspace_id=workspace_id,
        )

        return result


# Module-level singleton
tool_service = ToolService()
