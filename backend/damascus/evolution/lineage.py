"""
Lineage Service — Evolution History Tracking
===============================================
Tracks the version history of evolving workflows.
Every promotion creates a parent→child link.
Failed experiments are preserved as learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.evolution.models import (
    Experiment,
    ExperimentStatus,
    PromotionRecord,
    Variant,
)

log = structlog.get_logger(__name__)


@dataclass
class LineageNode:
    """A single node in the evolution lineage graph."""

    version_id: str
    experiment_id: str | None
    variant_id: str | None
    status: str
    created_at: str
    parent_version_id: str | None
    children: list[LineageNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "status": self.status,
            "created_at": self.created_at,
            "parent_version_id": self.parent_version_id,
            "children": [c.to_dict() for c in self.children],
        }


class LineageService:
    """
    Tracks and queries the evolution lineage of a workflow target.
    Provides the version history from initial creation through
    all experiments and promotions.
    """

    async def get_lineage(
        self,
        session: AsyncSession,
        target_id: str,
    ) -> list[dict[str, Any]]:
        """
        Build the evolution history for a target.
        Returns a chronological list of experiments and their outcomes.
        """
        result = await session.execute(
            select(Experiment)
            .where(Experiment.target_id == target_id)
            .order_by(Experiment.created_at.asc())
        )
        experiments = list(result.scalars().all())

        lineage: list[dict[str, Any]] = []
        for exp in experiments:
            # Get variants for this experiment
            variants_result = await session.execute(
                select(Variant).where(Variant.experiment_id == exp.id)
            )
            variants = list(variants_result.scalars().all())

            # Get promotions
            promotions_result = await session.execute(
                select(PromotionRecord).where(PromotionRecord.experiment_id == exp.id)
            )
            promotions = list(promotions_result.scalars().all())

            lineage.append({
                "experiment_id": exp.id,
                "name": exp.name,
                "hypothesis": exp.hypothesis,
                "status": exp.status,
                "baseline_id": exp.baseline_id,
                "created_at": exp.created_at.isoformat(),
                "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
                "variants": [
                    {
                        "id": v.id,
                        "name": v.name,
                        "status": v.status,
                        "score": v.score,
                        "hypothesis": v.hypothesis,
                    }
                    for v in variants
                ],
                "promotions": [
                    {
                        "id": p.id,
                        "variant_id": p.variant_id,
                        "status": p.status,
                        "approved_by": p.approved_by,
                        "promoted_at": p.promoted_at.isoformat() if p.promoted_at else None,
                    }
                    for p in promotions
                ],
            })

        return lineage

    async def get_experiment_count(
        self, session: AsyncSession, target_id: str
    ) -> int:
        """Return the number of experiments run for a target."""
        from sqlalchemy import func

        count = await session.scalar(
            select(func.count(Experiment.id)).where(Experiment.target_id == target_id)
        )
        return count or 0

    async def get_promotion_count(
        self, session: AsyncSession, target_id: str
    ) -> int:
        """Return the number of successful promotions for a target."""
        from sqlalchemy import func

        count = await session.scalar(
            select(func.count(PromotionRecord.id))
            .join(Experiment, PromotionRecord.experiment_id == Experiment.id)
            .where(
                Experiment.target_id == target_id,
                Experiment.status == ExperimentStatus.PROMOTED,
            )
        )
        return count or 0


# Module-level singleton
lineage_service = LineageService()
