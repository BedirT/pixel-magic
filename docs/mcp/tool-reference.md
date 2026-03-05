---
title: MCP Tool Reference
---

# MCP Tool Reference

All tools return JSON strings. Generation tools return a **workflow job envelope** (see [Common Response Shape](#common-response-shape) below). Pipeline and utility tools return simpler, tool-specific JSON.

---

## Common Response Shape

All generation tools (`generate_character`, `generate_tileset`, `generate_items`, `generate_effect`, `generate_ui_elements`, `generate_custom`, `extend_character_animation`) return this envelope:

```json
{
  "status": "success",
  "job_id": "7f3a21b4",
  "stage": "finalize",
  "plan": {
    "asset_type": "character",
    "animations": { "idle": { "frame_count": 4 }, "walk": { "frame_count": 6 } },
    "directions": ["south", "east", "north", "west"]
  },
  "deterministic_gate": {
    "passed": true,
    "checks": [
      { "name": "alpha_compliance", "passed": true },
      { "name": "frame_count_match", "passed": true },
      { "name": "palette_size", "passed": true }
    ]
  },
  "final_validation": {
    "decision": "pass",
    "notes": "Frames are consistent, palette is compliant"
  },
  "artifacts": {
    "output_dir": "output/knight",
    "atlas_path": "output/knight/atlas.png",
    "metadata_path": "output/knight/metadata.json",
    "frame_paths": {
      "idle_south": ["output/knight/idle_south_000.png", "output/knight/idle_south_001.png"],
      "walk_south": ["output/knight/walk_south_000.png", "..."]
    },
    "total_frames": 32
  },
  "output_paths": ["output/knight/idle_south_000.png", "..."],
  "output_dir": "output/knight",
  "trace": [
    { "stage": "input_validate", "duration_ms": 2 },
    { "stage": "route", "duration_ms": 340 },
    { "stage": "plan", "duration_ms": 890 }
  ],
  "metrics": {
    "generation_calls": 4,
    "retry_count": 0,
    "duration_ms": 12400
  }
}
```

**Key fields:**

| Field | Type | Description |
|---|---|---|
| `status` | string | `"success"` or `"error"` |
| `job_id` | string | Unique identifier for this generation run |
| `output_paths` | array | Flat list of all output PNG file paths (most useful for downstream pipelines) |
| `output_dir` | string | Directory containing all outputs |
| `artifacts.atlas_path` | string | Single PNG atlas combining all frames |
| `artifacts.metadata_path` | string | JSON file with frame dims, animation names, durations |
| `artifacts.frame_paths` | object | Frame paths grouped by animation+direction key |
| `deterministic_gate.passed` | boolean | Whether the QA gate passed |
| `final_validation.decision` | string | `"pass"`, `"retry"`, or `"fail"` |

**On error**, the response looks like:

```json
{
  "status": "error",
  "job_id": "7f3a21b4",
  "stage": "deterministic_gate",
  "errors": [
    {
      "code": "QA_FAILED",
      "stage": "deterministic_gate",
      "details": { "failed_checks": ["alpha_compliance"] }
    }
  ]
}
```

See [Error Codes](#error-codes) at the bottom of this page.

---

## Generation Tools

### `generate_character`

Generates a complete pixel art character sprite set with all directional views and animations. By default produces idle and walk animations in 4 directions.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `character_description` | string | **required** | Detailed visual description of the character |
| `name` | string | `"character"` | Name used for the output directory and file prefix |
| `style` | string | `"16-bit SNES RPG style"` | Art style description passed to the image model |
| `direction_mode` | integer | `4` | `4` generates south/east/north/west (with flips); `8` adds SE, NE diagonals |
| `animations` | object | idle + walk | Map of animation name to preset name or definition (see below) |
| `resolution` | string | `"64x64"` | Per-frame resolution as `"WxH"` |
| `max_colors` | integer | `16` | Maximum palette colors per frame |
| `palette_name` | string | `null` | Name of a `.hex` palette file (see `list_palettes`). Enforces strict palette compliance |
| `palette_hint` | string | `""` | Color hint text for the model (e.g., `"warm earth tones, avoid blue"`) |

**The `animations` parameter** accepts a map where each key is an animation name and the value is either:

- A preset name string (e.g., `"idle"`, `"walk"`, `"attack"`, `"run"`, `"hurt"`, `"death"`) — use `list_animations` to see all presets
- An inline definition object:

```json
{
  "fishing": {
    "frame_count": 6,
    "description": "Character casts a fishing rod, waits, then reels in",
    "duration_ms": 150,
    "is_looping": true
  }
}
```

**Example — minimal:**

```json
{
  "character_description": "A young female knight in silver plate armor with a red cape",
  "name": "knight"
}
```

**Example — full control:**

```json
{
  "character_description": "A cloaked dark mage with glowing purple runes on his robes, skeletal hands, staff topped with a skull",
  "name": "dark_mage",
  "style": "16-bit SNES RPG style, dark fantasy",
  "direction_mode": 4,
  "resolution": "64x64",
  "max_colors": 16,
  "palette_name": "twilight_16",
  "palette_hint": "dark purples, bone whites, sickly green accents",
  "animations": {
    "idle": "idle",
    "walk": "walk",
    "cast": {
      "frame_count": 8,
      "description": "Mage raises staff, runes flash, energy ball launches forward",
      "duration_ms": 100,
      "is_looping": false
    }
  }
}
```

**Output:** PNG files per frame in `output/<name>/`, plus `atlas.png` and `metadata.json`.

---

### `extend_character_animation`

Adds a new animation to an existing character by providing a reference sprite image. The new animation is generated to visually match the reference character design.

Use this when you already have a character sprite set and want to add more animations (e.g., you generated idle+walk and now want a fishing or swimming animation).

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `character_name` | string | **required** | Name identifying the character (for metadata and output naming) |
| `animation_name` | string | **required** | Name of the new animation (e.g., `"fishing"`, `"swim"`, `"jump"`) |
| `reference_image_path` | string | **required** | Absolute or relative path to an existing sprite image of this character |
| `frame_count` | integer | `4` | Number of frames for the new animation |
| `description` | string | `""` | Motion description for the new animation |
| `duration_ms` | integer | `100` | Duration per frame in milliseconds |
| `is_looping` | boolean | `true` | Whether the animation loops |
| `direction_mode` | integer | `4` | `4` or `8` directional generation |
| `style` | string | `"16-bit SNES RPG style"` | Art style (should match the original character's style) |
| `resolution` | string | `"64x64"` | Per-frame resolution (should match the original character) |
| `max_colors` | integer | `16` | Max palette colors |
| `palette_name` | string | `null` | Named palette (should match the original if one was used) |

**Important:** `reference_image_path` must point to an existing readable file. The pipeline validates this at input stage and fails immediately if the file is missing.

**Example:**

```json
{
  "character_name": "knight",
  "animation_name": "fishing",
  "reference_image_path": "/path/to/output/knight/idle_south_000.png",
  "frame_count": 6,
  "description": "Knight holds a fishing rod, casts the line, waits, then pulls back",
  "duration_ms": 150,
  "is_looping": true,
  "direction_mode": 4,
  "style": "16-bit SNES RPG style",
  "resolution": "64x64",
  "max_colors": 16
}
```

**Output:** New animation frames in `output/<character_name>_<animation_name>/`.

---

### `generate_tileset`

Generates isometric tile sprites for a set of tile types in a given biome. Each tile type becomes a separate PNG output.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `biome` | string | **required** | Environment type (e.g., `"forest"`, `"desert"`, `"snow"`, `"dungeon"`, `"underwater"`) |
| `tile_types` | array of strings | **required** | List of tile variants to generate |
| `name` | string | `"tileset"` | Output name prefix |
| `tile_width` | integer | `64` | Tile width in pixels |
| `tile_height` | integer | `32` | Tile height in pixels (32 gives standard 2:1 isometric ratio) |
| `style` | string | `"16-bit isometric RPG style"` | Art style |
| `max_colors` | integer | `16` | Max palette colors |
| `palette_name` | string | `null` | Named palette for consistency across tiles |

**Example — forest biome:**

```json
{
  "biome": "forest",
  "tile_types": ["grass", "dirt path", "stone", "water", "flower patch", "tree base"],
  "name": "forest",
  "tile_width": 64,
  "tile_height": 32,
  "style": "16-bit isometric RPG, lush green tones",
  "max_colors": 16
}
```

**Example — dungeon biome with shared palette:**

```json
{
  "biome": "dungeon",
  "tile_types": ["stone floor", "cracked stone floor", "stone wall", "dirt", "lava pool"],
  "name": "dungeon",
  "tile_width": 64,
  "tile_height": 32,
  "style": "dark dungeon crawler, gritty",
  "max_colors": 12,
  "palette_name": "dungeon_12"
}
```

**Tip:** Use a `palette_name` when generating multiple tilesets that will appear in the same scene. This ensures consistent colors across all tile types.

---

### `generate_items`

Generates a batch of item icon sprites in one call. Each item in the list becomes a separate PNG.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_descriptions` | array of strings | **required** | Descriptions of each item to generate |
| `resolution` | string | `"32x32"` | Icon resolution (items typically use smaller sizes than characters) |
| `style` | string | `"16-bit SNES RPG style"` | Art style |
| `max_colors` | integer | `16` | Max palette colors per item |
| `view` | string | `"front-facing icon"` | Viewing angle (e.g., `"top-down"`, `"isometric"`, `"side view"`) |
| `palette_name` | string | `null` | Named palette |

**Example — RPG item batch:**

```json
{
  "item_descriptions": [
    "rusty iron sword with a leather-wrapped handle",
    "small red glass health potion with a cork stopper",
    "ancient skeleton key with ornate handle",
    "wooden shield with a painted red cross",
    "silver ring with a glowing blue gemstone"
  ],
  "resolution": "32x32",
  "style": "16-bit SNES RPG style",
  "max_colors": 16
}
```

**Example — top-down view for inventory grid:**

```json
{
  "item_descriptions": ["loaf of bread", "raw fish", "apple", "cheese wedge"],
  "resolution": "16x16",
  "style": "8-bit NES style",
  "max_colors": 8,
  "view": "top-down icon"
}
```

**Output:** One PNG per item in `output/items/`. The `output_paths` array in the response is ordered to match the `item_descriptions` input order.

---

### `generate_effect`

Generates an animated pixel art visual effect as a sequence of frames.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `effect_description` | string | **required** | Description of the visual effect |
| `frame_count` | integer | `6` | Number of animation frames |
| `resolution` | string | `"64x64"` | Frame resolution |
| `style` | string | `"16-bit pixel art"` | Art style |
| `max_colors` | integer | `12` | Max palette colors (effects often need fewer colors for clarity) |
| `color_emphasis` | string | `""` | Comma-separated dominant color guidance (e.g., `"fire: orange, red, yellow"`) |

**Example — explosion:**

```json
{
  "effect_description": "Medium explosion with a bright flash, expanding fireball, and smoke dissipating",
  "frame_count": 8,
  "resolution": "64x64",
  "style": "16-bit pixel art",
  "max_colors": 12,
  "color_emphasis": "orange, red, yellow, black smoke, white flash center"
}
```

**Example — magic heal:**

```json
{
  "effect_description": "Holy healing effect: soft golden light rays emanating upward with sparkle particles",
  "frame_count": 6,
  "resolution": "48x64",
  "style": "16-bit SNES RPG style",
  "max_colors": 8,
  "color_emphasis": "gold, white, pale yellow"
}
```

**Example — ice projectile:**

```json
{
  "effect_description": "Ice shard projectile flying right with a trailing frost mist",
  "frame_count": 4,
  "resolution": "32x32",
  "style": "16-bit pixel art",
  "max_colors": 10
}
```

---

### `generate_ui_elements`

Generates a batch of pixel art UI element sprites. Useful for health bars, buttons, dialog boxes, HUD elements, and other interface components.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `element_descriptions` | array of strings | **required** | Descriptions of each UI element to generate |
| `resolution` | string | `"64x64"` | Element resolution |
| `style` | string | `"16-bit RPG UI style"` | Art style |
| `max_colors` | integer | `8` | Max palette colors (UI elements typically use fewer colors) |

**Example — RPG HUD elements:**

```json
{
  "element_descriptions": [
    "heart icon for health display",
    "empty heart outline",
    "stamina bar segment (filled)",
    "stamina bar segment (empty)",
    "small sword icon for attack stat",
    "small shield icon for defense stat"
  ],
  "resolution": "16x16",
  "style": "16-bit RPG HUD style, clean and readable",
  "max_colors": 6
}
```

**Example — dialog box components:**

```json
{
  "element_descriptions": [
    "dialog box top-left corner piece",
    "dialog box top edge tile",
    "dialog box top-right corner piece",
    "dialog box left edge tile",
    "dialog box background fill",
    "dialog box right edge tile"
  ],
  "resolution": "16x16",
  "style": "classic JRPG dialog box, dark blue border with gold trim",
  "max_colors": 8
}
```

---

### `generate_custom`

Generates pixel art from a completely freeform prompt. Use this for anything that doesn't fit the structured generation tools — backgrounds, logos, map icons, decorative elements, etc.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | **required** | Your full generation prompt |
| `frame_count` | integer | `1` | Number of frames to extract from the generated image |
| `layout` | string | `"horizontal_strip"` | How frames are arranged: `horizontal_strip`, `vertical_strip`, `grid`, `auto_detect` |

**Example — single background:**

```json
{
  "prompt": "16-bit pixel art forest clearing background, tall pine trees on sides, moonlit clearing in center, stars visible, suitable for RPG battle scene, 256x144 resolution",
  "frame_count": 1,
  "layout": "horizontal_strip"
}
```

**Example — animated coin:**

```json
{
  "prompt": "Gold coin rotation animation, 4 frames showing front face, 3/4 view, edge-on, 3/4 view other side, 16x16 pixel art, classic RPG style, horizontal strip layout",
  "frame_count": 4,
  "layout": "horizontal_strip"
}
```

**Note:** The model generates a single composite image and the pipeline extracts `frame_count` frames from it. For multi-frame results, describe the layout clearly in your prompt (e.g., "horizontal strip of 4 frames").

---

## Pipeline Tools

### `convert_image`

Converts any image through the pixel art post-processing pipeline: grid inference, palette quantization, and cleanup. Use this to turn photographs, high-res art, or AI-generated images into clean pixel art sprites.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image_path` | string | **required** | Path to the input image |
| `target_resolution` | string | `null` | Optional output resolution as `"WxH"`. If omitted, resolution is inferred from the image |
| `palette_name` | string | `null` | Named palette to quantize to |
| `max_colors` | integer | `16` | Colors for adaptive palette (used when no `palette_name` is given) |
| `alpha_policy` | string | `"binary"` | `"binary"` — pixels are fully opaque or fully transparent; `"keep8bit"` — preserve partial transparency |
| `remove_bg` | boolean | `false` | Remove solid-color background before processing |

**Example:**

```json
{
  "image_path": "/path/to/character_concept.png",
  "target_resolution": "64x64",
  "max_colors": 16,
  "alpha_policy": "binary",
  "remove_bg": true
}
```

**Response:**

```json
{
  "status": "success",
  "output_path": "output/converted/character_concept_pixel.png",
  "grid": { "macro_size": 2, "confidence": 0.94 },
  "palette_size": 14,
  "resolution": "64x64"
}
```

---

### `process_sprite_sheet`

Takes an existing sprite sheet (multiple frames in one image) and runs it through frame extraction, palette quantization, cleanup, and QA. Useful for cleaning up or re-paletting existing sprite sheets.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image_path` | string | **required** | Path to the sprite sheet image |
| `frame_count` | integer | `null` | Expected number of frames. Helps guide extraction when layout is ambiguous |
| `layout` | string | `"auto_detect"` | Frame arrangement: `auto_detect`, `horizontal_strip`, `vertical_strip`, `grid` |
| `palette_name` | string | `null` | Named palette to quantize all frames to |
| `max_colors` | integer | `16` | Colors for adaptive palette |
| `name` | string | `"sheet"` | Output name prefix for exported frames |

**Example:**

```json
{
  "image_path": "/path/to/walk_animation.png",
  "frame_count": 8,
  "layout": "horizontal_strip",
  "max_colors": 16,
  "name": "character_walk"
}
```

**Response:**

```json
{
  "status": "success",
  "frame_count": 8,
  "output_paths": [
    "output/character_walk/character_walk_000.png",
    "output/character_walk/character_walk_001.png"
  ],
  "qa": {
    "passed": true,
    "checks": [
      { "name": "alpha_compliance", "passed": true },
      { "name": "palette_size", "passed": true, "value": 14 }
    ]
  }
}
```

---

### `extract_frames_tool`

Extracts individual frames from a composite image without any post-processing. Useful when you just need to split a sprite sheet into frame files.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image_path` | string | **required** | Path to the composite image |
| `frame_count` | integer | `null` | Expected frame count (helps guide extraction) |
| `layout` | string | `"auto_detect"` | Frame arrangement: `auto_detect`, `horizontal_strip`, `vertical_strip`, `grid` |

**Example:**

```json
{
  "image_path": "/path/to/effects_sheet.png",
  "frame_count": 6,
  "layout": "horizontal_strip"
}
```

**Response:**

```json
{
  "status": "success",
  "frame_count": 6,
  "output_paths": [
    "output/extracted/frame_000.png",
    "output/extracted/frame_001.png",
    "output/extracted/frame_002.png",
    "output/extracted/frame_003.png",
    "output/extracted/frame_004.png",
    "output/extracted/frame_005.png"
  ]
}
```

---

## QA Tool

### `run_qa_check`

Runs QA checks on one or more sprite images. Checks alpha compliance, palette size, and frame consistency. Optionally runs AI vision QA for deeper quality assessment.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image_paths` | array of strings | **required** | Paths to the images to check |
| `palette_name` | string | `null` | Named palette to check compliance against |
| `alpha_policy` | string | `"binary"` | `"binary"` or `"keep8bit"` |
| `run_vision` | boolean | `false` | Run AI vision QA in addition to deterministic checks. Costs API credits |

**Example:**

```json
{
  "image_paths": [
    "output/knight/idle_south_000.png",
    "output/knight/idle_south_001.png",
    "output/knight/idle_south_002.png"
  ],
  "palette_name": "default_16",
  "alpha_policy": "binary",
  "run_vision": false
}
```

**Response:**

```json
{
  "passed": true,
  "checks": [
    { "name": "alpha_compliance", "passed": true },
    { "name": "palette_compliance", "passed": true, "palette": "default_16" },
    { "name": "palette_size", "passed": true, "value": 12, "max": 16 },
    { "name": "frame_consistency", "passed": true }
  ]
}
```

---

## Utility Tools

### `list_palettes`

Lists all available named palettes with a color preview.

**Parameters:** None

**Example response:**

```json
[
  {
    "name": "default_16",
    "size": 16,
    "colors": ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#e94560", "#ff6b6b", "#ffd93d", "#6bcb77"],
    "path": "palettes/default_16.hex"
  },
  {
    "name": "gameboy",
    "size": 4,
    "colors": ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"],
    "path": "palettes/gameboy.hex"
  }
]
```

Use the `name` field value as the `palette_name` parameter in generation tools.

---

### `list_animations`

Lists all built-in animation presets that can be used as shorthand in the `generate_character` `animations` parameter.

**Parameters:** None

**Example response:**

```json
{
  "idle": {
    "frame_count": 4,
    "description": "Gentle breathing idle stance",
    "duration_ms": 150,
    "is_looping": true
  },
  "walk": {
    "frame_count": 6,
    "description": "Standard walking cycle",
    "duration_ms": 100,
    "is_looping": true
  },
  "attack": {
    "frame_count": 6,
    "description": "Basic melee attack swing",
    "duration_ms": 80,
    "is_looping": false
  },
  "hurt": {
    "frame_count": 3,
    "description": "Damage recoil reaction",
    "duration_ms": 120,
    "is_looping": false
  },
  "death": {
    "frame_count": 6,
    "description": "Collapse and fade",
    "duration_ms": 120,
    "is_looping": false
  }
}
```

---

### `list_prompt_templates`

Lists all internal prompt templates used by the pipeline, along with their parameters.

**Parameters:** None

**Response:** Array of template objects with `name`, `description`, `parameters`, and `reference_strategy` fields. Primarily useful for debugging and understanding how prompts are constructed.

---

### `set_provider`

Switches the active AI image provider at runtime without restarting the server.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `provider` | string | yes | `"gemini"` or `"openai"` |

**Example:**

```json
{ "provider": "openai" }
```

**Response:**

```json
{ "status": "success", "provider": "openai" }
```

This recreates the provider adapter, agent runtime, and workflow executor in-process. All subsequent generation calls use the new provider until switched again or the server restarts.

---

### `set_style_defaults`

Sets default style parameters applied to all future generation calls in this session. Useful to avoid repeating the same parameters on every call.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `direction_mode` | integer | — | `4` or `8` — sets the default for character generation |
| `resolution` | string | — | Default resolution (e.g., `"64x64"`) |
| `palette_size` | integer | — | Default max palette colors |
| `alpha_policy` | string | — | `"binary"` or `"keep8bit"` |

All parameters are optional. Only the ones you provide are updated.

**Example — set project-wide defaults before a session:**

```json
{
  "direction_mode": 4,
  "resolution": "64x64",
  "palette_size": 16,
  "alpha_policy": "binary"
}
```

**Response:**

```json
{
  "status": "success",
  "direction_mode": 4,
  "resolution": "64x64",
  "palette_size": 16,
  "alpha_policy": "binary"
}
```

---

## Evaluation Tools

### `run_evaluation`

Runs the built-in offline evaluation suite. Generates pixel art for each test case and scores the results using an LLM-as-a-Judge. Results are saved to `output/eval/<variant_label>/results.json`.

This is not a production gate — it's for regression testing and provider comparison.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `variant_label` | string | `"default"` | Label for this run (e.g., `"gemini_v1"`, `"openai_baseline"`) |
| `case_names` | array of strings | `null` | Run specific cases by name. Runs all cases if omitted |
| `repeats` | integer | `1` | Repeat each case N times for statistical significance |
| `mode` | string | `"direct"` | `"direct"` uses PromptBuilder+provider (fast); `"agent"` runs the full workflow pipeline |

**Example — baseline run:**

```json
{
  "variant_label": "gemini_baseline",
  "repeats": 1,
  "mode": "direct"
}
```

**Example — targeted agent-mode evaluation:**

```json
{
  "variant_label": "openai_agent_v2",
  "case_names": ["character_knight", "tileset_forest", "items_weapons"],
  "repeats": 3,
  "mode": "agent"
}
```

**Response:**

```json
{
  "status": "success",
  "variant": "gemini_baseline",
  "total_cases": 12,
  "errors": 0,
  "overall_mean": 0.847,
  "overall_pass_rate": 0.917,
  "dimensions": {
    "pixel_art_quality": 0.88,
    "style_consistency": 0.83,
    "animation_smoothness": 0.82,
    "palette_compliance": 0.96
  },
  "results_path": "output/eval/gemini_baseline/results.json"
}
```

---

### `compare_evaluations`

Compares two or more evaluation runs and generates a statistical comparison report in Markdown.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `run_paths` | array of strings | yes | Paths to `results.json` files from previous `run_evaluation` calls |

**Example:**

```json
{
  "run_paths": [
    "output/eval/gemini_baseline/results.json",
    "output/eval/openai_baseline/results.json"
  ]
}
```

**Response:** A Markdown report with per-dimension score tables, statistical significance notes, and a winner declaration per dimension. The report is also saved to `output/eval/comparison/`.

---

### `list_eval_cases`

Lists all built-in test cases for the evaluation suite.

**Parameters:** None

**Response:** Array of test case objects, each with `name`, `asset_type`, `description`, and evaluation rubric parameters.

---

## Error Codes

When a generation fails, the `errors` array in the response contains one or more objects with these fields:

| Field | Description |
|---|---|
| `code` | Machine-readable error code (see table below) |
| `stage` | Workflow stage where the failure occurred |
| `details` | Structured, stage-specific context about the failure |

| Code | Stage | Meaning |
|---|---|---|
| `INVALID_INPUT` | `input_validate` | A required parameter is missing or invalid (e.g., `reference_image_path` doesn't exist) |
| `PLAN_INVALID` | `plan` | The agent produced a malformed generation plan |
| `PROVIDER_ERROR` | `generate` | The AI provider returned an error (API key issue, quota exceeded, transient failure) |
| `EXTRACTION_MISMATCH` | `extract` | Frame extraction produced a different count than expected |
| `QA_FAILED` | `deterministic_gate` | Frames failed alpha, palette, or frame count checks after the retry budget was spent |
| `VALIDATOR_FAILED` | `final_validator_agent` | The validator agent returned `fail` or `retry` after the retry budget was exhausted |
| `EXPORT_FAILED` | `export` | File write failed (permissions, disk space) |
| `TIMEOUT` | any | Pipeline exceeded the allowed duration |
| `INTERNAL_ERROR` | any | Unexpected internal failure |

See [Troubleshooting](../troubleshooting/common-issues.md) for solutions to the most common errors.
