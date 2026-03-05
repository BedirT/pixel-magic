# Pixel Magic Benchmark Report (2026-03-04)

This file contains the benchmark snapshot and model-specific operational notes.

## 1) Benchmark Setup

- Dataset: 12 standard evaluation cases
- Judge: LLM-as-judge (8 dimensions, normalized 0-1)
- Run type: single repeat (`--repeats 1`) for model comparison; 5 repeats for framing validation
- Compared models:
  - `gpt-image-1`
  - `gpt-image-1.5`
  - `gemini-2.5-flash-image`
  - `gemini-3.1-flash-image-preview`

## 2) Model Comparison Results (1× repeat)

| Model | Cases | Errors | Overall | Pass Rate | Mean Latency | Estimated Cost |
|---|---:|---:|---:|---:|---:|---:|
| `gpt-image-1` | 12 | 0 | 0.800 | 92% | 19.9s | $0.5241 |
| `gpt-image-1.5` | 12 | 0 | 0.767 | 83% | 18.0s | $0.7162 |
| `gemini-2.5-flash-image` | 12 | 0 | 0.917 | 100% | 7.2s | $0.0098 |
| `gemini-3.1-flash-image-preview` | 12 | 2 | 0.940 | 100%* | 112.5s | $0.0095 |

\* Pass rate is over successful cases only (10/10); 2 cases errored.

## 3) Framing & Direction Improvement Results (5× repeats, `framing_v1`)

After implementing magenta separator framing in prompts and fixing 4-dir isometric directions (SE+NE), the evaluation suite was run with 5 repeats per case (60 total evaluations) using the Gemini provider with primary `gemini-3.1-flash-image-preview` and fallback to `gemini-2.5-flash-image`.

### Per-case results

| Case | Runs | Errors | Mean | Min | Max | Pass Rate |
|---|---:|---:|---:|---:|---:|---:|
| warrior_4dir | 5 | 0 | 0.98 | 0.90 | 1.00 | 100% |
| mage_4dir | 5 | 0 | 0.84 | 0.50 | 1.00 | 80% |
| thief_8dir | 5 | 0 | 0.92 | 0.80 | 1.00 | 100% |
| warrior_walk | 5 | 0 | 0.88 | 0.60 | 1.00 | 80% |
| mage_attack | 5 | 0 | 0.84 | 0.60 | 1.00 | 80% |
| forest_ground | 5 | 0 | 1.00 | 1.00 | 1.00 | 100% |
| desert_ground | 5 | 0 | 0.98 | 0.90 | 1.00 | 100% |
| rpg_weapons | 5 | 0 | 0.92 | 0.90 | 1.00 | 100% |
| consumables | 5 | 0 | 0.88 | 0.80 | 0.90 | 100% |
| fire_explosion | 5 | 0 | 0.92 | 0.90 | 1.00 | 100% |
| heal_spell | 5 | 0 | 0.96 | 0.90 | 1.00 | 100% |
| rpg_ui | 5 | 0 | 0.90 | 0.80 | 1.00 | 100% |

**Overall: 0.918 mean, 95% pass rate (57/60), 0 generation errors.**

### Dimension breakdown

| Dimension | Mean | Min |
|---|---:|---:|
| instruction_following | 0.888 | 0.10 |
| pixel_art_quality | 0.977 | 0.90 |
| style_adherence | 0.965 | 0.90 |
| composition_layout | 0.905 | 0.20 |
| silhouette_readability | 0.972 | 0.90 |
| palette_discipline | 0.920 | 0.40 |
| consistency | 0.978 | 0.60 |
| overall | 0.918 | 0.50 |

### Separator detection verification

Programmatic verification of the latest generated images shows that magenta separator lines are produced in a subset of generations and the extractor correctly detects them:

| Case | Separator Lines Detected | Frames Extracted via Separators |
|---|---|---|
| warrior_4dir | ✓ (1 group) | 2 frames (694×768 each) |
| fire_explosion | ✓ (5 groups) | 6 frames (411×416 each) |
| heal_spell | ✓ (3 groups) | 4 frames (517×512 each) |
| Other 9 cases | — | Falls back to heuristic extraction |

The fallback chain (component detection → grid → strip) handles cases where the AI model does not produce separator lines.

### Failure analysis

All 3 failures (out of 60 runs) were correctly identified by the judge:
- **mage_4dir** (0.50): AI generated 8 sprites in 2 rows instead of 2 in a horizontal strip
- **mage_attack** (0.60): AI generated 10 sprites in a 2×5 grid instead of 6-frame strip
- **warrior_walk** (0.60): AI generated 6 frames instead of 4, arranged in wrong layout

All failures scored low on `instruction_following` (0.10) and `composition_layout` (0.20) while maintaining high scores on `pixel_art_quality` (0.90) and `style_adherence` (0.90+), confirming the judge accurately distinguishes quality from correctness.

- Quality winner: `gemini-3.1-flash-image-preview`
- Reliability winner: `gemini-2.5-flash-image`
- Cost winner: both Gemini image models (~$0.01 per run) by a large margin over OpenAI runs
- Best operational default: `gemini-3.1-flash-image-preview` with auto-fallback to `gemini-2.5-flash-image`

## 4) Known Issues Research (Gemini 3.1 Flash Image Preview)

### Verified from official docs

1. Preview lifecycle and potential volatility:
   - Model page lists image models as preview lifecycle variants.
   - Preview models can have more restrictive limits and faster iteration.

2. Capacity-related backend errors are expected classes:
   - Official troubleshooting maps `503 UNAVAILABLE` to temporary overload/capacity shortages.
   - Official guidance includes retrying and temporarily switching models.

3. Thought signatures in multi-turn workflows:
   - Image generation/editing docs explicitly state thought signatures should be preserved in conversation history.
   - Missing signature circulation in custom chat history handling can fail subsequent turns.

4. Image config constraints are strict:
   - Official image docs specify accepted `image_size` values (`512px`, `1K`, `2K`, `4K`) and uppercase `K` requirement.
   - Aspect ratio/image_size behavior depends on model and request mode.

### Community-reported (treat as signal, not guaranteed)

- Intermittent `400` on repeated requests with same payload
- Inconsistent adherence to `image_size`/aspect settings in some client paths
- Multi-turn edit continuity failures (partial reset/recomposition)
- Occasional empty/low-value outputs while token usage is non-zero
- Temporary “no capacity available” style service responses

These reports are plausible and align with our observed 3.1 instability pattern, but should be verified against your exact SDK version, endpoint mode, and request shape.

## 5) Practical Mitigations Used in Pixel Magic

- Primary model: `gemini-3.1-flash-image-preview`
- Automatic timeout fallback: if primary path exceeds `120s` budget or fails, retry via `gemini-2.5-flash-image`
- Retry on transient backend failures (`429`, `500`, `503`)
- Cost/latency tracking enabled in eval output

## 6) Source Links

- Gemini image generation docs: https://ai.google.dev/gemini-api/docs/image-generation
- Gemini troubleshooting: https://ai.google.dev/gemini-api/docs/troubleshooting
- Gemini models overview: https://ai.google.dev/gemini-api/docs/models
- Gemini release notes: https://ai.google.dev/gemini-api/docs/changelog
- OpenAI compatibility notes: https://ai.google.dev/gemini-api/docs/openai
- Community forum index: https://discuss.ai.google.dev/
