"""
Agent API — FastAPI Router
============================
Exposes agent profile management endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.agents.service import agent_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["agents"])


class AgentCreate(BaseModel):
    workspace_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    system_prompt: str = Field(..., min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    model_preference: str = "ollama/llama3.1"
    tools: list[str] = Field(default_factory=list)
    max_iterations: int = Field(default=10, ge=1, le=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


def _handle(exc: DamascusError) -> HTTPException:
    m = {"AGENT_NOT_FOUND": 404}
    return HTTPException(
        status_code=m.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


@router.get("/agents")
async def list_agents(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await agent_service.list_for_workspace(session, workspace_id, page, per_page)
    data = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "capabilities": a.capabilities,
            "model_preference": a.model_preference,
            "status": a.status,
        }
        for a in items
    ]
    return {
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/agents", status_code=201)
async def create_agent(
    body: AgentCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        agent = await agent_service.create(
            session,
            workspace_id=body.workspace_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            capabilities=body.capabilities,
            model_preference=body.model_preference,
            tools=body.tools,
            max_iterations=body.max_iterations,
            temperature=body.temperature,
        )
        return {
            "data": {
                "id": agent.id,
                "name": agent.name,
                "workspace_id": agent.workspace_id,
                "status": agent.status,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    try:
        agent = await agent_service.get(session, agent_id)
        return {
            "data": {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "capabilities": agent.capabilities,
                "model_preference": agent.model_preference,
                "tools": agent.tools,
                "max_iterations": agent.max_iterations,
                "temperature": agent.temperature,
                "status": agent.status,
                "created_at": agent.created_at.isoformat(),
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc
