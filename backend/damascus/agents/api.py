"""
Agent API — FastAPI Router
============================
Exposes agent profile and team management endpoints.

Phase 2 additions:
  - Team CRUD endpoints
  - Agent performance endpoint
  - Role filtering on agent list
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.agents.performance import performance_service
from damascus.agents.service import agent_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["agents"])


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------


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
    role: str = "CUSTOM"
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)


class TeamMemberInput(BaseModel):
    agent_profile_id: str
    role: str = "CUSTOM"
    position: int = 0


class TeamCreate(BaseModel):
    workspace_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    communication_topology: str = Field(default="sequential")
    max_iterations: int = Field(default=5, ge=1, le=50)
    members: list[TeamMemberInput] = Field(default_factory=list)


class AddMemberRequest(BaseModel):
    agent_profile_id: str
    role: str = "CUSTOM"
    position: int = 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def _handle(exc: DamascusError) -> HTTPException:
    m = {
        "AGENT_NOT_FOUND": 404,
        "TEAM_NOT_FOUND": 404,
        "MESSAGE_BUDGET_EXCEEDED": 429,
        "MESSAGE_TOO_LARGE": 413,
    }
    return HTTPException(
        status_code=m.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Agent serialization helper
# ---------------------------------------------------------------------------


def _serialize_agent(agent: Any) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "role": agent.role,
        "capabilities": agent.capabilities,
        "model_preference": agent.model_preference,
        "tools": agent.tools,
        "max_iterations": agent.max_iterations,
        "temperature": agent.temperature,
        "status": agent.status,
        "input_contract": agent.input_contract,
        "output_contract": agent.output_contract,
        "created_at": agent.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Agent Endpoints
# ---------------------------------------------------------------------------


@router.get("/agents")
async def list_agents(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await agent_service.list_for_workspace(
        session, workspace_id, page, per_page, role=role
    )
    data = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "role": a.role,
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
            role=body.role,
            input_contract=body.input_contract,
            output_contract=body.output_contract,
        )
        return {
            "data": {
                "id": agent.id,
                "name": agent.name,
                "workspace_id": agent.workspace_id,
                "role": agent.role,
                "status": agent.status,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    try:
        agent = await agent_service.get(session, agent_id)
        return {"data": _serialize_agent(agent)}
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/{agent_id}/performance")
async def get_agent_performance(
    agent_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Get aggregated performance summary for an agent."""
    try:
        # Verify agent exists
        await agent_service.get(session, agent_id)
        summary = await performance_service.get_agent_summary(session, agent_id)
        return {"data": summary.to_dict()}
    except DamascusError as exc:
        raise _handle(exc) from exc


# ---------------------------------------------------------------------------
# Team Endpoints
# ---------------------------------------------------------------------------


@router.post("/agents/teams", status_code=201)
async def create_team(
    body: TeamCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        team = await agent_service.create_team(
            session,
            workspace_id=body.workspace_id,
            name=body.name,
            description=body.description,
            communication_topology=body.communication_topology,
            max_iterations=body.max_iterations,
            members=[m.model_dump() for m in body.members],
        )
        return {
            "data": {
                "id": team.id,
                "name": team.name,
                "workspace_id": team.workspace_id,
                "status": team.status,
                "member_count": len(body.members),
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/teams/{team_id}")
async def get_team(
    team_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        team = await agent_service.get_team(session, team_id)
        return {
            "data": {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "workspace_id": team.workspace_id,
                "communication_topology": team.communication_topology,
                "max_iterations": team.max_iterations,
                "status": team.status,
                "members": [
                    {
                        "id": m.id,
                        "agent_profile_id": m.agent_profile_id,
                        "role": m.role,
                        "position": m.position,
                    }
                    for m in team.members
                ],
                "created_at": team.created_at.isoformat(),
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/teams")
async def list_teams(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await agent_service.list_teams(session, workspace_id, page, per_page)
    data = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "member_count": len(t.members),
            "status": t.status,
        }
        for t in items
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


@router.post("/agents/teams/{team_id}/members", status_code=201)
async def add_team_member(
    team_id: str,
    body: AddMemberRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        member = await agent_service.add_team_member(
            session,
            team_id=team_id,
            agent_profile_id=body.agent_profile_id,
            role=body.role,
            position=body.position,
        )
        return {
            "data": {
                "id": member.id,
                "team_id": team_id,
                "agent_profile_id": member.agent_profile_id,
                "role": member.role,
                "position": member.position,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/agents/teams/{team_id}/performance")
async def get_team_performance(
    team_id: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Get aggregated performance summary for a team and all its members."""
    try:
        summary = await performance_service.get_team_summary(session, team_id)
        return {"data": summary.to_dict()}
    except DamascusError as exc:
        raise _handle(exc) from exc
