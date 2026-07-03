"""
Agent — ORM Models
===================
Defines the AgentProfile and AgentPerformance database models.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from damascus.shared.database import Base


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"


def _new_agent_id() -> str:
    return f"ag_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    performance_records: Mapped[list[AgentPerformance]] = relationship(
        "AgentPerformance", back_populates="agent", cascade="all, delete-orphan"
    )


class AgentPerformance(Base):
    """Tracks agent performance metrics over time for evolution analysis."""
    __tablename__ = "agent_performance"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"perf_{uuid.uuid4().hex[:12]}")
    agent_profile_id: Mapped[str] = mapped_column(ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(128), default="")
    success: Mapped[bool] = mapped_column(default=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    agent: Mapped[AgentProfile] = relationship("AgentProfile", back_populates="performance_records")
