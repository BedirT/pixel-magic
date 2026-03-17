"""Cost estimation for image generation runs based on token usage and known pricing."""

from __future__ import annotations

from datetime import datetime

from pixel_magic.evaluation.runner import EvalRun
from pixel_magic.usage import MODEL_PRICING, estimate_token_cost, normalize_usage_metadata


def _usage_buckets(metadata: dict) -> list[tuple[str, dict]]:
    """Return usage buckets from direct-mode or agent-mode metadata."""
    usage = metadata.get("usage")
    if isinstance(usage, dict) and any(key in usage for key in ("generation", "judge", "agent")):
        buckets = []
        for key in ("generation", "judge", "agent"):
            bucket = usage.get(key)
            if isinstance(bucket, dict):
                buckets.append((key, bucket))
        return buckets
    return [("generation", metadata)]


def _get_tokens(metadata: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from any normalized metadata shape."""
    normalized = normalize_usage_metadata(metadata, provider=str(metadata.get("provider", "")))
    return normalized["input_tokens"], normalized["output_tokens"]


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a single generation."""
    if model not in MODEL_PRICING:
        return 0.0
    return estimate_token_cost(model, input_tokens, output_tokens)


def estimate_run_cost(run: EvalRun) -> dict:
    """Compute cost and latency summary for a completed EvalRun.

    Returns:
        Dict with: total_gen_time_s, mean_gen_time_s, wall_clock_s,
        total_input_tokens, total_output_tokens, estimated_cost_usd,
        per_case (list of per-case breakdowns).
    """
    total_gen_time = 0.0
    total_input = 0
    total_output = 0
    total_cost = 0.0
    per_case: list[dict] = []

    for rec in run.records:
        meta = rec.generation_metadata
        case_input = 0
        case_output = 0
        cost = 0.0
        model = rec.model_used

        for bucket_name, bucket in _usage_buckets(meta):
            inp, out = _get_tokens(bucket)
            bucket_model = bucket.get("model", model)
            bucket_cost = _estimate_cost(bucket_model, inp, out)
            case_input += inp
            case_output += out
            cost += bucket_cost
            if bucket_name == "generation" and bucket_model:
                model = bucket_model

        total_gen_time += rec.generation_time_s
        total_input += case_input
        total_output += case_output
        total_cost += cost

        per_case.append({
            "case_name": rec.case_name,
            "model": model,
            "gen_time_s": round(rec.generation_time_s, 2),
            "input_tokens": case_input,
            "output_tokens": case_output,
            "cost_usd": round(cost, 6),
        })

    # Wall-clock time from timestamps
    wall_clock = 0.0
    try:
        t0 = datetime.fromisoformat(run.started_at.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(run.completed_at.replace("Z", "+00:00"))
        wall_clock = (t1 - t0).total_seconds()
    except (ValueError, AttributeError):
        wall_clock = total_gen_time  # fallback

    n = len(run.records) or 1
    return {
        "total_gen_time_s": round(total_gen_time, 2),
        "mean_gen_time_s": round(total_gen_time / n, 2),
        "wall_clock_s": round(wall_clock, 2),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": round(total_cost, 6),
        "per_case": per_case,
    }
