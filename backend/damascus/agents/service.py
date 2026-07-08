"""
Agent Service — Business Logic
================================
Manages agent profiles and teams: creation, retrieval, update, and deletion.

Phase 2 additions:
  - Team CRUD (create_team, get_team, list_teams)
  - Agent invocation context assembly
  - Performance recording delegation
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from damascus.agents.models import (
    AgentProfile,
    AgentRole,
    AgentStatus,
    TeamDefinition,
    TeamMember,
    TeamStatus,
)
from damascus.shared.errors import AgentNotFoundError, TeamNotFoundError

log = structlog.get_logger(__name__)


class AgentService:
    # ------------------------------------------------------------------
    # Agent CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        system_prompt: str,
        capabilities: list[str] | None = None,
        model_preference: str = "ollama/llama3.1",
        tools: list[str] | None = None,
        max_iterations: int = 10,
        temperature: float = 0.7,
        role: str = AgentRole.CUSTOM,
        input_contract: dict[str, Any] | None = None,
        output_contract: dict[str, Any] | None = None,
        communication_contract: dict[str, Any] | None = None,
    ) -> AgentProfile:
        agent = AgentProfile(
            workspace_id=workspace_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            capabilities=capabilities or [],
            model_preference=model_preference,
            tools=tools or [],
            max_iterations=max_iterations,
            temperature=temperature,
            role=role,
            input_contract=input_contract or {},
            output_contract=output_contract or {},
            communication_contract=communication_contract or {},
        )
        session.add(agent)
        await session.flush()
        log.info(
            "Created agent profile",
            agent_id=agent.id,
            workspace_id=workspace_id,
            role=role,
        )
        return agent

    async def get(self, session: AsyncSession, agent_id: str) -> AgentProfile:
        agent = await session.get(AgentProfile, agent_id)
        if agent is None or agent.status == AgentStatus.DEPRECATED:
            raise AgentNotFoundError(agent_id=agent_id)
        return agent

    async def list_for_workspace(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
        role: str | None = None,
    ) -> tuple[list[AgentProfile], int]:
        from sqlalchemy import func

        base = select(AgentProfile).where(
            AgentProfile.workspace_id == workspace_id,
            AgentProfile.status == AgentStatus.ACTIVE,
        )
        if role is not None:
            base = base.where(AgentProfile.role == role)

        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(base.offset((page - 1) * per_page).limit(per_page))
        return list(result.all()), total

    # ------------------------------------------------------------------
    # Team CRUD
    # ------------------------------------------------------------------

    async def create_team(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        communication_topology: str = "sequential",
        max_iterations: int = 5,
        members: list[dict[str, Any]] | None = None,
    ) -> TeamDefinition:
        """
        Create a team with member bindings.

        members: list of {"agent_profile_id": str, "role": str, "position": int}
        """
        team = TeamDefinition(
            workspace_id=workspace_id,
            name=name,
            description=description,
            communication_topology=communication_topology,
            max_iterations=max_iterations,
        )
        session.add(team)
        await session.flush()

        # Add members
        if members:
            for idx, m in enumerate(members):
                member = TeamMember(
                    team_id=team.id,
                    agent_profile_id=m["agent_profile_id"],
                    role=m.get("role", AgentRole.CUSTOM),
                    position=m.get("position", idx),
                )
                session.add(member)
            await session.flush()

        log.info(
            "Created team",
            team_id=team.id,
            workspace_id=workspace_id,
            member_count=len(members) if members else 0,
        )
        return team

    async def get_team(self, session: AsyncSession, team_id: str) -> TeamDefinition:
        """Get a team with its members eagerly loaded."""
        result = await session.execute(
            select(TeamDefinition)
            .where(TeamDefinition.id == team_id)
            .options(selectinload(TeamDefinition.members))
        )
        team = result.scalar_one_or_none()
        if team is None or team.status == TeamStatus.ARCHIVED:
            raise TeamNotFoundError(team_id=team_id)
        return team

    async def list_teams(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[TeamDefinition], int]:
        from sqlalchemy import func

        base = select(TeamDefinition).where(
            TeamDefinition.workspace_id == workspace_id,
            TeamDefinition.status == TeamStatus.ACTIVE,
        )
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(
            base.options(selectinload(TeamDefinition.members))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.all()), total

    async def add_team_member(
        self,
        session: AsyncSession,
        *,
        team_id: str,
        agent_profile_id: str,
        role: str = AgentRole.CUSTOM,
        position: int = 0,
    ) -> TeamMember:
        """Add an agent to an existing team."""
        # Verify team and agent exist
        await self.get_team(session, team_id)
        await self.get(session, agent_profile_id)

        member = TeamMember(
            team_id=team_id,
            agent_profile_id=agent_profile_id,
            role=role,
            position=position,
        )
        session.add(member)
        await session.flush()
        log.info(
            "Added team member",
            team_id=team_id,
            agent_id=agent_profile_id,
            role=role,
        )
        return member

    async def remove_team_member(
        self,
        session: AsyncSession,
        member_id: str,
    ) -> None:
        """Remove a member from a team."""
        member = await session.get(TeamMember, member_id)
        if member is not None:
            await session.delete(member)
            await session.flush()
            log.info("Removed team member", member_id=member_id)


agent_service = AgentService()
