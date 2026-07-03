"""
Unit tests for the Tool service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from damascus.tools.interface import RiskLevel
from damascus.tools.service import ToolService


@pytest.fixture
def service():
    return ToolService()


def test_list_tools(service):
    """Should return all registered V1 native tools."""
    tools = service.list_tools()
    names = [t["name"] for t in tools]
    assert "terminal" in names
    assert "filesystem" in names


def test_terminal_risk_level(service):
    """Terminal tool should be HIGH risk."""
    tool = service.get_tool("terminal")
    assert tool is not None
    assert tool.risk_level == RiskLevel.HIGH
    assert tool.requires_approval is True


def test_filesystem_risk_level(service):
    """Filesystem tool should be MEDIUM risk."""
    tool = service.get_tool("filesystem")
    assert tool is not None
    assert tool.risk_level == RiskLevel.MEDIUM
    assert tool.requires_approval is False


@pytest.mark.asyncio
async def test_execute_unknown_tool(service):
    """Executing an unknown tool should return failure result."""
    result = await service.execute(
        tool_name="unknown_tool",
        workspace_id="ws_001",
    )
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_filesystem_read_nonexistent(service):
    """Reading a non-existent file should return failure."""
    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        result = await service.execute(
            tool_name="filesystem",
            workspace_id="ws_001",
            operation="read_file",
            path="/tmp/damascus_test_nonexistent_file_xyz.txt",
        )
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_filesystem_exists_operation(service, tmp_path):
    """Exists operation should return True for an existing path."""
    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        result = await service.execute(
            tool_name="filesystem",
            workspace_id="ws_001",
            operation="exists",
            path=str(tmp_path),
        )
    assert result.success is True
    assert result.output == "True"


@pytest.mark.asyncio
async def test_filesystem_write_and_read(service, tmp_path):
    """Should write a file and read it back."""
    test_file = str(tmp_path / "test.txt")
    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        write_result = await service.execute(
            tool_name="filesystem",
            workspace_id="ws_001",
            operation="write_file",
            path=test_file,
            content="Hello from Damascus",
        )
    assert write_result.success is True

    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        read_result = await service.execute(
            tool_name="filesystem",
            workspace_id="ws_001",
            operation="read_file",
            path=test_file,
        )
    assert read_result.success is True
    assert "Hello from Damascus" in read_result.output
