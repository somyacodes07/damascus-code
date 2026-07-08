"""
Unit Tests — Benchmark System (Milestone 2.4)
===============================================
Tests for scoring system (deterministic and composite).
"""

from __future__ import annotations

from damascus.benchmarks.scoring import (
    CompositeScorer,
    DeterministicScorer,
    MetricScore,
    ScoringResult,
    composite_scorer,
    deterministic_scorer,
)


class TestDeterministicScorer:
    def test_exact_match_pass(self) -> None:
        result = deterministic_scorer.score("hello world", "hello world", "exact_match")
        assert result.score == 1.0

    def test_exact_match_fail(self) -> None:
        result = deterministic_scorer.score("hello", "world", "exact_match")
        assert result.score == 0.0

    def test_exact_match_whitespace_trim(self) -> None:
        result = deterministic_scorer.score("  hello  ", "hello", "exact_match")
        assert result.score == 1.0

    def test_contains_pass(self) -> None:
        result = deterministic_scorer.score("the quick brown fox", "brown", "contains")
        assert result.score == 1.0

    def test_contains_fail(self) -> None:
        result = deterministic_scorer.score("the quick brown fox", "lazy", "contains")
        assert result.score == 0.0

    def test_regex_match(self) -> None:
        result = deterministic_scorer.score("error code: 404", r"\d{3}", "regex_match")
        assert result.score == 1.0

    def test_regex_match_fail(self) -> None:
        result = deterministic_scorer.score("no numbers here", r"\d+", "regex_match")
        assert result.score == 0.0

    def test_regex_invalid_pattern(self) -> None:
        result = deterministic_scorer.score("test", r"[invalid", "regex_match")
        assert result.score == 0.0

    def test_json_valid(self) -> None:
        result = deterministic_scorer.score('{"key": "value"}', None, "json_valid")
        assert result.score == 1.0

    def test_json_invalid(self) -> None:
        result = deterministic_scorer.score("not json {", None, "json_valid")
        assert result.score == 0.0

    def test_numeric_range_in_range(self) -> None:
        result = deterministic_scorer.score("42", {"min": 0, "max": 100}, "numeric_range")
        assert result.score == 1.0

    def test_numeric_range_out_of_range(self) -> None:
        result = deterministic_scorer.score("200", {"min": 0, "max": 100}, "numeric_range")
        assert result.score == 0.0

    def test_numeric_range_non_numeric(self) -> None:
        result = deterministic_scorer.score("not a number", {"min": 0, "max": 100}, "numeric_range")
        assert result.score == 0.0

    def test_token_count_in_range(self) -> None:
        # ~25 tokens (100 chars / 4)
        text = "a" * 100
        result = deterministic_scorer.score(text, 50, "token_count", min_tokens=10, max_tokens=50)
        assert result.score == 1.0

    def test_token_count_too_long(self) -> None:
        text = "a" * 10000  # ~2500 tokens
        result = deterministic_scorer.score(text, 100, "token_count", max_tokens=100)
        assert result.score == 0.0


class TestCompositeScorer:
    def test_empty_scores(self) -> None:
        result = composite_scorer.score([])
        assert result.overall_score == 0.0
        assert result.confidence == 0.0

    def test_single_score(self) -> None:
        scores = [MetricScore(metric_name="accuracy", score=0.8, weight=1.0)]
        result = composite_scorer.score(scores)
        assert result.overall_score == 0.8

    def test_weighted_average(self) -> None:
        scores = [
            MetricScore(metric_name="accuracy", score=1.0, weight=2.0),
            MetricScore(metric_name="speed", score=0.0, weight=1.0),
        ]
        result = composite_scorer.score(scores)
        # (1.0*2 + 0.0*1) / 3 = 0.6667
        assert abs(result.overall_score - 0.6667) < 0.001

    def test_equal_weights(self) -> None:
        scores = [
            MetricScore(metric_name="a", score=0.5, weight=1.0),
            MetricScore(metric_name="b", score=0.5, weight=1.0),
        ]
        result = composite_scorer.score(scores)
        assert result.overall_score == 0.5

    def test_all_perfect(self) -> None:
        scores = [
            MetricScore(metric_name="a", score=1.0, weight=1.0),
            MetricScore(metric_name="b", score=1.0, weight=1.0),
            MetricScore(metric_name="c", score=1.0, weight=1.0),
        ]
        result = composite_scorer.score(scores)
        assert result.overall_score == 1.0

    def test_confidence_deterministic(self) -> None:
        scores = [
            MetricScore(metric_name="a", score=0.9, weight=1.0, method="deterministic"),
        ]
        result = composite_scorer.score(scores)
        assert result.confidence == 1.0

    def test_confidence_semantic(self) -> None:
        scores = [
            MetricScore(metric_name="a", score=0.9, weight=1.0, method="semantic"),
        ]
        result = composite_scorer.score(scores)
        assert result.confidence == 0.85
