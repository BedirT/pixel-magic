# Pixel Magic Benchmark Report (2026-03-04)

This file contains the benchmark snapshot and model-specific operational notes.

## 1) Benchmark Setup

- Dataset: 12 standard evaluation cases
- Judge: LLM-as-judge (8 dimensions, normalized 0-1)
- Run type: single repeat (`--repeats 1`)
- Compared models:
  - `gpt-image-1`
  - `gpt-image-1.5`
  - `gemini-2.5-flash-image`
  - `gemini-3.1-flash-image-preview`

## 2) Results Summary

| Model | Cases | Errors | Overall | Pass Rate | Mean Latency | Estimated Cost |
|---|---:|---:|---:|---:|---:|---:|
| `gpt-image-1` | 12 | 0 | 0.800 | 92% | 19.9s | $0.5241 |
| `gpt-image-1.5` | 12 | 0 | 0.767 | 83% | 18.0s | $0.7162 |
| `gemini-2.5-flash-image` | 12 | 0 | 0.917 | 100% | 7.2s | $0.0098 |
| `gemini-3.1-flash-image-preview` | 12 | 2 | 0.940 | 100%* | 112.5s | $0.0095 |

\* Pass rate is over successful cases only (10/10); 2 cases errored.

## 3) Interpretation

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
