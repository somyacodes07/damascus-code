"""
Agent — ORM Models
===================
Defines the AgentProfile, AgentPerformance, TeamDefinition, and TeamMember
database models.

Phase 2 additions:
  - AgentRole enum for typed specialization
  - Role, input_contract, output_contract on AgentProfile
  - TeamDefinition — a named group of agents that collaborate in workflows
  - TeamMember — binds an agent to a team with role and position
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from damascus.shared.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"


class AgentRole(str, Enum):
    """
    Standard agent role types (architecture doc AG-002).
    CUSTOM allows user-defined roles beyond the standard set.
    """

    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    ARCHITECT = "ARCHITECT"
    CODER = "CODER"
    REVIEWER = "REVIEWER"
    EVALUATOR = "EVALUATOR"
    CUSTOM = "CUSTOM"


class TeamStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_agent_id() -> str:
    return f"ag_{uuid.uuid4().hex[:12]}"


def _new_team_id() -> str:
    return f"tm_{uuid.uuid4().hex[:12]}"


def _new_member_id() -> str:
    return f"mbr_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Agent Profile
# ---------------------------------------------------------------------------


class AgentProfile(Base):
    """
    An agent profile defines a specialized agent's capabilities and behavior.
    Agents are execution primitives inside workflows — not standalone entities.
    """

    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_agent_id)
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)
    model_preference: Mapped[str] = mapped_column(String(255), default="ollama/llama3.1")
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    max_iterations: Mapped[int] = mapped_column(Integer, default=10)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    status: Mapped[str] = mapped_column(String(32), default=AgentStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # --- Phase 2 fields ---
    role: Mapped[str] = mapped_column(String(32), default=AgentRole.CUSTOM, nullable=False)
    input_contract: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_contract: Mapped[dict] = mapped_column(JSONB, default=dict)
    communication_contract: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    performance_records: Mapped[list[AgentPerformance]] = relationship(
        "AgentPerformance", back_populates="agent", cascade="all, delete-orphan"
    )
    team_memberships: Mapped[list[TeamMember]] = relationship(
        "TeamMember", back_populates="agent", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Agent Performance
# ---------------------------------------------------------------------------


class AgentPerformance(Base):
    """Tracks agent performance metrics over time for evolution analysis."""

    __tablename__ = "agent_performance"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: f"perf_{uuid.uuid4().hex[:12]}"
    )
    agent_profile_id: Mapped[str] = mapped_column(
        ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(128), default="")
    success: Mapped[bool] = mapped_column(default=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    agent: Mapped[AgentProfile] = relationship("AgentProfile", back_populates="performance_records")


# ---------------------------------------------------------------------------
# Team Definition
# ---------------------------------------------------------------------------


class TeamDefinition(Base):
    """
    A named group of agents that collaborate within a workflow.
    Teams are explicit, observable workflow structures — not hidden coordination.
    """

    __tablename__ = "team_definitions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_team_id)
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    communication_topology: Mapped[str] = mapped_column(
        String(64), default="sequential", nullable=False
    )
    max_iterations: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(32), default=TeamStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    members: Mapped[list[TeamMember]] = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan",
        order_by="TeamMember.position",
    )


# ---------------------------------------------------------------------------
# Team Member
# ---------------------------------------------------------------------------


class TeamMember(Base):
    """Binds an agent profile to a team with a role and execution order."""

    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_member_id)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("team_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_profile_id: Mapped[str] = mapped_column(
        ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    team: Mapped[TeamDefinition] = relationship("TeamDefinition", back_populates="members")
    agent: Mapped[AgentProfile] = relationship("AgentProfile", back_populates="team_memberships")
