"""LLM-as-judge evaluation framework for pixel art generation quality."""

from pixel_magic.evaluation.judge import JudgeResult, PixelArtJudge
from pixel_magic.evaluation.metrics import (
    AggregateScores,
    ComparisonResult,
    aggregate_results,
    compare_variants,
)
from pixel_magic.evaluation.cases import EvalCase, get_standard_cases
from pixel_magic.evaluation.runner import EvalRun, EvalRunner
from pixel_magic.evaluation.report import generate_report

__all__ = [
    "AggregateScores",
    "ComparisonResult",
    "EvalCase",
    "EvalRun",
    "EvalRunner",
    "JudgeResult",
    "PixelArtJudge",
    "aggregate_results",
    "compare_variants",
    "generate_report",
    "get_standard_cases",
]
