---
title: MCP Tool Reference
---

This page is the authoritative MCP surface for `src/pixel_magic/server.py`.

## Response Conventions

- All tools return a string payload.
- Most tools return JSON strings.
- `compare_evaluations` returns a Markdown string (report body).
- File paths are local filesystem paths on the server host.

## Generation Envelope (All Generation Tools)

These tools return the workflow `JobResult` envelope plus helper fields:

- `generate_character`
- `extend_character_animation`
- `generate_tileset`
- `generate_items`
- `generate_effect`
- `generate_ui_elements`
- `generate_custom`

### Success Shape

```json
{
  "status": "success",
  "job_id": "b1c2d3",
  "stage": "finalize",
  "request": {
    "asset_type": "character",
    "name": "knight",
    "objective": "A knight in silver armor",
    "style": "16-bit SNES RPG style",
    "resolution": "64x64",
    "max_colors": 16,
    "expected_frames": 1,
    "layout": "horizontal_strip",
    "parameters": {}
  },
  "plan": {
    "asset_type": "character",
    "expected_total_frames": 20,
    "planned_prompts": [],
    "qa_min_score": 0.7,
    "notes": "..."
  },
  "artifacts": {
    "output_dir": "output/knight",
    "atlas_path": "output/knight/knight_atlas.png",
    "metadata_path": "output/knight/knight_metadata.json",
    "raw_paths": {},
    "frame_paths": {},
    "total_frames": 20
  },
  "deterministic_gate": {
    "passed": true,
    "checks": [],
    "failure_reasons": []
  },
  "final_validation": {
    "decision": "pass",
    "overall_score": 0.88,
    "critical_issues": [],
    "retry_instructions": "",
    "confidence": 0.84,
    "notes": ""
  },
  "metrics": {
    "provider": "gemini",
    "model": "gemini-2.5-flash-image-preview",
    "total_generation_calls": 6,
    "retry_count": 0,
    "duration_s": 8.91
  },
  "warnings": [],
  "errors": [],
  "trace": [],
  "output_paths": ["output/knight/walk_south_east_000.png"],
  "output_dir": "output/knight"
}
```

### Failure Shape

```json
{
  "status": "failed",
  "job_id": "b1c2d3",
  "stage": "deterministic_gate",
  "errors": [
    {
      "code": "QA_FAILED",
      "message": "Deterministic QA gate failed",
      "stage": "deterministic_gate",
      "details": {
        "failed_checks": ["alpha_compliance: 3800/4096 pixels have binary alpha"]
      }
    }
  ],
  "trace": []
}
```

## Generation Tools

### `generate_character`

Generate a full character sprite set (directions + animations).

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `character_description` | string | yes | - |
| `name` | string | no | `"character"` |
| `style` | string | no | `"16-bit SNES RPG style"` |
| `direction_mode` | integer | no | `4` |
| `animations` | object | no | `{}` |
| `resolution` | string `WxH` | no | `"64x64"` |
| `max_colors` | integer | no | `16` |
| `palette_name` | string | no | `null` |
| `palette_hint` | string | no | `""` |

**Success response example**

Uses the generation envelope. Character runs usually contain multiple animation/direction frame groups under `artifacts.frame_paths`.

**Failure example**

```json
{
  "status": "failed",
  "stage": "final_validator_agent",
  "errors": [{"code": "VALIDATOR_FAILED", "message": "Final validator rejected output"}]
}
```

### `extend_character_animation`

Generate a new animation for an existing character using a reference image.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `character_name` | string | yes | - |
| `animation_name` | string | yes | - |
| `reference_image_path` | string path | yes | - |
| `frame_count` | integer | no | `4` |
| `description` | string | no | `""` |
| `duration_ms` | integer | no | `100` |
| `is_looping` | boolean | no | `true` |
| `direction_mode` | integer | no | `4` |
| `style` | string | no | `"16-bit SNES RPG style"` |
| `resolution` | string `WxH` | no | `"64x64"` |
| `max_colors` | integer | no | `16` |
| `palette_name` | string | no | `null` |

**Success response example**

Uses the generation envelope. Output folder is deterministic: `<character_name>_<animation_name>`.

**Failure example**

```json
{
  "status": "failed",
  "stage": "input_validate",
  "errors": [
    {
      "code": "INVALID_INPUT",
      "message": "Reference image path does not exist",
      "details": {"path": "/tmp/missing_ref.png"}
    }
  ]
}
```

### `generate_tileset`

Generate an isometric tileset batch.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `biome` | string | yes | - |
| `tile_types` | array[string] | yes | - |
| `name` | string | no | `"tileset"` |
| `tile_width` | integer | no | `64` |
| `tile_height` | integer | no | `32` |
| `style` | string | no | `"16-bit isometric RPG style"` |
| `max_colors` | integer | no | `16` |
| `palette_name` | string | no | `null` |

**Success response example**

Uses the generation envelope. `artifacts.total_frames` typically matches `len(tile_types)`.

**Failure example**

```json
{
  "status": "failed",
  "stage": "generate",
  "errors": [{"code": "PROVIDER_ERROR", "message": "Image generation failed"}]
}
```

### `generate_items`

Generate a batch of item icons.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `item_descriptions` | array[string] | yes | - |
| `resolution` | string `WxH` | no | `"32x32"` |
| `style` | string | no | `"16-bit SNES RPG style"` |
| `max_colors` | integer | no | `16` |
| `view` | string | no | `"front-facing icon"` |
| `palette_name` | string | no | `null` |

**Success response example**

Uses the generation envelope.

**Failure example**

```json
{
  "status": "failed",
  "stage": "deterministic_gate",
  "errors": [{"code": "QA_FAILED", "message": "Deterministic QA gate failed"}]
}
```

### `generate_effect`

Generate an animated effect sprite sequence.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `effect_description` | string | yes | - |
| `frame_count` | integer | no | `6` |
| `resolution` | string `WxH` | no | `"64x64"` |
| `style` | string | no | `"16-bit pixel art"` |
| `max_colors` | integer | no | `12` |
| `color_emphasis` | string | no | `""` |

**Success response example**

Uses the generation envelope.

**Failure example**

```json
{
  "status": "failed",
  "stage": "extract",
  "errors": [{"code": "EXTRACTION_MISMATCH", "message": "Extracted frame count mismatch"}]
}
```

### `generate_ui_elements`

Generate a batch of UI sprites.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `element_descriptions` | array[string] | yes | - |
| `resolution` | string `WxH` | no | `"64x64"` |
| `style` | string | no | `"16-bit RPG UI style"` |
| `max_colors` | integer | no | `8` |

**Success response example**

Uses the generation envelope.

**Failure example**

```json
{
  "status": "failed",
  "stage": "generate",
  "errors": [{"code": "TIMEOUT", "message": "Workflow timed out"}]
}
```

### `generate_custom`

Generate from a freeform prompt.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `prompt` | string | yes | - |
| `frame_count` | integer | no | `1` |
| `layout` | string | no | `"horizontal_strip"` |

Allowed `layout` values: `horizontal_strip`, `vertical_strip`, `grid`, `auto_detect`.

**Success response example**

Uses the generation envelope.

**Failure example**

```json
{
  "status": "failed",
  "stage": "plan",
  "errors": [{"code": "PLAN_INVALID", "message": "Planner returned no prompts"}]
}
```

## Pipeline Tools

### `convert_image`

Convert one image through ingest, grid inference, projection, quantization, and cleanup.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `image_path` | string path | yes | - |
| `target_resolution` | string `WxH` | no | `null` |
| `palette_name` | string | no | `null` |
| `max_colors` | integer | no | `16` |
| `alpha_policy` | string | no | `"binary"` |
| `remove_bg` | boolean | no | `false` |

**Success response example**

```json
{
  "status": "success",
  "output_path": "output/converted/hero_pixel.png",
  "grid": {"macro_size": 1, "confidence": 0.97},
  "palette_size": 16,
  "resolution": "64x64"
}
```

**Failure example**

This tool raises an MCP error (exception), not a workflow failure envelope.

```text
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/missing.png'
```

### `process_sprite_sheet`

Extract, normalize, quantize, clean, and QA an existing sprite sheet.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `image_path` | string path | yes | - |
| `frame_count` | integer | no | `null` |
| `layout` | string | no | `"auto_detect"` |
| `palette_name` | string | no | `null` |
| `max_colors` | integer | no | `16` |
| `name` | string | no | `"sheet"` |

**Success response example**

```json
{
  "status": "success",
  "frame_count": 6,
  "output_paths": ["output/sheet/sheet_000.png"],
  "qa": {
    "passed": true,
    "checks": [
      {"name": "alpha_compliance", "passed": true, "score": 1.0, "details": "..."}
    ]
  }
}
```

**Failure example**

```text
ValueError: 'diagonal_strip' is not a valid CompositeLayout
```

### `extract_frames_tool`

Extract frames from a composite image and save each frame.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `image_path` | string path | yes | - |
| `frame_count` | integer | no | `null` |
| `layout` | string | no | `"auto_detect"` |

**Success response example**

```json
{
  "status": "success",
  "frame_count": 4,
  "output_paths": [
    "output/extracted/frame_000.png",
    "output/extracted/frame_001.png"
  ]
}
```

**Failure example**

```text
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/missing_sheet.png'
```

## QA Tool

### `run_qa_check`

Run deterministic QA checks, and optional vision QA, on image paths.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `image_paths` | array[string] | yes | - |
| `palette_name` | string | no | `null` |
| `alpha_policy` | string | no | `"binary"` |
| `run_vision` | boolean | no | `false` |

`run_vision` only adds vision checks when server config `qa_vision_enabled=true`.

**Success response example**

```json
{
  "passed": true,
  "checks": [
    {"name": "alpha_compliance", "passed": true, "score": 1.0, "details": "..."},
    {"name": "frame_size_consistency", "passed": true, "score": 1.0, "details": "..."}
  ]
}
```

**Failure example**

```text
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/missing_frame.png'
```

## Utility Tools

### `list_palettes`

List `.hex` palettes available under the configured palettes directory.

**Request fields**

None.

**Success response example**

```json
[
  {
    "name": "default_16",
    "size": 16,
    "colors": ["#000000", "#ffffff"],
    "path": "palettes/default_16.hex"
  }
]
```

**Failure example**

```text
ValueError: Invalid HEX color at line 3 in palette file
```

### `list_animations`

List built-in animation presets.

**Request fields**

None.

**Success response example**

```json
{
  "idle": {
    "frame_count": 4,
    "description": "...",
    "duration_ms": 150,
    "is_looping": true
  }
}
```

**Failure example**

No tool-specific failure payload. Unexpected runtime errors surface as MCP exception text.

### `list_prompt_templates`

List prompt templates and parameter names.

**Request fields**

None.

**Success response example**

```json
[
  {
    "name": "character_directions_4dir",
    "description": "...",
    "parameters": ["character_description", "style"],
    "reference_strategy": "none"
  }
]
```

**Failure example**

No tool-specific failure payload. Unexpected runtime errors surface as MCP exception text.

### `set_provider`

Switch active provider at runtime and rebuild provider/agent/executor state.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `provider` | string | yes | - |

Allowed values: `gemini`, `openai`.

**Success response example**

```json
{"status": "success", "provider": "openai"}
```

**Failure example**

```json
{"error": "Unknown provider: foo. Use 'gemini' or 'openai'."}
```

### `set_style_defaults`

Update default style settings for the running server process.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `direction_mode` | integer | no | unchanged |
| `resolution` | string `WxH` | no | unchanged |
| `palette_size` | integer | no | unchanged |
| `alpha_policy` | string | no | unchanged |

**Success response example**

```json
{
  "status": "success",
  "direction_mode": 4,
  "resolution": "64x64",
  "palette_size": 16,
  "alpha_policy": "binary"
}
```

**Failure example**

No tool-specific failure payload. Invalid values can cause downstream generation failures later.

## Evaluation Tools

### `run_evaluation`

Run offline evaluation cases and aggregate LLM-as-a-Judge results.

LLM-as-a-Judge is offline regression tooling, not a separate production gate.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `variant_label` | string | no | `"default"` |
| `case_names` | array[string] | no | `null` |
| `repeats` | integer | no | `1` |
| `mode` | string | no | `"direct"` |

`mode` values: `direct` or `agent` (`agent` runs the workflow executor).

**Success response example**

```json
{
  "status": "success",
  "variant": "baseline",
  "total_cases": 12,
  "errors": 1,
  "overall_mean": 0.842,
  "overall_pass_rate": 0.917,
  "dimensions": {"overall": 0.842},
  "results_path": "output/eval/baseline/results.json"
}
```

**Failure example**

When generation/judging fails per case, this tool usually still returns `status: success` with increased `errors` count. Hard runtime exceptions surface as MCP exception text.

### `compare_evaluations`

Compare multiple evaluation result files and return a Markdown report.

**Request fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `run_paths` | array[string] | yes | - |

**Success response example**

```md
# Evaluation Comparison

## Summary
- Run A overall: 0.81
- Run B overall: 0.85

## Dimension Comparison
| Dimension | Run A | Run B | Delta |
|---|---:|---:|---:|
| overall | 0.81 | 0.85 | +0.04 |
```

**Failure example**

```text
FileNotFoundError: [Errno 2] No such file or directory: 'output/eval/missing/results.json'
```

### `list_eval_cases`

List built-in evaluation test cases.

**Request fields**

None.

**Success response example**

```json
[
  {
    "name": "warrior_4dir",
    "template_name": "character_directions_4dir",
    "asset_type": "character_directions",
    "params": {"resolution": "64x64"},
    "expected_count": 2
  }
]
```

**Failure example**

No tool-specific failure payload. Unexpected runtime errors surface as MCP exception text.

## Generation Error Codes

These `errors[].code` values are used in generation-tool failure envelopes:

| Code | Stage | Meaning |
|---|---|---|
| `INVALID_INPUT` | `input_validate` | Input is invalid (for example missing reference image). |
| `PLAN_INVALID` | `plan` | Planner output was invalid or empty. |
| `PROVIDER_ERROR` | `generate` | Provider call failed. |
| `EXTRACTION_MISMATCH` | `extract` | Extracted frame count/shape mismatch. |
| `QA_FAILED` | `deterministic_gate` | Deterministic QA hard gate failed. |
| `VALIDATOR_FAILED` | `final_validator_agent` | Final validator failed or retry budget exhausted. |
| `EXPORT_FAILED` | `export` | Asset export failed. |
| `TIMEOUT` | any | Workflow timed out. |
| `INTERNAL_ERROR` | any | Internal execution failure. |
