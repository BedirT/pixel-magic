"""Report generation — Markdown and JSON summaries with statistical comparisons."""

from __future__ import annotations

import json
from pathlib import Path

from pixel_magic.evaluation.cost import estimate_run_cost
from pixel_magic.evaluation.judge import DIMENSIONS
from pixel_magic.evaluation.metrics import (
    AggregateScores,
    ComparisonResult,
    aggregate_results,
    compare_variants,
)
from pixel_magic.evaluation.runner import EvalRun


def generate_report(
    runs: list[EvalRun],
    output_dir: Path | None = None,
) -> str:
    """Generate a Markdown evaluation report comparing one or more runs.

    Args:
        runs: List of completed EvalRun objects to compare.
        output_dir: If provided, saves report.md and report.json here.

    Returns:
        The Markdown report as a string.
    """
    aggregates = [aggregate_results(r.results, r.variant_label) for r in runs]
    cost_summaries = [estimate_run_cost(r) for r in runs]

    lines: list[str] = []
    lines.append("# Pixel Magic — Model Comparison Report\n")

    # ── Summary table ─────────────────────────────────────────────────

    lines.append("## Summary\n")
    lines.append(
        "| Variant | Model | Cases | Errors | Overall | Pass Rate "
        "| Mean Latency | Wall Clock | Est. Cost |"
    )
    lines.append(
        "|---------|-------|------:|-------:|--------:|----------:"
        "|-----------:|-----------:|----------:|"
    )

    for run, agg, cost in zip(runs, aggregates, cost_summaries):
        model = run.records[0].model_used if run.records else run.model_name
        lines.append(
            f"| {agg.variant_label} | {model} | {agg.total_runs} | "
            f"{agg.error_count} | {agg.overall_mean:.3f} | "
            f"{agg.overall_pass_rate:.0%} | "
            f"{cost['mean_gen_time_s']:.1f}s | "
            f"{cost['wall_clock_s']:.0f}s | "
            f"${cost['estimated_cost_usd']:.4f} |"
        )

    lines.append("")

    # ── Cost & Latency breakdown ──────────────────────────────────────

    lines.append("## Cost & Latency\n")
    lines.append(
        "| Variant | Total Gen Time | Mean/Case | Input Tokens | Output Tokens | Est. Cost |"
    )
    lines.append(
        "|---------|-------------:|---------:|-------------:|--------------:|----------:|"
    )

    for run, cost in zip(runs, cost_summaries):
        lines.append(
            f"| {run.variant_label} | {cost['total_gen_time_s']:.1f}s | "
            f"{cost['mean_gen_time_s']:.1f}s | "
            f"{cost['total_input_tokens']:,} | "
            f"{cost['total_output_tokens']:,} | "
            f"${cost['estimated_cost_usd']:.4f} |"
        )

    lines.append("")

    # ── Per-dimension breakdown ───────────────────────────────────────

    lines.append("## Dimension Scores\n")

    header = "| Dimension |"
    sep = "|-----------|"
    for agg in aggregates:
        header += f" {agg.variant_label} (μ ± σ) | {agg.variant_label} 95% CI |"
        sep += "---:|---:|"
    lines.append(header)
    lines.append(sep)

    for dim in DIMENSIONS:
        row = f"| {dim} |"
        for agg in aggregates:
            stats = agg.dimensions.get(dim)
            if stats:
                row += f" {stats.mean:.3f} ± {stats.std:.3f} | [{stats.ci_lower:.3f}, {stats.ci_upper:.3f}] |"
            else:
                row += " — | — |"
        lines.append(row)

    lines.append("")

    # ── A/B Comparisons (if >1 variant) ──────────────────────────────

    if len(aggregates) >= 2:
        lines.append("## Variant Comparisons\n")

        for i in range(len(aggregates)):
            for j in range(i + 1, len(aggregates)):
                a, b = aggregates[i], aggregates[j]
                comparisons = compare_variants(a, b)

                lines.append(f"### {a.variant_label} vs {b.variant_label}\n")
                lines.append("| Dimension | Mean A | Mean B | Δ | Effect Size | Winner | Sig? |")
                lines.append("|-----------|-------:|-------:|--:|------------:|--------|------|")

                for c in comparisons:
                    sig = "✓" if c.significant else ""
                    lines.append(
                        f"| {c.dimension} | {c.mean_a:.3f} | {c.mean_b:.3f} | "
                        f"{c.delta:+.3f} | {c.effect_size:+.2f} | {c.winner} | {sig} |"
                    )

                lines.append("")

                # Overall verdict
                overall = next(
                    (c for c in comparisons if c.dimension == "overall"), None
                )
                if overall:
                    if overall.winner == "tie":
                        lines.append(f"**Verdict:** No meaningful difference (d={overall.effect_size:+.2f})\n")
                    elif overall.significant:
                        lines.append(
                            f"**Verdict:** **{overall.winner}** is significantly better "
                            f"(Δ={overall.delta:+.3f}, d={overall.effect_size:+.2f})\n"
                        )
                    else:
                        lines.append(
                            f"**Verdict:** {overall.winner} trends better but not "
                            f"statistically significant (Δ={overall.delta:+.3f}, d={overall.effect_size:+.2f})\n"
                        )

    # ── Per-case detail ───────────────────────────────────────────────

    lines.append("## Per-Case Results\n")

    for run, agg, cost in zip(runs, aggregates, cost_summaries):
        lines.append(f"### {agg.variant_label}\n")
        lines.append("| Case | Template | Overall | Gen Time | Tokens (in/out) | Cost | Feedback |")
        lines.append("|------|----------|--------:|---------:|----------------:|-----:|----------|")

        cost_by_case = {c["case_name"]: c for c in cost["per_case"]}
        for rec in run.records:
            score = f"{rec.judge.overall:.2f}" if not rec.judge.error else "ERR"
            t = f"{rec.generation_time_s:.1f}s" if rec.generation_time_s else "—"
            c = cost_by_case.get(rec.case_name, {})
            tokens = f"{c.get('input_tokens', 0)}/{c.get('output_tokens', 0)}"
            cost_str = f"${c.get('cost_usd', 0):.4f}"
            fb = rec.judge.feedback[:50] + "…" if len(rec.judge.feedback) > 50 else rec.judge.feedback
            lines.append(
                f"| {rec.case_name} | {rec.template_name} | {score} | {t} "
                f"| {tokens} | {cost_str} | {fb} |"
            )

        lines.append("")

    # ── Effect size interpretation guide ──────────────────────────────

    lines.append("## Methodology Notes\n")
    lines.append("- **Scores** are normalized 0–1 (from LLM judge ratings 1–10)")
    lines.append("- **Pass rate** is the fraction of runs scoring ≥ 0.70 on overall")
    lines.append("- **95% CI** uses normal approximation (z=1.96)")
    lines.append("- **Effect size** (Cohen's d): |d| < 0.2 negligible, 0.2–0.5 small, 0.5–0.8 medium, > 0.8 large")
    lines.append("- **Significant** (✓) when 95% CIs do not overlap (conservative)")
    lines.append("")

    report_md = "\n".join(lines)

    # Save if output_dir provided
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.md").write_text(report_md)

        # Also save structured JSON
        report_json = {
            "aggregates": [a.to_dict() for a in aggregates],
            "cost_summaries": [c for c in cost_summaries],
            "runs": [r.to_dict() for r in runs],
        }
        if len(aggregates) >= 2:
            report_json["comparisons"] = []
            for i in range(len(aggregates)):
                for j in range(i + 1, len(aggregates)):
                    comps = compare_variants(aggregates[i], aggregates[j])
                    report_json["comparisons"].extend([c.to_dict() for c in comps])

        (output_dir / "report.json").write_text(json.dumps(report_json, indent=2))

    return report_md
