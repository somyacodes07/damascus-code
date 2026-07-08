"""
Evolution Engine — ORM Models
===============================
Defines the Experiment, Variant, PromotionRecord, and RollbackRecord
database models per the Data-Models doc.

The Evolution Engine is the defining subsystem of Damascus. These models
track the full lifecycle: opportunity → experiment → variant → benchmark →
evaluate → promote/reject → monitor → rollback.
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


class ExperimentStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class VariantStatus(str, Enum):
    CREATED = "CREATED"
    TESTING = "TESTING"
    EVALUATED = "EVALUATED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


class PromotionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    STABLE = "STABLE"
    ROLLED_BACK = "ROLLED_BACK"


class EvolutionTargetType(str, Enum):
    WORKFLOW = "WORKFLOW"
    TEAM = "TEAM"
    TOOL_SELECTION = "TOOL_SELECTION"
    MODEL_ROUTING = "MODEL_ROUTING"


class OpportunityType(str, Enum):
    REPEATED_FAILURE = "REPEATED_FAILURE"
    HIGH_LATENCY = "HIGH_LATENCY"
    EXCESSIVE_COST = "EXCESSIVE_COST"
    LOW_QUALITY = "LOW_QUALITY"
    RECURRING_CORRECTION = "RECURRING_CORRECTION"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------


class EvolutionOpportunity(Base):
    """
    A detected improvement opportunity from workflow trace analysis.
    Opportunities are the inputs to the experiment planning phase.
    """

    __tablename__ = "evolution_opportunities"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"opp_{uuid.uuid4().hex[:12]}",
    )
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    addressed: Mapped[bool] = mapped_column(default=False)
    experiment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------


class Experiment(Base):
    """
    An evolution experiment that tests whether a change improves performance.
    Contains a hypothesis, baseline, variants, and benchmark suite reference.
    """

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"exp_{uuid.uuid4().hex[:12]}",
    )
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(
        String(32), default=EvolutionTargetType.WORKFLOW
    )
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_id: Mapped[str] = mapped_column(String(32), nullable=False)
    benchmark_suite_id: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics_to_compare: Mapped[list] = mapped_column(JSONB, default=list)
    resource_budget: Mapped[dict] = mapped_column(JSONB, default=dict)
    safety_constraints: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default=ExperimentStatus.PLANNED)
    result_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list[Variant]] = relationship(
        "Variant", back_populates="experiment", cascade="all, delete-orphan"
    )
    promotions: Mapped[list[PromotionRecord]] = relationship(
        "PromotionRecord", back_populates="experiment", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Variant
# ---------------------------------------------------------------------------


class Variant(Base):
    """
    A candidate alternative being tested in an experiment.
    Each variant represents a specific mutation from the baseline.
    """

    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"var_{uuid.uuid4().hex[:12]}",
    )
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    baseline_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    change_set: Mapped[dict] = mapped_column(JSONB, default=dict)
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    benchmark_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    benchmark_results: Mapped[dict] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default=VariantStatus.CREATED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="variants")


# ---------------------------------------------------------------------------
# Promotion Record
# ---------------------------------------------------------------------------


class PromotionRecord(Base):
    """
    Records when a variant is promoted to production.
    Tracks evidence, approval, and rollback planning.
    """

    __tablename__ = "promotion_records"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"promo_{uuid.uuid4().hex[:12]}",
    )
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_id: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    expected_benefits: Mapped[dict] = mapped_column(JSONB, default=dict)
    actual_benefits: Mapped[dict] = mapped_column(JSONB, default=dict)
    regressions: Mapped[list] = mapped_column(JSONB, default=list)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollback_plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=PromotionStatus.PROPOSED)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="promotions")

    rollbacks: Mapped[list[RollbackRecord]] = relationship(
        "RollbackRecord", back_populates="promotion", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Rollback Record
# ---------------------------------------------------------------------------


class RollbackRecord(Base):
    """Records when a promotion is rolled back due to regression or failure."""

    __tablename__ = "rollback_records"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True,
        default=lambda: f"rb_{uuid.uuid4().hex[:12]}",
    )
    promotion_id: Mapped[str] = mapped_column(
        ForeignKey("promotion_records.id", ondelete="CASCADE"), nullable=False
    )
    cause: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    restored_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rolled_back_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    promotion: Mapped[PromotionRecord] = relationship(
        "PromotionRecord", back_populates="rollbacks"
    )
