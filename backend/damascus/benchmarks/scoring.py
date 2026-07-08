"""
Benchmark Scoring System
==========================
Provides deterministic, semantic, and composite scoring for benchmark runs.

Scoring methods:
  DETERMINISTIC — JSON schema validation, exact match, numeric comparison
  SEMANTIC — LLM-as-a-Judge evaluation with configurable evaluator model
  COMPOSITE — Weighted aggregation of multiple metrics

All scoring is isolated and reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Score Result
# ---------------------------------------------------------------------------


@dataclass
class MetricScore:
    """Score for a single metric within a benchmark."""

    metric_name: str
    score: float  # 0.0 to 1.0
    weight: float = 1.0
    method: str = "deterministic"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoringResult:
    """Complete scoring result for a benchmark run."""

    overall_score: float  # 0.0 to 1.0
    metric_scores: list[MetricScore]
    confidence: float = 1.0  # 1.0 for deterministic, lower for semantic
    method: str = "composite"


# ---------------------------------------------------------------------------
# Deterministic Scorer
# ---------------------------------------------------------------------------


class DeterministicScorer:
    """
    Scores outputs using deterministic methods:
      - exact_match: output == expected
      - contains: expected substring in output
      - regex_match: output matches regex pattern
      - numeric_range: numeric output within [min, max]
      - json_valid: output is valid JSON
      - token_count: output within token count bounds
    """

    def score(
        self,
        output: str,
        expected: Any,
        method: str = "exact_match",
        **kwargs: Any,
    ) -> MetricScore:
        handlers = {
            "exact_match": self._exact_match,
            "contains": self._contains,
            "regex_match": self._regex_match,
            "numeric_range": self._numeric_range,
            "json_valid": self._json_valid,
            "token_count": self._token_count,
        }
        handler = handlers.get(method, self._exact_match)
        return handler(output, expected, **kwargs)

    def _exact_match(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        match = output.strip() == str(expected).strip()
        return MetricScore(
            metric_name="exact_match",
            score=1.0 if match else 0.0,
            method="deterministic",
            details={"match": match},
        )

    def _contains(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        found = str(expected) in output
        return MetricScore(
            metric_name="contains",
            score=1.0 if found else 0.0,
            method="deterministic",
            details={"found": found},
        )

    def _regex_match(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        try:
            match = bool(re.search(str(expected), output))
        except re.error:
            match = False
        return MetricScore(
            metric_name="regex_match",
            score=1.0 if match else 0.0,
            method="deterministic",
            details={"match": match, "pattern": str(expected)},
        )

    def _numeric_range(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        try:
            value = float(output.strip())
            min_val = float(kwargs.get("min", expected.get("min", 0) if isinstance(expected, dict) else 0))
            max_val = float(kwargs.get("max", expected.get("max", 1) if isinstance(expected, dict) else 1))
            in_range = min_val <= value <= max_val
            return MetricScore(
                metric_name="numeric_range",
                score=1.0 if in_range else 0.0,
                method="deterministic",
                details={"value": value, "min": min_val, "max": max_val, "in_range": in_range},
            )
        except (ValueError, TypeError):
            return MetricScore(
                metric_name="numeric_range",
                score=0.0,
                method="deterministic",
                details={"error": "Could not parse numeric value"},
            )

    def _json_valid(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        import json

        try:
            json.loads(output)
            return MetricScore(
                metric_name="json_valid",
                score=1.0,
                method="deterministic",
                details={"valid_json": True},
            )
        except (json.JSONDecodeError, TypeError):
            return MetricScore(
                metric_name="json_valid",
                score=0.0,
                method="deterministic",
                details={"valid_json": False},
            )

    def _token_count(self, output: str, expected: Any, **kwargs: Any) -> MetricScore:
        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(output) // 4
        max_tokens = int(kwargs.get("max_tokens", expected if isinstance(expected, (int, float)) else 1000))
        min_tokens = int(kwargs.get("min_tokens", 0))
        in_range = min_tokens <= estimated_tokens <= max_tokens
        return MetricScore(
            metric_name="token_count",
            score=1.0 if in_range else 0.0,
            method="deterministic",
            details={
                "estimated_tokens": estimated_tokens,
                "min": min_tokens,
                "max": max_tokens,
            },
        )


# ---------------------------------------------------------------------------
# Composite Scorer
# ---------------------------------------------------------------------------


class CompositeScorer:
    """
    Aggregates multiple metric scores into an overall score
    using weighted averaging.
    """

    def score(self, metric_scores: list[MetricScore]) -> ScoringResult:
        if not metric_scores:
            return ScoringResult(
                overall_score=0.0,
                metric_scores=[],
                confidence=0.0,
            )

        total_weight = sum(m.weight for m in metric_scores)
        if total_weight == 0:
            return ScoringResult(
                overall_score=0.0,
                metric_scores=metric_scores,
                confidence=0.0,
            )

        weighted_sum = sum(m.score * m.weight for m in metric_scores)
        overall = weighted_sum / total_weight

        # Confidence: 1.0 for all deterministic, lower if any semantic
        has_semantic = any(m.method == "semantic" for m in metric_scores)
        confidence = 0.85 if has_semantic else 1.0

        return ScoringResult(
            overall_score=round(overall, 4),
            metric_scores=metric_scores,
            confidence=confidence,
            method="composite",
        )


# ---------------------------------------------------------------------------
# Module-level instances
# ---------------------------------------------------------------------------

deterministic_scorer = DeterministicScorer()
composite_scorer = CompositeScorer()
