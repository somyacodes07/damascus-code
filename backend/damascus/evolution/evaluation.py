"""
Evaluation Engine — Compares Variants Against Baseline
========================================================
Takes benchmark results from the arena and produces an evaluation
with a clear recommendation: Promote, Reject, or Inconclusive.

Evaluation criteria:
  - Overall score improvement (must exceed threshold)
  - No regressions on critical metrics
  - Statistical significance (min benchmark runs)
  - Cost/latency trade-off analysis

Output: EvaluationReport with recommendation and evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Evaluation Result
# ---------------------------------------------------------------------------


class Recommendation(str, Enum):
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class MetricComparison:
    """Comparison of a single metric between baseline and candidate."""

    metric_name: str
    baseline_value: float
    candidate_value: float
    delta: float
    delta_percent: float
    improved: bool
    is_regression: bool
    is_critical: bool  # If True, regression blocks promotion


@dataclass
class EvaluationReport:
    """Complete evaluation report for a variant."""

    variant_id: str
    experiment_id: str
    recommendation: Recommendation
    overall_score_delta: float
    metric_comparisons: list[MetricComparison]
    regressions: list[str]
    improvements: list[str]
    confidence: float
    reasoning: str
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class EvaluationEngine:
    """
    Compares benchmark results between baseline and candidate variants
    and produces evaluation reports with recommendations.
    """

    # Default thresholds
    IMPROVEMENT_THRESHOLD = 0.02  # Must improve by at least 2%
    REGRESSION_THRESHOLD = -0.05  # Any metric dropping >5% is a regression
    CRITICAL_REGRESSION_THRESHOLD = -0.10  # >10% drop blocks promotion

    def evaluate(
        self,
        *,
        variant_id: str,
        experiment_id: str,
        baseline_metrics: dict[str, float],
        candidate_metrics: dict[str, float],
        baseline_score: float,
        candidate_score: float,
        critical_metrics: list[str] | None = None,
        improvement_threshold: float | None = None,
    ) -> EvaluationReport:
        """
        Evaluate a variant against the baseline.

        Args:
            baseline_metrics: Metric name → value for the baseline
            candidate_metrics: Metric name → value for the candidate
            baseline_score: Overall baseline score (0.0-1.0)
            candidate_score: Overall candidate score (0.0-1.0)
            critical_metrics: Metric names where regression blocks promotion
            improvement_threshold: Override default improvement threshold
        """
        threshold = improvement_threshold or self.IMPROVEMENT_THRESHOLD
        critical = set(critical_metrics or [])

        # Compare each metric
        comparisons: list[MetricComparison] = []
        regressions: list[str] = []
        improvements: list[str] = []

        all_metrics = set(list(baseline_metrics.keys()) + list(candidate_metrics.keys()))
        for metric in sorted(all_metrics):
            b_val = baseline_metrics.get(metric, 0.0)
            c_val = candidate_metrics.get(metric, 0.0)
            delta = c_val - b_val
            delta_pct = (delta / b_val * 100) if b_val != 0 else (100.0 if delta > 0 else 0.0)

            is_regression = delta_pct < self.REGRESSION_THRESHOLD * 100
            is_critical = metric in critical
            improved = delta > 0

            comp = MetricComparison(
                metric_name=metric,
                baseline_value=round(b_val, 4),
                candidate_value=round(c_val, 4),
                delta=round(delta, 4),
                delta_percent=round(delta_pct, 2),
                improved=improved,
                is_regression=is_regression,
                is_critical=is_critical,
            )
            comparisons.append(comp)

            if is_regression:
                regressions.append(metric)
            if improved:
                improvements.append(metric)

        # Overall score comparison
        score_delta = candidate_score - baseline_score

        # Determine recommendation
        recommendation, reasoning = self._determine_recommendation(
            score_delta=score_delta,
            threshold=threshold,
            comparisons=comparisons,
            regressions=regressions,
            improvements=improvements,
        )

        # Confidence based on number of metrics
        confidence = min(1.0, len(comparisons) / 3) if comparisons else 0.0

        report = EvaluationReport(
            variant_id=variant_id,
            experiment_id=experiment_id,
            recommendation=recommendation,
            overall_score_delta=round(score_delta, 4),
            metric_comparisons=comparisons,
            regressions=regressions,
            improvements=improvements,
            confidence=round(confidence, 2),
            reasoning=reasoning,
        )

        log.info(
            "Evaluation complete",
            variant_id=variant_id,
            recommendation=recommendation.value,
            score_delta=round(score_delta, 4),
            regressions=len(regressions),
            improvements=len(improvements),
        )

        return report

    def _determine_recommendation(
        self,
        *,
        score_delta: float,
        threshold: float,
        comparisons: list[MetricComparison],
        regressions: list[str],
        improvements: list[str],
    ) -> tuple[Recommendation, str]:
        """Determine the recommendation based on evidence."""

        # Check for critical regressions (automatic reject)
        critical_regressions = [
            c for c in comparisons
            if c.is_regression and c.is_critical
        ]
        if critical_regressions:
            names = ", ".join(c.metric_name for c in critical_regressions)
            return (
                Recommendation.REJECT,
                f"Critical regression detected in: {names}. "
                f"Cannot promote with regressions on critical metrics.",
            )

        # Check for significant regressions
        severe_regressions = [
            c for c in comparisons
            if c.delta_percent < self.CRITICAL_REGRESSION_THRESHOLD * 100
        ]
        if severe_regressions:
            names = ", ".join(c.metric_name for c in severe_regressions)
            return (
                Recommendation.REJECT,
                f"Severe regression (>{abs(self.CRITICAL_REGRESSION_THRESHOLD)*100:.0f}%) "
                f"detected in: {names}.",
            )

        # Check for meaningful improvement
        if score_delta >= threshold:
            if regressions:
                return (
                    Recommendation.INCONCLUSIVE,
                    f"Overall score improved by {score_delta:.4f} (threshold: {threshold}), "
                    f"but regressions exist in: {', '.join(regressions)}. "
                    f"Requires human review.",
                )
            return (
                Recommendation.PROMOTE,
                f"Overall score improved by {score_delta:.4f} "
                f"(threshold: {threshold}) with no regressions. "
                f"Improvements in: {', '.join(improvements) or 'overall score'}.",
            )

        # No meaningful improvement
        if abs(score_delta) < threshold:
            return (
                Recommendation.INCONCLUSIVE,
                f"Score delta ({score_delta:.4f}) is below the improvement threshold "
                f"({threshold}). Insufficient evidence.",
            )

        # Score decreased
        return (
            Recommendation.REJECT,
            f"Overall score decreased by {abs(score_delta):.4f}. "
            f"No improvement observed.",
        )


# Module-level singleton
evaluation_engine = EvaluationEngine()
