"""Cost estimation for image generation runs based on token usage and known pricing."""

from __future__ import annotations

from datetime import datetime

from pixel_magic.evaluation.runner import EvalRun


# ── Pricing table (USD per 1K tokens) ────────────────────────────────
# Source: published pricing pages as of 2026-03.
# Image generation models charge per token (input prompt + output image tokens).

MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI image models — per 1K tokens
    "gpt-image-1": {
        "input_per_1k": 0.005,    # $5.00 / 1M = $0.005 / 1K
        "output_per_1k": 0.040,   # $40.00 / 1M = $0.040 / 1K
    },
    "gpt-image-1.5": {
        "input_per_1k": 0.005,
        "output_per_1k": 0.040,
    },
    # Gemini image models — per 1K tokens (input/output image tokens)
    "gemini-2.5-flash-image": {
        "input_per_1k": 0.00015,  # $0.15 / 1M
        "output_per_1k": 0.00060, # $0.60 / 1M (image output)
    },
    "gemini-3.1-flash-image-preview": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    },
}


def _get_tokens(metadata: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from generation metadata."""
    usage = metadata.get("usage", {})
    provider = metadata.get("provider", "")

    if provider == "openai":
        return (
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )
    elif provider == "gemini":
        return (
            usage.get("prompt_token_count", 0),
            usage.get("candidates_token_count", 0),
        )
    return (0, 0)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a single generation."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    return (
        (input_tokens / 1000) * pricing["input_per_1k"]
        + (output_tokens / 1000) * pricing["output_per_1k"]
    )


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
        inp, out = _get_tokens(meta)
        model = meta.get("model", rec.model_used)
        cost = _estimate_cost(model, inp, out)

        total_gen_time += rec.generation_time_s
        total_input += inp
        total_output += out
        total_cost += cost

        per_case.append({
            "case_name": rec.case_name,
            "model": model,
            "gen_time_s": round(rec.generation_time_s, 2),
            "input_tokens": inp,
            "output_tokens": out,
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
