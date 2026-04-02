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

Intermediate artifacts are saved for debugging:

- **Animation flows** (single-frame): `frame_NN_raw.png` (raw Gemini output per frame), `frame_NN_prompt.json` (rendered JSON prompt per frame)
- **Canvas-based flows** (tile, object, effect): `canvas_input.png`, `raw.png` / `sheet_raw.png`, `sheet_cleaned.png`
- `sheet.png` — the final assembled sprite sheet

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

Generate animation frames for an existing character sprite using single-frame sequential generation.

Each `--frame-poses` entry triggers one Gemini call. The model receives the reference sprite + the previous frame as context, producing one new frame per call. Total frames = number of poses + 1 (the reference).

```bash
pixel-magic animate --name <name> --animation-description "<desc>" --frame-poses "<p1>" "<p2>" ... [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. The command expects a source sprite in `output/<name>/views/` unless `--reference` is provided. |
| `--animation-description "<desc>"` | Natural-language description of the animation (e.g. "a walk cycle — legs alternating, arms swinging"). |
| `--frame-poses "<p1>" "<p2>" ...` | Per-frame pose descriptions. Each entry generates one frame via a separate Gemini call. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--description "<desc>"` | *(none)* | Extra character description to improve consistency. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--direction <dir>` | `south_east` | Which extracted character view to animate. Compass names like `north_east`, `south`, and `west` are canonical. |
| `--reference <path>` | *(auto-detect)* | Use a custom reference image instead of the generated view. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue}` | from `.env` | Override the chromakey used during cleanup. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |

### Examples

Looping walk cycle (8 poses = 9 total frames):

```bash
pixel-magic animate \
  --name knight \
  --animation-description "a walk cycle — legs alternating, arms swinging naturally" \
  --frame-poses \
    "left foot forward, right arm swinging forward" \
    "weight drops onto front foot, knee bends" \
    "legs cross at center, body at highest point" \
    "right leg swings forward reaching ahead" \
    "right foot strikes ground, left arm forward" \
    "weight drops onto right foot" \
    "legs cross at center again" \
    "left leg swings forward, returning to start"
```

One-shot attack with per-frame poses:

```bash
pixel-magic animate \
  --name knight \
  --animation-description "a spear thrust attack" \
  --no-loop \
  --frame-poses \
    "body coils back, spear drawn behind shoulder" \
    "explosive forward lunge, spear thrusts forward" \
    "full extension past target, momentum carries forward" \
    "body settles back, spear retracting"
```

### Output

```text
output/<name>/animations/<sanitized-description>/
├── frame_01.png            # Reference frame (cleaned)
├── frame_02.png            # Generated frame 2 (cleaned)
├── frame_02_raw.png        # Raw Gemini output for frame 2
├── frame_02_prompt.json    # JSON prompt sent for frame 2
├── frame_03.png
├── frame_03_raw.png
├── frame_03_prompt.json
├── ...
└── sheet.png               # Horizontal sprite sheet of all cleaned frames
```

## `pixel-magic animate-object`

Generate animation frames for an existing object sprite using single-frame sequential generation.

Same pipeline as `animate` — each `--frame-poses` entry triggers one Gemini call with reference + previous frame context.

```bash
pixel-magic animate-object --set <set-name> --name <object-name> --animation-description "<desc>" --frame-poses "<p1>" "<p2>" ... [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--set <set-name>` | Object set name, for example `forest`, `dungeon`, or `camp`. |
| `--name <object-name>` | Object name inside that set, for example `oak_tree_1` or `torch_1`. |
| `--animation-description "<desc>"` | Natural-language description of the animation (e.g. "gentle swaying in wind"). |
| `--frame-poses "<p1>" "<p2>" ...` | Per-frame pose descriptions. Each entry generates one frame. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--description "<desc>"` | *(none)* | Extra object description for consistency. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--reference <path>` | *(auto-detect)* | Override the source object sprite path. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to protect green and blue object colors. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--sizes "<list>"` | *(none)* | Resize frames to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized frames. |

### Examples

Looping torch flicker:

```bash
pixel-magic animate-object --set dungeon --name torch \
  --animation-description "a flickering animation — flame pulses and shifts shape" \
  --frame-poses "flame leans left, tip narrows" "flame stands tall, widens at base" "flame leans right, sparks fly" "flame shrinks briefly, embers glow"
```

One-shot chest opening:

```bash
pixel-magic animate-object --set dungeon --name chest \
  --animation-description "the chest lid swings open revealing the interior" \
  --no-loop \
  --frame-poses "lid begins to lift, light glows from crack" "lid halfway open, golden glow spills out" "lid fully open, treasures visible inside" "lid settles, glow dims slightly"
```

### Output

```text
output/objects/<set-name>/animations/<object-name>/<sanitized-description>/
├── frame_01.png
├── frame_02.png
├── frame_02_raw.png
├── frame_02_prompt.json
├── ...
├── sheet.png
├── 32x32/
│   ├── frame_01.png
│   └── sheet.png
└── 64x64/
    ├── frame_01.png
    └── sheet.png
```

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
