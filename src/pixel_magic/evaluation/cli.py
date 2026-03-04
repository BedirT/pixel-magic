#!/usr/bin/env python3
"""CLI entry point for running evaluations and generating reports.

Usage:
    # Run evaluation with current settings
    uv run python -m pixel_magic.evaluation.cli run --variant gemini_baseline

    # Run specific cases only
    uv run python -m pixel_magic.evaluation.cli run --variant test --cases warrior_4dir mage_4dir

    # Run with repeats for statistical significance
    uv run python -m pixel_magic.evaluation.cli run --variant gemini_v2 --repeats 3

    # Compare two runs
    uv run python -m pixel_magic.evaluation.cli compare output/eval/gemini_v1/results.json output/eval/openai_v1/results.json

    # List available test cases
    uv run python -m pixel_magic.evaluation.cli list-cases
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def cmd_run(args: argparse.Namespace) -> None:
    """Run evaluation on test cases."""
    from pixel_magic.config import Settings
    from pixel_magic.evaluation.cases import get_standard_cases
    from pixel_magic.evaluation.metrics import aggregate_results
    from pixel_magic.evaluation.runner import EvalRunner
    from pixel_magic.generation.prompts import PromptBuilder

    settings = Settings()

    # CLI flag overrides .env provider
    active_provider = args.provider or settings.provider

    # Create provider
    if active_provider == "openai":
        from pixel_magic.providers.openai import OpenAIProvider
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            quality=settings.openai_quality,
        )
    else:
        from pixel_magic.providers.gemini import GeminiProvider
        provider = GeminiProvider(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
            image_model=settings.gemini_image_model,
            fallback_image_model=settings.gemini_image_fallback_model,
            enable_fallback=settings.gemini_enable_image_fallback,
            fallback_after_seconds=settings.gemini_fallback_timeout_s,
        )

    prompts = PromptBuilder()
    runner = EvalRunner(provider, prompts, settings)

    cases = get_standard_cases()
    if args.cases:
        case_set = set(args.cases)
        cases = [c for c in cases if c.name in case_set]
        if not cases:
            logger.error("No matching cases found for: %s", args.cases)
            sys.exit(1)

    logger.info(
        "Starting evaluation: variant=%s, cases=%d, repeats=%d, provider=%s",
        args.variant, len(cases), args.repeats, active_provider,
    )

    concurrency = getattr(args, 'concurrency', 1) or 1
    run = await runner.run_all(
        cases, variant_label=args.variant, repeats=args.repeats, concurrency=concurrency,
    )
    agg = aggregate_results(run.results, args.variant)

    await provider.close()

    # Compute cost/latency summary
    from pixel_magic.evaluation.cost import estimate_run_cost
    cost_summary = estimate_run_cost(run)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Evaluation Complete: {args.variant}")
    print(f"{'=' * 60}")
    print(f"Total cases: {agg.total_runs}")
    print(f"Errors:      {agg.error_count}")
    print(f"Overall:     {agg.overall_mean:.3f} (pass rate: {agg.overall_pass_rate:.0%})")
    print(f"\nDimension scores:")
    for dim, stats in agg.dimensions.items():
        bar = "█" * int(stats.mean * 20) + "░" * (20 - int(stats.mean * 20))
        print(f"  {dim:30s} {bar} {stats.mean:.3f} ± {stats.std:.3f}")
    print(f"\n--- Cost & Latency ---")
    print(f"Total generation time:  {cost_summary['total_gen_time_s']:.1f}s")
    print(f"Mean gen time/case:     {cost_summary['mean_gen_time_s']:.1f}s")
    print(f"Wall-clock time:        {cost_summary['wall_clock_s']:.1f}s")
    print(f"Total input tokens:     {cost_summary['total_input_tokens']:,}")
    print(f"Total output tokens:    {cost_summary['total_output_tokens']:,}")
    print(f"Estimated cost:         ${cost_summary['estimated_cost_usd']:.4f}")
    print(f"\nResults saved to: {settings.output_dir / 'eval' / args.variant / 'results.json'}")


async def cmd_compare(args: argparse.Namespace) -> None:
    """Compare multiple evaluation runs."""
    from pixel_magic.evaluation.report import generate_report
    from pixel_magic.evaluation.runner import EvalRun

    runs = []
    for p in args.run_paths:
        path = Path(p)
        if not path.exists():
            logger.error("Results file not found: %s", path)
            sys.exit(1)
        runs.append(EvalRun.load(path))

    output_dir = Path(args.output) if args.output else Path("output/eval/comparison")
    md = generate_report(runs, output_dir=output_dir)
    print(md)
    print(f"\nReport saved to: {output_dir / 'report.md'}")


def cmd_list_cases(_args: argparse.Namespace) -> None:
    """List available test cases."""
    from pixel_magic.evaluation.cases import get_standard_cases

    cases = get_standard_cases()
    print(f"\nAvailable evaluation cases ({len(cases)} total):\n")
    for case in cases:
        print(f"  {case.name:25s}  {case.asset_type:25s}  ({case.expected_count} sprites)")
        if case.description:
            print(f"  {'':25s}  {case.description}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pixel Magic evaluation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Run evaluation on test cases")
    p_run.add_argument("--variant", "-v", default="default", help="Label for this run")
    p_run.add_argument("--provider", "-p", choices=["gemini", "openai"], help="Override provider (default: from .env)")
    p_run.add_argument("--cases", "-c", nargs="*", help="Specific case names to run")
    p_run.add_argument("--repeats", "-r", type=int, default=1, help="Repetitions per case")
    p_run.add_argument("--concurrency", "-j", type=int, default=4, help="Max parallel generations (default: 4)")

    # compare
    p_cmp = sub.add_parser("compare", help="Compare evaluation runs")
    p_cmp.add_argument("run_paths", nargs="+", help="Paths to results.json files")
    p_cmp.add_argument("--output", "-o", help="Output directory for report")

    # list-cases
    sub.add_parser("list-cases", help="List available test cases")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "compare":
        asyncio.run(cmd_compare(args))
    elif args.command == "list-cases":
        cmd_list_cases(args)


if __name__ == "__main__":
    main()
