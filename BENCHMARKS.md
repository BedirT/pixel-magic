# Pixel Magic — Model Selection & Evaluation Guide

This document is the **operational guide** for choosing models and running/interpreting evaluation in this repo.

For the latest benchmark snapshot and raw comparison summary, see:
- `docs/BENCHMARK_REPORT_2026-03-04.md`
- `output/eval/model_comparison_4way/report.md`

---

## 1) Recommended Model Strategy

### Default runtime strategy (now implemented)

- **Primary image model:** `gemini-3.1-flash-image-preview`
- **Fallback image model:** `gemini-2.5-flash-image`
- **Fallback trigger:** primary path exceeds `120s` budget or fails

Why this strategy:
- `gemini-3.1-flash-image-preview` currently gives the highest visual quality in our evals.
- `gemini-2.5-flash-image` is significantly more stable and fast when 3.1 has capacity spikes.

### Config knobs

All via environment variables:

- `PIXEL_MAGIC_GEMINI_IMAGE_MODEL` (default: `gemini-3.1-flash-image-preview`)
- `PIXEL_MAGIC_GEMINI_IMAGE_FALLBACK_MODEL` (default: `gemini-2.5-flash-image`)
- `PIXEL_MAGIC_GEMINI_ENABLE_IMAGE_FALLBACK` (default: `true`)
- `PIXEL_MAGIC_GEMINI_FALLBACK_TIMEOUT_S` (default: `120`)

Example:

```bash
PIXEL_MAGIC_PROVIDER=gemini \
PIXEL_MAGIC_GEMINI_IMAGE_MODEL=gemini-3.1-flash-image-preview \
PIXEL_MAGIC_GEMINI_IMAGE_FALLBACK_MODEL=gemini-2.5-flash-image \
PIXEL_MAGIC_GEMINI_FALLBACK_TIMEOUT_S=120 \
uv run python -m pixel_magic.evaluation.cli run --variant gemini_default
```

---

## 2) How Evaluation Works

Pixel Magic uses an LLM-as-judge harness over a fixed suite of test cases.

### What gets measured

Per run, each case is scored on normalized `0.0–1.0` dimensions:

- `instruction_following`
- `pixel_art_quality`
- `style_adherence`
- `composition_layout`
- `silhouette_readability`
- `palette_discipline`
- `consistency`
- `overall`

### Aggregates reported

- **Overall mean** across scored cases
- **Pass rate** (`overall >= 0.70`)
- **Error count** (generation failures)
- **Mean generation latency**
- **Estimated cost** from token usage metadata
- Pairwise model comparisons with effect size and CI-overlap significance flag

### Important interpretation detail

If a case errors, it does not contribute to score means. So:

- a model can show high pass rate on successful cases,
- while still having meaningful operational failure rate.

Always read **quality + errors + latency** together.

---

## 3) Running Evaluations

### Run a full variant

```bash
uv run python -m pixel_magic.evaluation.cli run \
  --provider gemini \
  --variant my_variant \
  --repeats 1 \
  --concurrency 4
```

### Run selected cases

```bash
uv run python -m pixel_magic.evaluation.cli run \
  --provider gemini \
  --variant quick_check \
  --cases warrior_4dir mage_4dir fire_explosion
```

### Compare multiple completed runs

```bash
uv run python -m pixel_magic.evaluation.cli compare \
  output/eval/modelcmp_openai_gpt_image_1_r1/results.json \
  output/eval/modelcmp_openai_gpt_image_1_5_r1/results.json \
  output/eval/modelcmp_gemini_25_flash_image_r1/results.json \
  output/eval/modelcmp_gemini_31_flash_image_preview_r1/results.json \
  --output output/eval/model_comparison_4way
```

---

## 4) How to Interpret Compare Reports

### Summary table

Use this for quick ranking:

- `Overall`
- `Errors`
- `Mean Latency`
- `Est. Cost`

### Dimension table

Use this to understand **why** one model wins:

- Pixel-art-specific dimensions (`pixel_art_quality`, `palette_discipline`, `consistency`) matter more for this project than generic instruction-only quality.

### Pairwise section

- `Δ` is mean difference (B - A style as rendered)
- `d` is Cohen’s d effect size
- `Sig?` is a conservative CI-overlap heuristic

Practical guidance:

- Prefer large positive deltas on `overall` plus low `errors`.
- Treat preview-model wins with unstable error/latency as conditional wins.

---

## 5) Current Selection Policy

Use this decision rule unless product goals change:

1. Run primary on `gemini-3.1-flash-image-preview`.
2. Auto-fallback to `gemini-2.5-flash-image` if primary exceeds timeout budget or fails.
3. For batch or strict SLA workloads, optionally pin directly to `gemini-2.5-flash-image`.

---

## 6) Known Caveats to Watch

- Preview models can have capacity instability (`503/500`) and latency spikes.
- Image-size/aspect controls may evolve quickly across model revisions.
- Multi-turn image editing requires preserving model response history/signatures when using chat workflows.
- OpenAI-compat and native SDKs can behave differently for edge cases.

When behavior shifts, rerun the benchmark suite and update the benchmark report file.
