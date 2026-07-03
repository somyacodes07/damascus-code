"""
Tools API — FastAPI Router
============================
Exposes tool listing and execution endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from damascus.tools.service import tool_service

router = APIRouter(prefix="/api/v1", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    tool_name: str
    workspace_id: str
    execution_id: str = ""
    arguments: dict[str, Any] = {}


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """GET /api/v1/tools — List all available tools."""
    return {"data": tool_service.list_tools()}


@router.post("/tools/execute")
async def execute_tool(body: ToolExecuteRequest) -> dict[str, Any]:
    """POST /api/v1/tools/execute — Execute a tool."""
    result = await tool_service.execute(
        tool_name=body.tool_name,
        workspace_id=body.workspace_id,
        execution_id=body.execution_id,
        **body.arguments,
    )
    return {
        "data": {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata,
        }
    }
