"""
Rollback Engine — Reverts Promoted Variants
=============================================
When a promoted variant causes regression or failure in production,
the rollback engine restores the prior stable version.

Rollback is always available and never requires approval — safety first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.evolution.models import (
    Experiment,
    ExperimentStatus,
    PromotionRecord,
    PromotionStatus,
    RollbackRecord,
)
from damascus.shared.errors import PromotionNotFoundError, RollbackFailedError

log = structlog.get_logger(__name__)


class RollbackEngine:
    """
    Reverts promoted variants by restoring the prior stable version.
    Rollback is instant and does not require approval.
    """

    async def rollback(
        self,
        session: AsyncSession,
        promotion_id: str,
        *,
        cause: str,
        evidence: dict[str, Any] | None = None,
    ) -> RollbackRecord:
        """
        Roll back a promotion and restore the baseline version.

        This operation:
          1. Creates a RollbackRecord with evidence
          2. Marks the PromotionRecord as ROLLED_BACK
          3. Marks the Experiment as ROLLED_BACK
          4. Returns the rollback record with the version to restore

        The actual version swap (updating the workflow registry) is
        handled by the caller (EvolutionService) using the returned
        restored_version_id.
        """
        promotion = await session.get(PromotionRecord, promotion_id)
        if promotion is None:
            raise PromotionNotFoundError(promotion_id=promotion_id)

        if promotion.status in (PromotionStatus.ROLLED_BACK, PromotionStatus.PROPOSED):
            raise RollbackFailedError(
                message=f"Cannot rollback promotion in state {promotion.status}"
            )

        # Create rollback record
        record = RollbackRecord(
            promotion_id=promotion_id,
            cause=cause,
            evidence=evidence or {},
            restored_version_id=promotion.baseline_id,
        )
        session.add(record)

        # Update promotion status
        promotion.status = PromotionStatus.ROLLED_BACK

        # Update experiment status
        experiment = await session.get(Experiment, promotion.experiment_id)
        if experiment:
            experiment.status = ExperimentStatus.ROLLED_BACK

        await session.flush()

        log.warning(
            "Promotion rolled back",
            promotion_id=promotion_id,
            cause=cause,
            restored_version_id=promotion.baseline_id,
        )

        return record


# Module-level singleton
rollback_engine = RollbackEngine()
