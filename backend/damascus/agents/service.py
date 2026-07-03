"""
Agent Service — Business Logic
================================
Manages agent profiles: creation, retrieval, and update.
Agents are profiles that define how AI agents behave within workflow nodes.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.agents.models import AgentProfile, AgentStatus
from damascus.shared.errors import AgentNotFoundError

log = structlog.get_logger(__name__)


class AgentService:
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
        )
        session.add(agent)
        await session.flush()
        log.info("Created agent profile", agent_id=agent.id, workspace_id=workspace_id)
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
    ) -> tuple[list[AgentProfile], int]:
        from sqlalchemy import func

        base = select(AgentProfile).where(
            AgentProfile.workspace_id == workspace_id,
            AgentProfile.status == AgentStatus.ACTIVE,
        )
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(base.offset((page - 1) * per_page).limit(per_page))
        return list(result.all()), total


agent_service = AgentService()
