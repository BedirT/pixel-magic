# CLI Reference

`pixel-magic` is a command-line tool for generating pixel art characters, animations, tiles, objects, and simple VFX with Gemini.

## Installation

Install project dependencies:

```bash
uv sync
```

Run commands with the installed entry point:

```bash
pixel-magic <command> [options]
```

## Output Conventions

By default, commands write into `output/`.

- Character generation writes to `output/<name>/`
- Character animation writes to `output/<name>/animations/<animation>/`
- Object generation writes to `output/objects/<set-name>/`
- Object animation writes to `output/objects/<set-name>/animations/<object-name>/<animation>/`
- Tile generation writes to `output/tiles/<set-name>/`
- Effect generation writes to `output/effects/<effect-name>/` or `output/effects/<preset>/<effect-name>/`

Most canvas-based flows save intermediate artifacts for debugging:

- `canvas_input.png` — the guide canvas sent to Gemini (single-batch)
- `raw.png` or `sheet_raw.png` — the first Gemini output (single-batch)
- `sheet_cleaned.png` — the cleanup-pass output when the pipeline removes guides
- `sheet.png` — the final assembled output after local cleanup
- `batch_<n>_canvas.png` / `batch_<n>_sheet_raw.png` / `batch_<n>_sheet_cleaned.png` — per-batch artifacts for multi-batch animations (>6 frames)

## `pixel-magic generate`

Generate a multi-view isometric character sheet.

```bash
pixel-magic generate --name <name> --description "<description>" [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. Used as the output folder under the output directory. |
| `--description "<desc>"` | Natural-language character description. Include silhouette, clothing, weapons, colors, and notable details. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--directions {4,8}` | `4` | Direction set. `4` produces 2 canonical views. `8` produces 5 canonical views. |
| `--tiles {1,4,9}` | `1` | Platform footprint. Larger values give the model more room for large creatures or mounts. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--resolution <WxH>` | `64x64` | Prompt hint for per-view resolution. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to the prompt. |
| `--palette-hint "<hint>"` | *(none)* | Extra palette guidance. |
| `--sizes "<list>"` | *(none)* | Resize extracted sprites to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized sprites. |
| `--chromakey {green,blue}` | from `.env` | Override the default chromakey used for background removal. |
| `--no-platform` | platform mode enabled | Skip platform-guided generation and use a text-only prompt instead. |
| `--char-ratio <float>` | `1.2` | Character height estimate relative to platform width. Used only in platform mode. |

### Examples

Basic 4-direction character:

```bash
pixel-magic generate \
  --name knight \
  --description "A medieval knight with silver armor, blue cape, and a longsword"
```

Large 8-direction creature:

```bash
pixel-magic generate \
  --name fire-mage \
  --description "A fire mage in red robes with a glowing staff and flame effects" \
  --directions 8 \
  --tiles 4
```

Text-only generation with custom palette guidance:

```bash
pixel-magic generate \
  --name cyberpunk-hacker \
  --description "A cyberpunk hacker with neon visor, black trenchcoat, and holographic keyboard" \
  --style "GBA-era pixel art" \
  --max-colors 32 \
  --palette-hint "neon green, dark purple, black, electric blue" \
  --no-platform
```

### Output

```text
output/<name>/
├── raw.png                 # First Gemini output
├── sheet.png               # Background removed
├── canvas_input.png        # Platform-guided input canvas (platform mode only)
├── sheet_cleaned.png       # Guide cleanup output (platform mode only)
├── views/
│   ├── south_west.png
│   └── north_east.png
└── views_raw/
    ├── south_west.png
    └── north_east.png
```

If you pass `--sizes`, resized variants are written under `views/<size>x<size>/`.

## `pixel-magic animate`

Generate animation frames for an existing character sprite.

```bash
pixel-magic animate --name <name> --animation-description "<desc>" [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. The command expects a source sprite in `output/<name>/views/` unless `--reference` is provided. |
| `--animation-description "<desc>"` | Natural-language description of the animation (e.g. "a walk cycle — legs alternating, arms swinging"). |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--description "<desc>"` | *(none)* | Extra character description to improve consistency. |
| `--frames <n>` | `6` | Total number of frames in the cycle. |
| `--frame-poses "<p1>" "<p2>" ...` | *(none)* | Optional per-frame pose descriptions for fillable slots. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--direction <dir>` | `south_east` | Which extracted character view to animate. Compass names like `north_east`, `south`, and `west` are canonical. |
| `--reference <path>` | *(auto-detect)* | Use a custom reference image instead of the generated view. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue}` | from `.env` | Override the chromakey used during cleanup. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--platform` / `--no-platform` | `--no-platform` | Add an isometric platform for perspective grounding. |
| `--tiles {1,4,9}` | `1` | Platform size. Values above `1` imply `--platform`. |
| `--padding <float>` | `0.2` | Slot padding fraction for pose overflow room. `0.2` = 20% extra per side, giving dynamic poses room to extend beyond the standing reference. |

### Examples

Looping walk cycle:

```bash
pixel-magic animate \
  --name samurai \
  --animation-description "a walk cycle — legs alternating, arms swinging naturally" \
  --frames 6 --platform
```

One-shot attack with per-frame poses:

```bash
pixel-magic animate \
  --name samurai \
  --animation-description "a sword attack — wind up, strike, follow through" \
  --frames 4 --tiles 4 --no-loop \
  --frame-poses "arm pulls back" "sword swings forward" "full extension"
```

Spell cast with a custom reference:

```bash
pixel-magic animate \
  --name samurai \
  --animation-description "a spell casting animation — hands raise, energy channels, spell releases" \
  --frames 4 \
  --direction south_east \
  --reference path/to/reference.png \
  --no-loop
```

### Output

```text
output/<name>/animations/<sanitized-description>/
├── canvas_input.png        # Single-batch canvas sent to Gemini
├── sheet_raw.png           # Single-batch raw Gemini output
├── sheet_cleaned.png       # Present when platform cleanup runs
├── batch_0_canvas.png      # Multi-batch (>6 frames): per-batch canvas
├── batch_0_sheet_raw.png   # Multi-batch: per-batch raw output
├── batch_0_sheet_cleaned.png  # Multi-batch: per-batch cleaned output
├── sheet.png
├── frame_01.png
├── frame_02.png
└── ...
```

Single-batch runs (≤6 frames) write `canvas_input.png` and `sheet_raw.png`. Multi-batch runs (>6 frames) write `batch_<n>_canvas.png`, `batch_<n>_sheet_raw.png`, and optionally `batch_<n>_sheet_cleaned.png` for each batch.

## `pixel-magic animate-object`

Generate animation frames for an existing object sprite.

```bash
pixel-magic animate-object --set <set-name> --name <object-name> --animation-description "<desc>" [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--set <set-name>` | Object set name, for example `forest`, `dungeon`, or `camp`. |
| `--name <object-name>` | Object name inside that set, for example `oak_tree_1` or `torch_1`. |
| `--animation-description "<desc>"` | Natural-language description of the animation (e.g. "gentle swaying in wind"). |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--description "<desc>"` | *(none)* | Extra object description for consistency. |
| `--frames <n>` | `6` | Total number of frames in the cycle. |
| `--frame-poses "<p1>" "<p2>" ...` | *(none)* | Optional per-frame pose descriptions for fillable slots. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--reference <path>` | *(auto-detect)* | Override the source object sprite path. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to protect green and blue object colors. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--platform` / `--no-platform` | `--no-platform` | Add an isometric platform for grounding. |
| `--tiles {1,4,9}` | `1` | Platform size. Values above `1` imply `--platform`. |
| `--padding <float>` | `0.2` | Slot padding fraction for pose overflow room. `0.2` = 20% extra per side. |
| `--sizes "<list>"` | *(none)* | Resize frames to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized frames. |

### Examples

Looping torch flicker:

```bash
pixel-magic animate-object --set dungeon --name torch \
  --animation-description "a flickering animation — flame pulses and shifts shape" --frames 6
```

One-shot chest opening:

```bash
pixel-magic animate-object --set dungeon --name chest \
  --animation-description "the chest lid swings open revealing the interior" --frames 5 --no-loop
```

Looping campfire with resized outputs:

```bash
pixel-magic animate-object --set camp --name campfire \
  --animation-description "flames dance and smoke wisps rise" --frames 6 --sizes 32,64
```

### Output

```text
output/objects/<set-name>/animations/<object-name>/<sanitized-description>/
├── canvas_input.png        # Single-batch canvas sent to Gemini
├── sheet_raw.png           # Single-batch raw Gemini output
├── sheet_cleaned.png       # Present when platform cleanup runs
├── batch_0_canvas.png      # Multi-batch (>6 frames): per-batch canvas
├── batch_0_sheet_raw.png   # Multi-batch: per-batch raw output
├── batch_0_sheet_cleaned.png  # Multi-batch: per-batch cleaned output
├── sheet.png
├── frame_01.png
├── frame_02.png
├── ...
├── 32x32/
│   ├── frame_01.png
│   └── sheet.png
└── 64x64/
    ├── frame_01.png
    └── sheet.png
```

Single-batch runs (≤6 frames) write `canvas_input.png` and `sheet_raw.png`. Multi-batch runs (>6 frames) write `batch_<n>_canvas.png`, `batch_<n>_sheet_raw.png`, and optionally `batch_<n>_sheet_cleaned.png` for each batch.

## `pixel-magic effect`

Generate subjectless VFX animation sheets such as explosions, smoke, fire, and status effects.

```bash
pixel-magic effect --name <name> --animation-description "<desc>" [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Effect name. Used as the output folder under `effects/`. |
| `--animation-description "<desc>"` | Natural-language description of the effect animation. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--frames <n>` | `6` | Total number of frames. Must be at least `2`. Looping effects need at least `3`. |
| `--frame-poses "<p1>" "<p2>" ...` | *(none)* | Optional per-frame descriptions for each slot. |
| `--loop` / `--no-loop` | `--no-loop` | Looping or one-shot animation. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to preserve green and blue VFX colors. |
| `--sizes "<list>"` | *(none)* | Resize frames to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized frames. |

### Examples

One-shot explosion:

```bash
pixel-magic effect --name explosion \
  --animation-description "an explosion — bright flash expanding outward with fire and debris, then dissipating" \
  --frames 4 --no-loop
```

Looping fire with resized outputs:

```bash
pixel-magic effect --name fire \
  --animation-description "flames dancing and flickering, changing shape organically each frame" \
  --frames 4 --loop --sizes 32
```

Effect with per-frame descriptions:

```bash
pixel-magic effect --name magic_missile \
  --animation-description "a magic missile forming and launching" \
  --frames 4 --no-loop \
  --frame-poses "small spark forming" "energy coalescing into orb" "orb streaking forward with trail" "impact burst"
```

### Output

```text
output/effects/<name>/
├── canvas_input.png
├── sheet_raw.png
├── sheet_cleaned.png
├── sheet.png
├── frame_01.png
├── frame_02.png
├── ...
└── 32x32/
    ├── frame_01.png
    └── sheet.png
```

### Notes

- The effect flow uses an empty numbered canvas, then a cleanup pass to remove guide digits before local extraction.
- Looping effects are closed deterministically after cleanup so frame 1 and the final frame match exactly.

## `pixel-magic tile`

Generate isometric terrain tilesets using a labeled diamond canvas.

```bash
pixel-magic tile (--type <tile-type> | --theme <theme>) [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--type <tile-type>` | Generate variants of a single material, for example `grass`, `stone`, or `water`. |
| `--theme <theme>` | Generate a predefined set: `forest`, `dungeon`, `desert`, `winter`, or `custom`. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--variants <n>` | `4` | Number of variants for `--type` mode. Must be at least `1`. |
| `--types "<a,b,c>"` | *(none)* | Required when using `--theme custom`. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the recommended default for tiles. |
| `--depth <n>` | `4` | Side-face depth in pixels. Use `0` for flat diamonds. |
| `--sizes "<list>"` | *(none)* | Resize outputs to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized outputs. |

### Examples

Single material with variants:

```bash
pixel-magic tile --type grass --variants 4 --sizes 32,64
```

Predefined forest set:

```bash
pixel-magic tile --theme forest --depth 4
```

Custom set:

```bash
pixel-magic tile --theme custom --types "mud,brick,poison swamp"
```

Flat cobblestone:

```bash
pixel-magic tile --type cobblestone --variants 3 --depth 0
```

### Output

```text
output/tiles/<set-name>/
├── canvas_input.png
├── raw.png
├── sheet_cleaned.png
├── <tile>.png
├── 32x32/
│   └── <tile>.png
└── 64x64/
    └── <tile>.png
```

### Notes

- Tile labels stay on the input canvas intentionally to improve slot binding.
- Small custom sets avoid empty cells when possible. For example, 3 tiles use a `3x1` layout instead of `2x2`.
- Tiles use `_clean_tile()`, not the sprite outline path, so natural terrain edges are preserved.

## `pixel-magic object`

Generate isometric world objects and props using a labeled platform canvas.

```bash
pixel-magic object (--name <name> | --preset <preset>) [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Generate variants of a single object type such as `tree`, `rock`, or `chest`. |
| `--preset <preset>` | Generate a predefined object set: `forest`, `dungeon`, `village`, `camp`, `desert`, `winter`, or `custom`. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--variants <n>` | `4` | Number of variants for `--name` mode. Must be at least `1`. |
| `--names "<a,b,c>"` | *(none)* | Required when using `--preset custom`. |
| `--description "<desc>"` | *(none)* | Extra theme/style guidance. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to protect green and blue object colors. |
| `--depth <n>` | `8` | Platform side-face depth in pixels. |
| `--sizes "<list>"` | *(none)* | Resize outputs to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized outputs. |

### Examples

Single object type with variants:

```bash
pixel-magic object --name tree --variants 4
```

Predefined set:

```bash
pixel-magic object --preset forest
```

Custom set with extra theme guidance:

```bash
pixel-magic object \
  --preset custom \
  --names "chest,barrel,campfire" \
  --description "dark fantasy dungeon props"
```

### Output

```text
output/objects/<set-name>/
├── canvas_input.png
├── raw.png
├── sheet_cleaned.png
├── <object>.png
├── 32x32/
│   └── <object>.png
└── 64x64/
    └── <object>.png
```

### Presets

| Preset | Objects |
|---|---|
| `forest` | oak tree, pine tree, bush, rock, log, mushroom |
| `dungeon` | chest, barrel, crate, torch, skull pile, potion |
| `village` | well, crate, signpost, fence, hay bale, barrel |
| `camp` | campfire, tent, bedroll, cooking pot, backpack, log seat |
| `desert` | cactus, dead tree, sandstone rock, skull, pottery, palm tree |
| `winter` | snowy pine, ice rock, frozen bush, snowman, ice crystal, snow pile |

## Environment Configuration

Settings are loaded from a `.env` file in the project root. CLI flags override `.env`.

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | *(required)* | Google AI API key. |
| `PIXEL_MAGIC_GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Gemini image model. |
| `PIXEL_MAGIC_DIRECTION_MODE` | `4` | Default direction mode for character generation. |
| `PIXEL_MAGIC_MAX_COLORS` | `16` | Default max color limit. |
| `PIXEL_MAGIC_CHROMAKEY_COLOR` | `green` | Default chromakey for character generation and character animation. Non-character flows commonly default to pink unless explicitly overridden. |
| `PIXEL_MAGIC_OUTPUT_DIR` | `output` | Default output directory. |

Example:

```env
GOOGLE_API_KEY=AI...
PIXEL_MAGIC_CHROMAKEY_COLOR=green
```
