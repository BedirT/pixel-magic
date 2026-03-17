"""Shared usage normalization and token-cost helpers."""

from __future__ import annotations

from typing import Any


MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-image-1": {
        "input_per_1k": 0.005,
        "output_per_1k": 0.040,
    },
    "gpt-image-1.5": {
        "input_per_1k": 0.005,
        "output_per_1k": 0.040,
    },
    "gemini-2.5-flash-image": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    },
    "gemini-3.1-flash-image-preview": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    },
}


def normalize_usage_metadata(
    metadata: dict[str, Any] | None,
    *,
    provider: str = "",
) -> dict[str, int]:
    """Normalize provider-specific usage fields into input/output/total tokens."""
    payload = metadata or {}
    if any(key in payload for key in ("input_tokens", "output_tokens", "total_tokens")):
        input_tokens = int(payload.get("input_tokens", 0) or 0)
        output_tokens = int(payload.get("output_tokens", 0) or 0)
        total_tokens = int(payload.get("total_tokens", input_tokens + output_tokens) or 0)
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    raw_usage = payload.get("raw_usage", payload.get("usage", {}))
    if not isinstance(raw_usage, dict):
        raw_usage = {}

    normalized = payload.get("normalized_usage")
    if isinstance(normalized, dict):
        return {
            "input_tokens": int(normalized.get("input_tokens", 0) or 0),
            "output_tokens": int(normalized.get("output_tokens", 0) or 0),
            "total_tokens": int(normalized.get("total_tokens", 0) or 0),
        }

    effective_provider = str(payload.get("provider", provider or ""))
    if effective_provider == "gemini":
        input_tokens = int(raw_usage.get("input_tokens", raw_usage.get("prompt_token_count", 0)) or 0)
        output_tokens = int(raw_usage.get("output_tokens", raw_usage.get("candidates_token_count", 0)) or 0)
        total_tokens = int(raw_usage.get("total_tokens", raw_usage.get("total_token_count", input_tokens + output_tokens)) or 0)
    else:
        input_tokens = int(raw_usage.get("input_tokens", raw_usage.get("prompt_token_count", 0)) or 0)
        output_tokens = int(raw_usage.get("output_tokens", raw_usage.get("candidates_token_count", 0)) or 0)
        total_tokens = int(raw_usage.get("total_tokens", raw_usage.get("total_token_count", input_tokens + output_tokens)) or 0)

    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def estimate_token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD token cost for a single usage record."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    return (
        (input_tokens / 1000) * pricing["input_per_1k"]
        + (output_tokens / 1000) * pricing["output_per_1k"]
    )


def build_usage_entry(
    metadata: dict[str, Any] | None,
    *,
    provider: str = "",
    model: str = "",
    prompt_key: str = "",
    reference_count: int | None = None,
) -> dict[str, Any]:
    """Build a normalized usage entry that can be aggregated across calls."""
    payload = dict(metadata or {})
    effective_provider = str(payload.get("provider", provider or ""))
    effective_model = str(payload.get("model", model or ""))
    normalized = normalize_usage_metadata(payload, provider=effective_provider)
    raw_usage = payload.get("raw_usage", payload.get("usage", {}))
    if not isinstance(raw_usage, dict):
        raw_usage = {}

    entry = {
        "prompt_key": prompt_key,
        "provider": effective_provider,
        "model": effective_model,
        "endpoint": str(payload.get("endpoint", "")),
        "image_size": str(payload.get("image_size", payload.get("size", ""))),
        "reference_count": int(payload.get("reference_count", reference_count or 0) or 0),
        "raw_usage": raw_usage,
        "normalized_usage": normalized,
        "input_tokens": normalized["input_tokens"],
        "output_tokens": normalized["output_tokens"],
        "total_tokens": normalized["total_tokens"],
        "estimated_cost_usd": round(
            estimate_token_cost(
                effective_model,
                normalized["input_tokens"],
                normalized["output_tokens"],
            ),
            6,
        ),
    }
    fallback = payload.get("fallback")
    if isinstance(fallback, dict):
        entry["fallback"] = fallback
    return entry


def summarize_usage_entries(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Summarize per-call usage entries into a durable bucket."""
    entries = list(entries or [])
    providers = {str(entry.get("provider", "")) for entry in entries if entry.get("provider")}
    models = {str(entry.get("model", "")) for entry in entries if entry.get("model")}

    input_tokens = sum(int(entry.get("input_tokens", 0) or 0) for entry in entries)
    output_tokens = sum(int(entry.get("output_tokens", 0) or 0) for entry in entries)
    total_tokens = sum(int(entry.get("total_tokens", 0) or 0) for entry in entries)
    estimated_cost = sum(float(entry.get("estimated_cost_usd", 0.0) or 0.0) for entry in entries)

    return {
        "provider": next(iter(providers)) if len(providers) == 1 else "",
        "model": next(iter(models)) if len(models) == 1 else "",
        "calls": len(entries),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost, 6),
        "entries": entries,
    }