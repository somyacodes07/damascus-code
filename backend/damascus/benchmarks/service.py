"""
Benchmark Service — Business Logic
=====================================
CRUD operations and benchmark execution orchestration.

Benchmark flow:
  1. Create benchmark definition (what to measure)
  2. Run benchmark against a target (workflow/agent/model)
  3. Scoring engine evaluates outputs
  4. Results stored as BenchmarkRun
  5. Compare two runs (baseline vs candidate) for evolution
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from damascus.benchmarks.models import (
    BenchmarkDefinition,
    BenchmarkRun,
    BenchmarkRunStatus,
    BenchmarkStatus,
)
from damascus.benchmarks.scoring import (
    CompositeScorer,
    DeterministicScorer,
    MetricScore,
    ScoringResult,
    composite_scorer,
    deterministic_scorer,
)
from damascus.shared.errors import BenchmarkNotFoundError

log = structlog.get_logger(__name__)


class BenchmarkService:
    """Manages benchmark definitions and runs."""

    # ------------------------------------------------------------------
    # Definition CRUD
    # ------------------------------------------------------------------

    async def create_definition(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        target_types: list[str] | None = None,
        metrics: list[dict[str, Any]] | None = None,
        dataset_reference: str = "",
        scoring_rules: dict[str, Any] | None = None,
        scoring_method: str = "DETERMINISTIC",
    ) -> BenchmarkDefinition:
        definition = BenchmarkDefinition(
            workspace_id=workspace_id,
            name=name,
            description=description,
            target_types=target_types or ["WORKFLOW"],
            metrics=metrics or [],
            dataset_reference=dataset_reference,
            scoring_rules=scoring_rules or {},
            scoring_method=scoring_method,
        )
        session.add(definition)
        await session.flush()
        log.info("Created benchmark definition", benchmark_id=definition.id, name=name)
        return definition

    async def get_definition(
        self, session: AsyncSession, benchmark_id: str
    ) -> BenchmarkDefinition:
        result = await session.execute(
            select(BenchmarkDefinition)
            .where(BenchmarkDefinition.id == benchmark_id)
            .options(selectinload(BenchmarkDefinition.runs))
        )
        defn = result.scalar_one_or_none()
        if defn is None or defn.status == BenchmarkStatus.ARCHIVED:
            raise BenchmarkNotFoundError(benchmark_id=benchmark_id)
        return defn

    async def list_definitions(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[BenchmarkDefinition], int]:
        from sqlalchemy import func

        base = select(BenchmarkDefinition).where(
            BenchmarkDefinition.workspace_id == workspace_id,
            BenchmarkDefinition.status == BenchmarkStatus.ACTIVE,
        )
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(base.offset((page - 1) * per_page).limit(per_page))
        return list(result.all()), total

    # ------------------------------------------------------------------
    # Run Management
    # ------------------------------------------------------------------

    async def create_run(
        self,
        session: AsyncSession,
        *,
        benchmark_id: str,
        target_id: str,
        target_type: str,
        target_version: int = 1,
        experiment_id: str | None = None,
    ) -> BenchmarkRun:
        """Create a new benchmark run record (PENDING state)."""
        # Verify benchmark exists
        await self.get_definition(session, benchmark_id)

        run = BenchmarkRun(
            benchmark_id=benchmark_id,
            target_id=target_id,
            target_type=target_type,
            target_version=target_version,
            experiment_id=experiment_id,
        )
        session.add(run)
        await session.flush()
        log.info(
            "Created benchmark run",
            run_id=run.id,
            benchmark_id=benchmark_id,
            target_id=target_id,
        )
        return run

    async def start_run(self, session: AsyncSession, run_id: str) -> BenchmarkRun:
        """Mark a run as RUNNING."""
        run = await session.get(BenchmarkRun, run_id)
        if run is None:
            raise BenchmarkNotFoundError(benchmark_id=run_id)
        run.status = BenchmarkRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await session.flush()
        return run

    async def complete_run(
        self,
        session: AsyncSession,
        run_id: str,
        *,
        metrics: dict[str, Any],
        overall_score: float,
    ) -> BenchmarkRun:
        """Mark a run as COMPLETED with results."""
        run = await session.get(BenchmarkRun, run_id)
        if run is None:
            raise BenchmarkNotFoundError(benchmark_id=run_id)
        run.status = BenchmarkRunStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        run.metrics = metrics
        run.overall_score = overall_score
        if run.started_at:
            run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
        await session.flush()
        log.info("Benchmark run completed", run_id=run_id, score=overall_score)
        return run

    async def fail_run(
        self, session: AsyncSession, run_id: str, error_message: str
    ) -> BenchmarkRun:
        """Mark a run as FAILED."""
        run = await session.get(BenchmarkRun, run_id)
        if run is None:
            raise BenchmarkNotFoundError(benchmark_id=run_id)
        run.status = BenchmarkRunStatus.FAILED
        run.completed_at = datetime.now(UTC)
        run.error_message = error_message
        if run.started_at:
            run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
        await session.flush()
        log.error("Benchmark run failed", run_id=run_id, error=error_message)
        return run

    async def get_run(self, session: AsyncSession, run_id: str) -> BenchmarkRun:
        run = await session.get(BenchmarkRun, run_id)
        if run is None:
            raise BenchmarkNotFoundError(benchmark_id=run_id)
        return run

    async def list_runs(
        self,
        session: AsyncSession,
        benchmark_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[BenchmarkRun], int]:
        from sqlalchemy import func

        base = select(BenchmarkRun).where(BenchmarkRun.benchmark_id == benchmark_id)
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(
            base.order_by(BenchmarkRun.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.all()), total

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    async def compare_runs(
        self,
        session: AsyncSession,
        baseline_run_id: str,
        candidate_run_id: str,
    ) -> dict[str, Any]:
        """
        Compare two benchmark runs and produce a structured diff.
        Returns improvement/regression analysis for each metric.
        """
        baseline = await self.get_run(session, baseline_run_id)
        candidate = await self.get_run(session, candidate_run_id)

        comparison: dict[str, Any] = {
            "baseline": {
                "run_id": baseline.id,
                "overall_score": baseline.overall_score,
                "metrics": baseline.metrics,
                "duration_ms": baseline.duration_ms,
            },
            "candidate": {
                "run_id": candidate.id,
                "overall_score": candidate.overall_score,
                "metrics": candidate.metrics,
                "duration_ms": candidate.duration_ms,
            },
            "score_delta": round(candidate.overall_score - baseline.overall_score, 4),
            "is_improvement": candidate.overall_score > baseline.overall_score,
            "is_regression": candidate.overall_score < baseline.overall_score,
            "metric_deltas": {},
        }

        # Per-metric comparison
        all_metrics = set(list(baseline.metrics.keys()) + list(candidate.metrics.keys()))
        for metric in all_metrics:
            b_val = baseline.metrics.get(metric, 0.0)
            c_val = candidate.metrics.get(metric, 0.0)
            if isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
                comparison["metric_deltas"][metric] = {
                    "baseline": b_val,
                    "candidate": c_val,
                    "delta": round(c_val - b_val, 4),
                    "improved": c_val > b_val,
                }

        return comparison

    # ------------------------------------------------------------------
    # Scoring Helper
    # ------------------------------------------------------------------

    def score_output(
        self,
        output: str,
        expected: Any,
        method: str = "exact_match",
        **kwargs: Any,
    ) -> MetricScore:
        """Score a single output against expected using deterministic scoring."""
        return deterministic_scorer.score(output, expected, method, **kwargs)

    def aggregate_scores(self, scores: list[MetricScore]) -> ScoringResult:
        """Aggregate multiple metric scores into an overall result."""
        return composite_scorer.score(scores)


# Module-level singleton
benchmark_service = BenchmarkService()
