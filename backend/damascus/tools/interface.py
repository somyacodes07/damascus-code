"""
Tool Interface — Abstract Contract
=====================================
All tool implementations must implement this interface.
Agents never call tool implementations directly.
They go through the Tool Layer interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ToolResult:
    """The result of a tool execution."""
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """
    Abstract tool interface.
    Every tool (native or MCP) must implement this.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-readable tool name (e.g., 'terminal', 'filesystem')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """How dangerous is this tool? Affects approval requirements."""
        ...

    @property
    def requires_approval(self) -> bool:
        """Default: HIGH and CRITICAL tools require approval."""
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given arguments."""
        ...

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """Return the tool's input schema for agent consumption."""
        ...
