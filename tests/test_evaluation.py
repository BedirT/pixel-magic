"""Tests for the evaluation framework — judge, metrics, cases, runner, report."""

from __future__ import annotations

import json
import math
import statistics

import pytest

from pixel_magic.evaluation.cases import EvalCase, get_standard_cases
from pixel_magic.evaluation.judge import DIMENSIONS, JudgeResult, PixelArtJudge
from pixel_magic.evaluation.metrics import (
    AggregateScores,
    ComparisonResult,
    aggregate_results,
    compare_variants,
)
from pixel_magic.evaluation.report import generate_report
from pixel_magic.evaluation.runner import EvalRun, EvalRunRecord


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_judge_result(
    overall: float = 0.8,
    error: str | None = None,
    **overrides,
) -> JudgeResult:
    """Create a synthetic JudgeResult for testing."""
    if error:
        return JudgeResult(error=error)
    scores = {dim: overall for dim in DIMENSIONS}
    scores.update(overrides)
    return JudgeResult(scores=scores, feedback="test feedback")


def _make_eval_run(
    label: str,
    count: int = 5,
    base_score: float = 0.75,
    spread: float = 0.05,
) -> EvalRun:
    """Create a synthetic EvalRun with scattered scores."""
    run = EvalRun(variant_label=label, model_name="test-model")
    for i in range(count):
        score = base_score + spread * (i - count // 2)
        score = max(0.0, min(1.0, score))
        record = EvalRunRecord(
            case_name=f"case_{i}",
            template_name="character_directions_4dir",
            variant_label=label,
            model_used="test-model",
            prompt_rendered="test prompt",
            judge=_make_judge_result(overall=score),
            generation_time_s=1.5,
        )
        run.records.append(record)
    return run


# ── JudgeResult tests ────────────────────────────────────────────────


class TestJudgeResult:
    def test_overall_score(self):
        r = _make_judge_result(overall=0.85)
        assert r.overall == 0.85

    def test_passed_above_threshold(self):
        assert _make_judge_result(overall=0.75).passed is True

    def test_failed_below_threshold(self):
        assert _make_judge_result(overall=0.65).passed is False

    def test_error_result(self):
        r = _make_judge_result(error="API failed")
        assert r.error == "API failed"
        assert r.overall == 0.0
        assert r.passed is False

    def test_to_dict(self):
        r = _make_judge_result(overall=0.8)
        d = r.to_dict()
        assert d["overall"] == 0.8
        assert d["passed"] is True
        assert "scores" in d
        assert "feedback" in d


# ── Metrics tests ─────────────────────────────────────────────────────


class TestAggregateResults:
    def test_basic_aggregation(self):
        results = [_make_judge_result(overall=s) for s in [0.6, 0.7, 0.8, 0.9]]
        agg = aggregate_results(results, "test")
        assert agg.variant_label == "test"
        assert agg.total_runs == 4
        assert agg.error_count == 0
        assert 0.7 < agg.overall_mean < 0.8  # mean of 0.6-0.9

    def test_handles_errors(self):
        results = [
            _make_judge_result(overall=0.8),
            _make_judge_result(error="fail"),
            _make_judge_result(overall=0.7),
        ]
        agg = aggregate_results(results, "mixed")
        assert agg.total_runs == 3
        assert agg.error_count == 1
        # Only 2 valid results averaged
        stats = agg.dimensions["overall"]
        assert stats.n == 2

    def test_pass_rate(self):
        results = [_make_judge_result(overall=s) for s in [0.6, 0.7, 0.8, 0.9]]
        agg = aggregate_results(results)
        stats = agg.dimensions["overall"]
        assert stats.pass_rate == 0.75  # 3 out of 4 >= 0.7

    def test_confidence_intervals(self):
        results = [_make_judge_result(overall=0.8) for _ in range(10)]
        agg = aggregate_results(results)
        stats = agg.dimensions["overall"]
        # With identical scores, CI should be tight
        assert stats.ci_lower == stats.ci_upper == stats.mean

    def test_single_result(self):
        agg = aggregate_results([_make_judge_result(overall=0.85)], "single")
        assert agg.overall_mean == 0.85
        assert agg.dimensions["overall"].n == 1

    def test_to_dict(self):
        results = [_make_judge_result(overall=0.8)]
        agg = aggregate_results(results, "v1")
        d = agg.to_dict()
        assert d["variant"] == "v1"
        assert "dimensions" in d
        assert "overall" in d["dimensions"]


class TestCompareVariants:
    def test_clear_winner(self):
        results_a = [_make_judge_result(overall=0.5) for _ in range(10)]
        results_b = [_make_judge_result(overall=0.9) for _ in range(10)]
        agg_a = aggregate_results(results_a, "low")
        agg_b = aggregate_results(results_b, "high")
        comparisons = compare_variants(agg_a, agg_b)

        overall_cmp = next(c for c in comparisons if c.dimension == "overall")
        assert overall_cmp.winner == "high"
        assert overall_cmp.delta > 0
        assert overall_cmp.effect_size > 0.8  # large effect

    def test_tie(self):
        # Large variance + tiny mean difference → Cohen's d < 0.2 → tie
        scores_a = [0.55, 0.65, 0.75, 0.85, 0.95, 0.60, 0.70, 0.80, 0.90, 0.50]
        scores_b = [0.56, 0.66, 0.76, 0.86, 0.96, 0.61, 0.71, 0.81, 0.91, 0.51]
        results_a = [_make_judge_result(overall=s) for s in scores_a]
        results_b = [_make_judge_result(overall=s) for s in scores_b]
        agg_a = aggregate_results(results_a, "a")
        agg_b = aggregate_results(results_b, "b")
        comparisons = compare_variants(agg_a, agg_b)

        overall_cmp = next(c for c in comparisons if c.dimension == "overall")
        assert overall_cmp.winner == "tie"

    def test_all_dimensions_compared(self):
        results_a = [_make_judge_result(overall=0.7) for _ in range(5)]
        results_b = [_make_judge_result(overall=0.8) for _ in range(5)]
        agg_a = aggregate_results(results_a, "a")
        agg_b = aggregate_results(results_b, "b")
        comparisons = compare_variants(agg_a, agg_b)
        dims_compared = {c.dimension for c in comparisons}
        assert dims_compared == set(DIMENSIONS)


# ── Test cases ────────────────────────────────────────────────────────


class TestEvalCases:
    def test_standard_cases_not_empty(self):
        cases = get_standard_cases()
        assert len(cases) >= 10

    def test_cases_have_required_fields(self):
        for case in get_standard_cases():
            assert case.name
            assert case.template_name
            assert case.asset_type
            assert case.expected_count >= 1

    def test_all_template_names_exist(self):
        from pixel_magic.generation.prompts import PromptBuilder

        builder = PromptBuilder()
        available = set(builder.list_names())
        for case in get_standard_cases():
            assert case.template_name in available, f"Case '{case.name}' uses unknown template '{case.template_name}'"

    def test_case_to_dict(self):
        case = EvalCase(
            name="test", template_name="t", asset_type="items",
            params={"a": "1"}, expected_count=3,
        )
        d = case.to_dict()
        assert d["name"] == "test"
        assert d["expected_count"] == 3


# ── EvalRun persistence ──────────────────────────────────────────────


class TestEvalRunPersistence:
    def test_save_and_load(self, tmp_path):
        run = _make_eval_run("v1", count=3)
        path = tmp_path / "results.json"
        run.save(path)
        assert path.exists()

        loaded = EvalRun.load(path)
        assert loaded.variant_label == "v1"
        assert len(loaded.records) == 3
        assert loaded.records[0].judge.overall == run.records[0].judge.overall


# ── Report generation ─────────────────────────────────────────────────


class TestReport:
    def test_single_run_report(self):
        run = _make_eval_run("baseline", count=5, base_score=0.8)
        md = generate_report([run])
        assert "# Pixel Magic" in md
        assert "baseline" in md
        assert "Overall Mean" in md or "Overall" in md

    def test_comparison_report(self, tmp_path):
        run_a = _make_eval_run("prompt_v1", count=5, base_score=0.7)
        run_b = _make_eval_run("prompt_v2", count=5, base_score=0.85)
        md = generate_report([run_a, run_b], output_dir=tmp_path)

        assert "prompt_v1 vs prompt_v2" in md
        assert "Effect Size" in md
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.json").exists()

        # Verify JSON structure
        data = json.loads((tmp_path / "report.json").read_text())
        assert len(data["aggregates"]) == 2
        assert "comparisons" in data

    def test_methodology_notes(self):
        run = _make_eval_run("test", count=3)
        md = generate_report([run])
        assert "Cohen's d" in md
        assert "95% CI" in md
