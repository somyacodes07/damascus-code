"""
Benchmark — ORM Models
========================
Defines the BenchmarkDefinition, BenchmarkRun, and BenchmarkArtifact
database models per the Data-Models doc.

Benchmarks provide objective measurement of workflow, agent, and model
performance. They are the foundation for the Evolution Engine — without
benchmarks, evolution has no evidence.
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


class BenchmarkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class BenchmarkRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BenchmarkTargetType(str, Enum):
    WORKFLOW = "WORKFLOW"
    AGENT = "AGENT"
    TEAM = "TEAM"
    MODEL = "MODEL"


class ScoringMethod(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"
    COMPOSITE = "COMPOSITE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Benchmark Definition
# ---------------------------------------------------------------------------


class BenchmarkDefinition(Base):
    """
    Describes a benchmark that can measure workflow/agent/model performance.
    Benchmark definitions are reusable templates.
    """

    __tablename__ = "benchmark_definitions"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"bm_{uuid.uuid4().hex[:12]}",
    )
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    target_types: Mapped[list] = mapped_column(
        JSONB, default=lambda: [BenchmarkTargetType.WORKFLOW.value]
    )
    metrics: Mapped[list] = mapped_column(JSONB, default=list)
    dataset_reference: Mapped[str] = mapped_column(String(512), default="")
    scoring_rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    scoring_method: Mapped[str] = mapped_column(
        String(32), default=ScoringMethod.DETERMINISTIC
    )
    status: Mapped[str] = mapped_column(String(32), default=BenchmarkStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    runs: Mapped[list[BenchmarkRun]] = relationship(
        "BenchmarkRun", back_populates="benchmark", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Benchmark Run
# ---------------------------------------------------------------------------


class BenchmarkRun(Base):
    """
    A single execution of a benchmark against a target.
    Records measured results and an overall score.
    """

    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"br_{uuid.uuid4().hex[:12]}",
    )
    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, default=1)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default=BenchmarkRunStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    benchmark: Mapped[BenchmarkDefinition] = relationship(
        "BenchmarkDefinition", back_populates="runs"
    )
    artifacts: Mapped[list[BenchmarkArtifact]] = relationship(
        "BenchmarkArtifact", back_populates="run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Benchmark Artifact
# ---------------------------------------------------------------------------


class BenchmarkArtifact(Base):
    """
    An artifact produced during a benchmark run (logs, outputs, traces).
    Stored in MinIO via the Storage Layer.
    """

    __tablename__ = "benchmark_artifacts"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"ba_{uuid.uuid4().hex[:12]}",
    )
    benchmark_run_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    artifact_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped[BenchmarkRun] = relationship("BenchmarkRun", back_populates="artifacts")
