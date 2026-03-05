---
title: Providers and Environment
---

## Provider Selection

Set:

```bash
PIXEL_MAGIC_PROVIDER=gemini
```

or:

```bash
PIXEL_MAGIC_PROVIDER=openai
```

## Required Keys

- Gemini path: `GOOGLE_API_KEY`
- OpenAI image path: `OPENAI_API_KEY`
- OpenAI Agents SDK runtime also uses `OPENAI_API_KEY`

## Common Environment Variables

| Variable | Purpose |
|---|---|
| `PIXEL_MAGIC_PROVIDER` | Active provider (`gemini` / `openai`) |
| `PIXEL_MAGIC_IMAGE_SIZE` | Provider generation size |
| `PIXEL_MAGIC_PALETTE_SIZE` | Default max palette size |
| `PIXEL_MAGIC_ALPHA_POLICY` | Alpha compliance mode |
| `PIXEL_MAGIC_OUTPUT_DIR` | Output folder |
| `PIXEL_MAGIC_QA_VISION_ENABLED` | Enable optional vision QA in `run_qa_check` |
| `PIXEL_MAGIC_AGENT_MODEL` | Reasoning model for route/plan/validation agents |

## Provider Switching at Runtime

Use MCP tool:

- `set_provider(provider="gemini" | "openai")`

This recreates provider adapter, agent runtime, and workflow executor in-process.
