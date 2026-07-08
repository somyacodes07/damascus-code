"""
Evolution Service — Full Loop Orchestration
=============================================
Orchestrates the complete evolution lifecycle:

  analyze_opportunities() → plan_experiment() → generate_variants()
  → run_experiment() → evaluate() → propose_promotion()
  → approve/reject() → rollback()

This is the central coordinator. It delegates to:
  - OpportunityAnalyzer (detect weaknesses)
  - VariantGenerator (create candidates)
  - BenchmarkService (run benchmarks)
  - EvaluationEngine (compare results)
  - PromotionEngine (manage approval)
  - RollbackEngine (revert if needed)
  - LineageService (track history)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from damascus.evolution.analyzer import OpportunityCandidate, opportunity_analyzer
from damascus.evolution.evaluation import EvaluationReport, evaluation_engine
from damascus.evolution.generator import variant_generator
from damascus.evolution.lineage import lineage_service
from damascus.evolution.models import (
    Experiment,
    ExperimentStatus,
    EvolutionOpportunity,
    PromotionRecord,
    Variant,
    VariantStatus,
)
from damascus.evolution.promotion import promotion_engine
from damascus.evolution.rollback import rollback_engine
from damascus.shared.errors import ExperimentNotFoundError

log = structlog.get_logger(__name__)


class EvolutionService:
    """
    Central coordinator for the evolution lifecycle.
    All evolution operations flow through this service.
    """

    # ------------------------------------------------------------------
    # 1. Opportunity Discovery
    # ------------------------------------------------------------------

    async def analyze_opportunities(
        self,
        session: AsyncSession,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """
        Analyze the workspace for improvement opportunities.
        Returns ranked list of opportunities with evidence.
        """
        candidates = await opportunity_analyzer.analyze_agent_performance(
            session, workspace_id
        )
        persisted = await opportunity_analyzer.persist_opportunities(
            session, workspace_id, candidates
        )
        return [
            {
                "id": opp.id,
                "target_id": opp.target_id,
                "target_type": opp.target_type,
                "opportunity_type": opp.opportunity_type,
                "description": opp.description,
                "priority_score": opp.priority_score,
                "evidence": opp.evidence,
            }
            for opp in persisted
        ]

    async def list_opportunities(
        self,
        session: AsyncSession,
        workspace_id: str,
        include_addressed: bool = False,
    ) -> list[EvolutionOpportunity]:
        """List evolution opportunities for a workspace."""
        query = select(EvolutionOpportunity).where(
            EvolutionOpportunity.workspace_id == workspace_id
        )
        if not include_addressed:
            query = query.where(EvolutionOpportunity.addressed == False)  # noqa: E712
        query = query.order_by(EvolutionOpportunity.priority_score.desc())
        result = await session.scalars(query)
        return list(result.all())

    # ------------------------------------------------------------------
    # 2. Experiment Planning
    # ------------------------------------------------------------------

    async def create_experiment(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        name: str,
        hypothesis: str,
        target_type: str,
        target_id: str,
        baseline_id: str,
        benchmark_suite_id: str,
        metrics_to_compare: list[str] | None = None,
        resource_budget: dict[str, Any] | None = None,
        safety_constraints: list[str] | None = None,
        opportunity_id: str | None = None,
    ) -> Experiment:
        """Create an experiment to test a hypothesis."""
        experiment = Experiment(
            workspace_id=workspace_id,
            name=name,
            hypothesis=hypothesis,
            target_type=target_type,
            target_id=target_id,
            baseline_id=baseline_id,
            benchmark_suite_id=benchmark_suite_id,
            metrics_to_compare=metrics_to_compare or [],
            resource_budget=resource_budget or {},
            safety_constraints=safety_constraints or [],
        )
        session.add(experiment)
        await session.flush()

        # Mark opportunity as addressed
        if opportunity_id:
            opp = await session.get(EvolutionOpportunity, opportunity_id)
            if opp:
                opp.addressed = True
                opp.experiment_id = experiment.id

        log.info(
            "Experiment created",
            experiment_id=experiment.id,
            name=name,
            target_id=target_id,
        )
        return experiment

    async def get_experiment(
        self, session: AsyncSession, experiment_id: str
    ) -> Experiment:
        result = await session.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id)
            .options(
                selectinload(Experiment.variants),
                selectinload(Experiment.promotions),
            )
        )
        experiment = result.scalar_one_or_none()
        if experiment is None:
            raise ExperimentNotFoundError(experiment_id=experiment_id)
        return experiment

    async def list_experiments(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Experiment], int]:
        from sqlalchemy import func

        base = select(Experiment).where(Experiment.workspace_id == workspace_id)
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(
            base.options(selectinload(Experiment.variants))
            .order_by(Experiment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.all()), total

    # ------------------------------------------------------------------
    # 3. Variant Generation
    # ------------------------------------------------------------------

    async def generate_variants(
        self,
        session: AsyncSession,
        experiment_id: str,
        baseline_config: dict[str, Any],
        available_models: list[str] | None = None,
    ) -> list[Variant]:
        """
        Generate variant candidates for an experiment.
        Uses parameter tuning and model swapping strategies.
        """
        experiment = await self.get_experiment(session, experiment_id)

        # Generate parameter variants
        specs = variant_generator.generate_parameter_variants(
            baseline_config, experiment.baseline_id
        )

        # Generate model variants if models provided
        if available_models:
            model_specs = variant_generator.generate_model_variants(
                baseline_config, available_models, experiment.baseline_id
            )
            specs.extend(model_specs)

        # Persist
        variants = await variant_generator.persist_variants(
            session, experiment_id, experiment.baseline_id, specs
        )

        # Update experiment status
        experiment.status = ExperimentStatus.RUNNING
        await session.flush()

        return variants

    # ------------------------------------------------------------------
    # 4. Evaluation
    # ------------------------------------------------------------------

    def evaluate_variant(
        self,
        *,
        variant_id: str,
        experiment_id: str,
        baseline_metrics: dict[str, float],
        candidate_metrics: dict[str, float],
        baseline_score: float,
        candidate_score: float,
        critical_metrics: list[str] | None = None,
    ) -> EvaluationReport:
        """Evaluate a variant against the baseline using benchmark results."""
        return evaluation_engine.evaluate(
            variant_id=variant_id,
            experiment_id=experiment_id,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            critical_metrics=critical_metrics,
        )

    # ------------------------------------------------------------------
    # 5. Promotion
    # ------------------------------------------------------------------

    async def propose_promotion(
        self,
        session: AsyncSession,
        experiment_id: str,
        variant_id: str,
        evaluation_report: EvaluationReport,
    ) -> PromotionRecord:
        """Propose promoting a variant based on evaluation results."""
        experiment = await self.get_experiment(session, experiment_id)

        return await promotion_engine.propose_promotion(
            session,
            experiment_id=experiment_id,
            variant_id=variant_id,
            baseline_id=experiment.baseline_id,
            evidence={
                "score_delta": evaluation_report.overall_score_delta,
                "improvements": evaluation_report.improvements,
                "confidence": evaluation_report.confidence,
                "reasoning": evaluation_report.reasoning,
            },
            expected_benefits={
                "score_improvement": evaluation_report.overall_score_delta,
                "improved_metrics": evaluation_report.improvements,
            },
            regressions=evaluation_report.regressions,
        )

    async def approve_promotion(
        self,
        session: AsyncSession,
        promotion_id: str,
        approver_id: str,
    ) -> PromotionRecord:
        """Approve a pending promotion."""
        return await promotion_engine.approve_promotion(
            session, promotion_id, approver_id
        )

    async def reject_promotion(
        self,
        session: AsyncSession,
        promotion_id: str,
        rejector_id: str,
        reason: str = "",
    ) -> PromotionRecord:
        """Reject a pending promotion."""
        return await promotion_engine.reject_promotion(
            session, promotion_id, rejector_id, reason
        )

    # ------------------------------------------------------------------
    # 6. Rollback
    # ------------------------------------------------------------------

    async def rollback_promotion(
        self,
        session: AsyncSession,
        promotion_id: str,
        cause: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Roll back a promoted variant to the prior stable version.
        Returns the rollback record and the version to restore.
        """
        record = await rollback_engine.rollback(
            session, promotion_id, cause=cause, evidence=evidence
        )
        return {
            "rollback_id": record.id,
            "promotion_id": promotion_id,
            "restored_version_id": record.restored_version_id,
            "cause": cause,
        }

    # ------------------------------------------------------------------
    # 7. Lineage
    # ------------------------------------------------------------------

    async def get_lineage(
        self,
        session: AsyncSession,
        target_id: str,
    ) -> list[dict[str, Any]]:
        """Get the evolution history for a target."""
        return await lineage_service.get_lineage(session, target_id)


# Module-level singleton
evolution_service = EvolutionService()
