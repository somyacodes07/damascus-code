"""
Promotion Engine — Manages Variant Promotion to Production
============================================================
When the Evaluation Engine recommends PROMOTE, this engine:
  1. Generates a promotion proposal with evidence
  2. Requires human approval (V1 — no auto-promotion)
  3. Activates the variant as the new production version
  4. Records the promotion with rollback plan

Architecture constraint: In V1, ALL promotions require human approval.
Auto-promotion is a Phase 3 feature gated by config.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.config import settings
from damascus.evolution.models import (
    Experiment,
    ExperimentStatus,
    PromotionRecord,
    PromotionStatus,
    Variant,
    VariantStatus,
)
from damascus.shared.errors import PromotionNotFoundError

log = structlog.get_logger(__name__)


class PromotionEngine:
    """
    Manages the promotion lifecycle for successful variants.
    """

    async def propose_promotion(
        self,
        session: AsyncSession,
        *,
        experiment_id: str,
        variant_id: str,
        baseline_id: str,
        evidence: dict[str, Any],
        expected_benefits: dict[str, Any],
        regressions: list[str] | None = None,
    ) -> PromotionRecord:
        """
        Create a promotion proposal for human review.
        Includes evidence, expected benefits, known regressions,
        and an automatic rollback plan.
        """
        rollback_plan = {
            "restore_version_id": baseline_id,
            "monitoring_period_hours": 24,
            "rollback_triggers": [
                "overall_score_drops_below_baseline",
                "error_rate_exceeds_threshold",
                "human_initiated",
            ],
        }

        record = PromotionRecord(
            experiment_id=experiment_id,
            variant_id=variant_id,
            baseline_id=baseline_id,
            evidence=evidence,
            expected_benefits=expected_benefits,
            regressions=regressions or [],
            rollback_plan=rollback_plan,
            status=PromotionStatus.PROPOSED,
        )
        session.add(record)
        await session.flush()

        log.info(
            "Promotion proposed",
            promotion_id=record.id,
            experiment_id=experiment_id,
            variant_id=variant_id,
        )
        return record

    async def approve_promotion(
        self,
        session: AsyncSession,
        promotion_id: str,
        approver_id: str,
    ) -> PromotionRecord:
        """
        Approve a promotion proposal and activate the variant.
        Only humans can approve in V1.
        """
        record = await session.get(PromotionRecord, promotion_id)
        if record is None:
            raise PromotionNotFoundError(promotion_id=promotion_id)

        if record.status != PromotionStatus.PROPOSED:
            from damascus.shared.errors import DamascusError

            raise DamascusError(
                message=f"Promotion {promotion_id} is in state {record.status}, cannot approve."
            )

        record.status = PromotionStatus.APPROVED
        record.approved_by = approver_id
        record.promoted_at = datetime.now(UTC)

        # Mark the variant as promoted
        variant = await session.get(Variant, record.variant_id)
        if variant:
            variant.status = VariantStatus.PROMOTED

        # Update experiment status
        experiment = await session.get(Experiment, record.experiment_id)
        if experiment:
            experiment.status = ExperimentStatus.PROMOTED

        await session.flush()

        log.info(
            "Promotion approved",
            promotion_id=promotion_id,
            approver=approver_id,
            variant_id=record.variant_id,
        )
        return record

    async def reject_promotion(
        self,
        session: AsyncSession,
        promotion_id: str,
        rejector_id: str,
        reason: str = "",
    ) -> PromotionRecord:
        """Reject a promotion proposal."""
        record = await session.get(PromotionRecord, promotion_id)
        if record is None:
            raise PromotionNotFoundError(promotion_id=promotion_id)

        record.status = PromotionStatus.ROLLED_BACK  # Reuse status for rejection
        record.approved_by = rejector_id  # Track who rejected
        record.actual_benefits = {"rejected": True, "reason": reason}

        # Mark variant as rejected
        variant = await session.get(Variant, record.variant_id)
        if variant:
            variant.status = VariantStatus.REJECTED

        # Update experiment
        experiment = await session.get(Experiment, record.experiment_id)
        if experiment:
            experiment.status = ExperimentStatus.REJECTED

        await session.flush()

        log.info(
            "Promotion rejected",
            promotion_id=promotion_id,
            rejector=rejector_id,
            reason=reason,
        )
        return record

    async def get_promotion(
        self, session: AsyncSession, promotion_id: str
    ) -> PromotionRecord:
        record = await session.get(PromotionRecord, promotion_id)
        if record is None:
            raise PromotionNotFoundError(promotion_id=promotion_id)
        return record


# Module-level singleton
promotion_engine = PromotionEngine()
