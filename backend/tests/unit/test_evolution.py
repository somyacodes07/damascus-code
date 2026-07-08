"""
Unit Tests — Evolution Engine (Milestone 2.5)
===============================================
Tests for variant generation, evaluation engine, and safety constraints.
"""

from __future__ import annotations

import pytest

from damascus.evolution.evaluation import (
    EvaluationEngine,
    EvaluationReport,
    Recommendation,
    evaluation_engine,
)
from damascus.evolution.generator import (
    IMMUTABLE_FIELDS,
    VariantGenerator,
    validate_safety,
    variant_generator,
)
from damascus.evolution.models import (
    ExperimentStatus,
    EvolutionTargetType,
    OpportunityType,
    PromotionStatus,
    VariantStatus,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestEvolutionEnums:
    def test_experiment_statuses(self) -> None:
        expected = {
            "PLANNED", "RUNNING", "EVALUATING", "COMPLETED",
            "PROMOTED", "REJECTED", "ROLLED_BACK", "CANCELLED",
        }
        assert {s.value for s in ExperimentStatus} == expected

    def test_variant_statuses(self) -> None:
        expected = {"CREATED", "TESTING", "EVALUATED", "PROMOTED", "REJECTED"}
        assert {s.value for s in VariantStatus} == expected

    def test_promotion_statuses(self) -> None:
        expected = {
            "PROPOSED", "APPROVED", "ACTIVE",
            "MONITORING", "STABLE", "ROLLED_BACK",
        }
        assert {s.value for s in PromotionStatus} == expected

    def test_target_types(self) -> None:
        expected = {"WORKFLOW", "TEAM", "TOOL_SELECTION", "MODEL_ROUTING"}
        assert {t.value for t in EvolutionTargetType} == expected

    def test_opportunity_types(self) -> None:
        expected = {
            "REPEATED_FAILURE", "HIGH_LATENCY",
            "EXCESSIVE_COST", "LOW_QUALITY", "RECURRING_CORRECTION",
        }
        assert {o.value for o in OpportunityType} == expected


# ---------------------------------------------------------------------------
# Safety Constraint Tests
# ---------------------------------------------------------------------------


class TestSafetyConstraints:
    def test_safe_change_set(self) -> None:
        """Normal parameter changes should pass safety validation."""
        change_set = {"temperature": 0.5, "model_preference": "gpt-4o"}
        assert validate_safety(change_set) is True

    def test_unsafe_security_policy(self) -> None:
        """Modifying security_policy must be blocked."""
        change_set = {"security_policy": {"allow_all": True}}
        assert validate_safety(change_set) is False

    def test_unsafe_permissions(self) -> None:
        change_set = {"permissions": ["admin"]}
        assert validate_safety(change_set) is False

    def test_unsafe_sandbox_config(self) -> None:
        change_set = {"sandbox_config": {"disabled": True}}
        assert validate_safety(change_set) is False

    def test_unsafe_nested_key(self) -> None:
        change_set = {"config": {"permissions": ["admin"]}}
        assert validate_safety(change_set) is False

    def test_immutable_fields_complete(self) -> None:
        """All expected immutable fields are defined."""
        assert "security_policy" in IMMUTABLE_FIELDS
        assert "permissions" in IMMUTABLE_FIELDS
        assert "sandbox_config" in IMMUTABLE_FIELDS
        assert "approval_requirements" in IMMUTABLE_FIELDS
        assert "audit_config" in IMMUTABLE_FIELDS
        assert "workspace_id" in IMMUTABLE_FIELDS
        assert "id" in IMMUTABLE_FIELDS


# ---------------------------------------------------------------------------
# Variant Generator Tests
# ---------------------------------------------------------------------------


class TestVariantGenerator:
    def test_generate_parameter_variants(self) -> None:
        """Should generate temperature and iteration variants."""
        baseline = {"temperature": 0.7, "max_iterations": 10}
        specs = variant_generator.generate_parameter_variants(baseline, "baseline_1")

        assert len(specs) > 0
        # Should have temperature variants (not including 0.7)
        temp_variants = [s for s in specs if "Temperature" in s.name]
        assert len(temp_variants) >= 4  # 0.1, 0.3, 0.5, 0.9, 1.2 minus 0.7

        # Should have iteration variants (not including 10)
        iter_variants = [s for s in specs if "iterations" in s.name]
        assert len(iter_variants) >= 3  # 5, 15, 20

    def test_no_duplicate_temperature(self) -> None:
        """Should not generate a variant for the current temperature."""
        baseline = {"temperature": 0.5}
        specs = variant_generator.generate_parameter_variants(baseline, "baseline_1")
        temp_values = [s.change_set.get("temperature") for s in specs if "Temperature" in s.name]
        assert 0.5 not in temp_values

    def test_generate_model_variants(self) -> None:
        baseline = {"model_preference": "ollama/llama3.1"}
        models = ["ollama/llama3.1", "openai/gpt-4o", "anthropic/claude-3-opus"]
        specs = variant_generator.generate_model_variants(baseline, models, "baseline_1")

        # Should not include current model
        assert len(specs) == 2
        model_names = [s.change_set["model_preference"] for s in specs]
        assert "ollama/llama3.1" not in model_names
        assert "openai/gpt-4o" in model_names

    def test_generate_prompt_variant(self) -> None:
        baseline = {"system_prompt": "You are a helpful assistant."}
        spec = variant_generator.generate_prompt_variant(
            baseline,
            "You are an expert software engineer. Be concise.",
            "More specific prompt may improve coding quality",
            "baseline_1",
        )
        assert spec.name == "Prompt refinement"
        assert spec.change_set["system_prompt"] == "You are an expert software engineer. Be concise."
        assert len(spec.mutations) == 1
        assert spec.mutations[0].mutation_type == "prompt"

    def test_variant_specs_have_hypotheses(self) -> None:
        """Every generated variant must have a hypothesis."""
        baseline = {"temperature": 0.7, "max_iterations": 10}
        specs = variant_generator.generate_parameter_variants(baseline, "b1")
        for spec in specs:
            assert spec.hypothesis, f"Variant '{spec.name}' has no hypothesis"

    def test_variant_specs_have_change_sets(self) -> None:
        """Every generated variant must have a non-empty change_set."""
        baseline = {"temperature": 0.7, "max_iterations": 10}
        specs = variant_generator.generate_parameter_variants(baseline, "b1")
        for spec in specs:
            assert spec.change_set, f"Variant '{spec.name}' has empty change_set"


# ---------------------------------------------------------------------------
# Evaluation Engine Tests
# ---------------------------------------------------------------------------


class TestEvaluationEngine:
    def test_clear_improvement(self) -> None:
        """Candidate clearly better → PROMOTE."""
        report = evaluation_engine.evaluate(
            variant_id="var_1",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.70, "speed": 0.80},
            candidate_metrics={"accuracy": 0.85, "speed": 0.85},
            baseline_score=0.75,
            candidate_score=0.85,
        )
        assert report.recommendation == Recommendation.PROMOTE
        assert report.overall_score_delta == 0.10
        assert len(report.improvements) == 2
        assert len(report.regressions) == 0

    def test_clear_regression(self) -> None:
        """Candidate clearly worse → REJECT."""
        report = evaluation_engine.evaluate(
            variant_id="var_2",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.80},
            candidate_metrics={"accuracy": 0.60},
            baseline_score=0.80,
            candidate_score=0.60,
        )
        assert report.recommendation == Recommendation.REJECT
        assert report.overall_score_delta == -0.20

    def test_mixed_results_inconclusive(self) -> None:
        """Some metrics improve, others regress → INCONCLUSIVE."""
        report = evaluation_engine.evaluate(
            variant_id="var_3",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.70, "speed": 0.90},
            candidate_metrics={"accuracy": 0.85, "speed": 0.85},
            baseline_score=0.80,
            candidate_score=0.83,
        )
        assert report.recommendation == Recommendation.INCONCLUSIVE
        assert len(report.regressions) >= 1
        assert len(report.improvements) >= 1

    def test_critical_metric_regression_blocks_promotion(self) -> None:
        """Regression on critical metric → REJECT even if overall improves."""
        report = evaluation_engine.evaluate(
            variant_id="var_4",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.80, "safety_score": 0.95},
            candidate_metrics={"accuracy": 0.95, "safety_score": 0.80},
            baseline_score=0.85,
            candidate_score=0.90,
            critical_metrics=["safety_score"],
        )
        assert report.recommendation == Recommendation.REJECT
        assert "safety_score" in report.regressions

    def test_no_change_inconclusive(self) -> None:
        """Same scores → INCONCLUSIVE."""
        report = evaluation_engine.evaluate(
            variant_id="var_5",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.80},
            candidate_metrics={"accuracy": 0.80},
            baseline_score=0.80,
            candidate_score=0.80,
        )
        assert report.recommendation == Recommendation.INCONCLUSIVE

    def test_marginal_improvement_below_threshold(self) -> None:
        """Improvement below threshold → INCONCLUSIVE."""
        report = evaluation_engine.evaluate(
            variant_id="var_6",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.80},
            candidate_metrics={"accuracy": 0.81},
            baseline_score=0.80,
            candidate_score=0.81,
        )
        # 0.01 improvement, default threshold is 0.02
        assert report.recommendation == Recommendation.INCONCLUSIVE

    def test_report_has_reasoning(self) -> None:
        """All reports must include human-readable reasoning."""
        report = evaluation_engine.evaluate(
            variant_id="var_7",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.70},
            candidate_metrics={"accuracy": 0.90},
            baseline_score=0.70,
            candidate_score=0.90,
        )
        assert report.reasoning
        assert len(report.reasoning) > 10

    def test_custom_threshold(self) -> None:
        """Custom improvement threshold should be respected."""
        report = evaluation_engine.evaluate(
            variant_id="var_8",
            experiment_id="exp_1",
            baseline_metrics={"accuracy": 0.80},
            candidate_metrics={"accuracy": 0.81},
            baseline_score=0.80,
            candidate_score=0.81,
            improvement_threshold=0.005,  # Lower threshold
        )
        assert report.recommendation == Recommendation.PROMOTE
