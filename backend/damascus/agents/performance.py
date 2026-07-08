"""
Agent Performance Tracking Service
====================================
Records and queries agent performance metrics for evolution analysis.

Architecture constraint AG-007: Agent and team usefulness must be
benchmarkable. This service provides the data foundation.

Metrics tracked per invocation:
  - success / failure
  - quality_score (0.0 - 1.0)
  - latency_ms
  - token_usage
  - task_type

Team-level aggregation computes:
  - team success rate
  - average quality
  - total cost (token usage)
  - communication overhead
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import Float as SAFloat
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.agents.models import AgentPerformance, AgentProfile, TeamDefinition, TeamMember

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class PerformanceSummary:
    """Aggregated performance summary for an agent."""

    agent_id: str
    total_executions: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_quality_score: float
    avg_latency_ms: float
    total_token_usage: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_quality_score": round(self.avg_quality_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "total_token_usage": self.total_token_usage,
        }


@dataclass
class TeamPerformanceSummary:
    """Aggregated performance summary for a team."""

    team_id: str
    team_name: str
    member_count: int
    member_summaries: list[PerformanceSummary]
    team_success_rate: float
    team_avg_quality: float
    team_total_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "member_count": self.member_count,
            "member_summaries": [m.to_dict() for m in self.member_summaries],
            "team_success_rate": round(self.team_success_rate, 4),
            "team_avg_quality": round(self.team_avg_quality, 4),
            "team_total_tokens": self.team_total_tokens,
        }


# ---------------------------------------------------------------------------
# Performance Service
# ---------------------------------------------------------------------------


class PerformanceService:
    """Records and queries agent performance metrics."""

    async def record(
        self,
        session: AsyncSession,
        *,
        agent_profile_id: str,
        execution_id: str,
        task_type: str = "",
        success: bool = True,
        quality_score: float = 0.0,
        latency_ms: int = 0,
        token_usage: int = 0,
    ) -> AgentPerformance:
        """Record a single agent performance measurement."""
        record = AgentPerformance(
            agent_profile_id=agent_profile_id,
            execution_id=execution_id,
            task_type=task_type,
            success=success,
            quality_score=quality_score,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )
        session.add(record)
        await session.flush()
        log.info(
            "Performance recorded",
            agent_id=agent_profile_id,
            execution_id=execution_id,
            success=success,
            quality=quality_score,
        )
        return record

    async def get_agent_summary(
        self, session: AsyncSession, agent_id: str
    ) -> PerformanceSummary:
        """Compute aggregated performance summary for an agent."""
        result = await session.execute(
            select(
                func.count(AgentPerformance.id).label("total"),
                func.sum(
                    func.cast(AgentPerformance.success, SAFloat)
                ).label("successes"),
                func.avg(AgentPerformance.quality_score).label("avg_quality"),
                func.avg(
                    func.cast(AgentPerformance.latency_ms, SAFloat)
                ).label("avg_latency"),
                func.sum(AgentPerformance.token_usage).label("total_tokens"),
            ).where(AgentPerformance.agent_profile_id == agent_id)
        )
        row = result.one()
        total = row.total or 0
        successes = int(row.successes or 0)
        return PerformanceSummary(
            agent_id=agent_id,
            total_executions=total,
            success_count=successes,
            failure_count=total - successes,
            success_rate=successes / total if total > 0 else 0.0,
            avg_quality_score=float(row.avg_quality or 0.0),
            avg_latency_ms=float(row.avg_latency or 0.0),
            total_token_usage=int(row.total_tokens or 0),
        )

    async def get_recent_records(
        self,
        session: AsyncSession,
        agent_id: str,
        limit: int = 20,
    ) -> list[AgentPerformance]:
        """Return recent performance records for an agent, newest first."""
        result = await session.scalars(
            select(AgentPerformance)
            .where(AgentPerformance.agent_profile_id == agent_id)
            .order_by(AgentPerformance.recorded_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def get_team_summary(
        self, session: AsyncSession, team_id: str
    ) -> TeamPerformanceSummary:
        """
        Compute aggregated performance for an entire team
        by combining member-level summaries.
        """
        # Get team and members
        team = await session.get(TeamDefinition, team_id)
        if team is None:
            from damascus.shared.errors import TeamNotFoundError

            raise TeamNotFoundError(team_id=team_id)

        members_result = await session.scalars(
            select(TeamMember).where(TeamMember.team_id == team_id)
        )
        members = list(members_result.all())

        # Aggregate per member
        member_summaries: list[PerformanceSummary] = []
        for member in members:
            summary = await self.get_agent_summary(session, member.agent_profile_id)
            member_summaries.append(summary)

        # Team-level aggregation
        total_execs = sum(s.total_executions for s in member_summaries)
        total_successes = sum(s.success_count for s in member_summaries)
        total_tokens = sum(s.total_token_usage for s in member_summaries)
        avg_quality = (
            sum(s.avg_quality_score * s.total_executions for s in member_summaries) / total_execs
            if total_execs > 0
            else 0.0
        )

        return TeamPerformanceSummary(
            team_id=team_id,
            team_name=team.name,
            member_count=len(members),
            member_summaries=member_summaries,
            team_success_rate=total_successes / total_execs if total_execs > 0 else 0.0,
            team_avg_quality=avg_quality,
            team_total_tokens=total_tokens,
        )


# Module-level singleton
performance_service = PerformanceService()
