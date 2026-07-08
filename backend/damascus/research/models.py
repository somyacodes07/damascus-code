"""
Research — ORM Models
=======================
Defines the ResearchTask, ResearchFinding, and ResearchSource
database models.

The Research Layer provides structured web search, document analysis,
and knowledge synthesis capabilities that agents can use during workflows.
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


class ResearchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FindingType(str, Enum):
    FACT = "FACT"
    OPINION = "OPINION"
    CODE_EXAMPLE = "CODE_EXAMPLE"
    DOCUMENTATION = "DOCUMENTATION"
    BENCHMARK_RESULT = "BENCHMARK_RESULT"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Research Task
# ---------------------------------------------------------------------------


class ResearchTask(Base):
    """
    A structured research request with a query, scope, and output format.
    Research tasks are created by agents during workflow execution.
    """

    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"rt_{uuid.uuid4().hex[:12]}",
    )
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(64), default="web")
    max_sources: Mapped[int] = mapped_column(Integer, default=10)
    output_format: Mapped[str] = mapped_column(String(64), default="summary")
    status: Mapped[str] = mapped_column(String(32), default=ResearchStatus.PENDING)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list[ResearchFinding]] = relationship(
        "ResearchFinding", back_populates="task", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Research Finding
# ---------------------------------------------------------------------------


class ResearchFinding(Base):
    """
    A single finding discovered during research.
    Each finding has a type, content, relevance score, and source.
    """

    __tablename__ = "research_findings"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"rf_{uuid.uuid4().hex[:12]}",
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_type: Mapped[str] = mapped_column(String(32), default=FindingType.FACT)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    source_title: Mapped[str] = mapped_column(String(512), default="")
    finding_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    task: Mapped[ResearchTask] = relationship("ResearchTask", back_populates="findings")
