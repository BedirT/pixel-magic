"""Metrics — aggregation, confidence intervals, and variant comparison."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from pixel_magic.evaluation.judge import DIMENSIONS, JudgeResult


@dataclass
class DimensionStats:
    """Statistics for a single scoring dimension."""

    dimension: str
    mean: float
    std: float
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    n: int
    pass_rate: float  # fraction of runs with score >= 0.7

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "ci_95": [round(self.ci_lower, 4), round(self.ci_upper, 4)],
            "n": self.n,
            "pass_rate": round(self.pass_rate, 4),
        }


@dataclass
class AggregateScores:
    """Aggregated evaluation scores across multiple runs."""

    variant_label: str
    dimensions: dict[str, DimensionStats] = field(default_factory=dict)
    total_runs: int = 0
    error_count: int = 0

    @property
    def overall_mean(self) -> float:
        s = self.dimensions.get("overall")
        return s.mean if s else 0.0

    @property
    def overall_pass_rate(self) -> float:
        s = self.dimensions.get("overall")
        return s.pass_rate if s else 0.0

    def to_dict(self) -> dict:
        return {
            "variant": self.variant_label,
            "total_runs": self.total_runs,
            "error_count": self.error_count,
            "overall_mean": round(self.overall_mean, 4),
            "overall_pass_rate": round(self.overall_pass_rate, 4),
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
        }


@dataclass
class ComparisonResult:
    """Statistical comparison between two variants."""

    variant_a: str
    variant_b: str
    dimension: str
    mean_a: float
    mean_b: float
    delta: float  # mean_b - mean_a
    effect_size: float  # Cohen's d
    winner: str  # "a", "b", or "tie"
    significant: bool  # True if CIs don't overlap (rough test)

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
            "mean_a": round(self.mean_a, 4),
            "mean_b": round(self.mean_b, 4),
            "delta": round(self.delta, 4),
            "effect_size": round(self.effect_size, 4),
            "winner": self.winner,
            "significant": self.significant,
        }


def _compute_stats(
    values: list[float],
    dimension: str,
    threshold: float = 0.7,
) -> DimensionStats:
    """Compute descriptive statistics with 95% CI for a list of scores."""
    n = len(values)
    if n == 0:
        return DimensionStats(dimension, 0.0, 0.0, 0.0, 0.0, 0, 0.0)

    mean = statistics.mean(values)
    std = statistics.stdev(values) if n > 1 else 0.0

    # 95% CI using t-distribution approximation (z=1.96 for large n)
    z = 1.96
    se = std / math.sqrt(n) if n > 0 else 0.0
    ci_lower = max(0.0, mean - z * se)
    ci_upper = min(1.0, mean + z * se)

    pass_rate = sum(1 for v in values if v >= threshold) / n

    return DimensionStats(
        dimension=dimension,
        mean=mean,
        std=std,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        n=n,
        pass_rate=pass_rate,
    )


def aggregate_results(
    results: list[JudgeResult],
    variant_label: str = "default",
) -> AggregateScores:
    """Aggregate multiple JudgeResults into statistical summaries per dimension."""
    valid = [r for r in results if r.error is None]
    errors = [r for r in results if r.error is not None]

    agg = AggregateScores(
        variant_label=variant_label,
        total_runs=len(results),
        error_count=len(errors),
    )

    for dim in DIMENSIONS:
        values = [r.scores.get(dim, 0.0) for r in valid]
        agg.dimensions[dim] = _compute_stats(values, dim)

    return agg


def compare_variants(
    agg_a: AggregateScores,
    agg_b: AggregateScores,
) -> list[ComparisonResult]:
    """Compare two aggregated variants across all dimensions.

    Uses Cohen's d for effect size and non-overlapping CIs as a rough
    significance test.
    """
    comparisons = []

    for dim in DIMENSIONS:
        stats_a = agg_a.dimensions.get(dim)
        stats_b = agg_b.dimensions.get(dim)

        if stats_a is None or stats_b is None:
            continue

        delta = stats_b.mean - stats_a.mean

        # Cohen's d: (M2 - M1) / pooled_std
        pooled_var = (
            (stats_a.std**2 * max(stats_a.n - 1, 0) + stats_b.std**2 * max(stats_b.n - 1, 0))
            / max(stats_a.n + stats_b.n - 2, 1)
        )
        pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1e-9
        effect_size = delta / pooled_std

        # Significance: CIs don't overlap
        significant = stats_a.ci_upper < stats_b.ci_lower or stats_b.ci_upper < stats_a.ci_lower

        # Winner determination (need meaningful delta + significance)
        if abs(effect_size) < 0.2:
            winner = "tie"
        elif delta > 0:
            winner = agg_b.variant_label
        else:
            winner = agg_a.variant_label

        comparisons.append(ComparisonResult(
            variant_a=agg_a.variant_label,
            variant_b=agg_b.variant_label,
            dimension=dim,
            mean_a=stats_a.mean,
            mean_b=stats_b.mean,
            delta=delta,
            effect_size=effect_size,
            winner=winner,
            significant=significant,
        ))

    return comparisons
