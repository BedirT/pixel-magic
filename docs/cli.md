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

- `canvas_input.png` — the guide canvas sent to Gemini
- `raw.png` or `sheet_raw.png` — the first Gemini output
- `sheet_cleaned.png` — the cleanup-pass output when the pipeline removes guides
- `sheet.png` — the final assembled output after local cleanup

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
│   ├── front_left.png
│   └── back_right.png
└── views_raw/
    ├── front_left.png
    └── back_right.png
```

If you pass `--sizes`, resized variants are written under `views/<size>x<size>/`.

## `pixel-magic animate`

Generate animation frames for an existing character sprite.

```bash
pixel-magic animate --name <name> --animation <type> [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. The command expects a source sprite in `output/<name>/views/` unless `--reference` is provided. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--animation <type>` | `walk` | Animation name. Common values: `walk`, `idle`, `attack`, `run`, `cast`. |
| `--description "<desc>"` | *(none)* | Extra character description to improve consistency. |
| `--frames <n>` | `5` | Total number of frames in the cycle. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--direction <dir>` | `front_right` | Which extracted character view to animate. |
| `--reference <path>` | *(auto-detect)* | Use a custom reference image instead of the generated view. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue}` | from `.env` | Override the chromakey used during cleanup. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--platform` / `--no-platform` | `--no-platform` | Add an isometric platform for perspective grounding. |
| `--tiles {1,4,9}` | `1` | Platform size. Values above `1` imply `--platform`. |

### Examples

Looping walk cycle:

```bash
pixel-magic animate --name samurai --animation walk --frames 6 --platform
```

One-shot attack with extra floor space:

```bash
pixel-magic animate --name samurai --animation attack --frames 4 --tiles 4 --no-loop
```

Spell cast with a custom reference:

```bash
pixel-magic animate \
  --name samurai \
  --animation cast \
  --frames 4 \
  --reference path/to/reference.png \
  --no-loop
```

### Output

```text
output/<name>/animations/<animation>/
├── canvas_input.png
├── sheet_raw.png
├── sheet_cleaned.png       # Present when platform cleanup runs
├── sheet.png
├── frame_01.png
├── frame_02.png
└── ...
```

## `pixel-magic animate-object`

Generate animation frames for an existing object sprite.

```bash
pixel-magic animate-object --set <set-name> --name <object-name> [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--set <set-name>` | Object set name, for example `forest`, `dungeon`, or `camp`. |
| `--name <object-name>` | Object name inside that set, for example `oak_tree_1` or `torch_1`. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--animation <type>` | `sway` | Animation name. |
| `--description "<desc>"` | *(none)* | Extra object description for consistency. |
| `--frames <n>` | `5` | Total number of frames in the cycle. |
| `--loop` / `--no-loop` | `--loop` | Generate a looping or one-shot sequence. |
| `--reference <path>` | *(auto-detect)* | Override the source object sprite path. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to protect green and blue object colors. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--platform` / `--no-platform` | `--no-platform` | Add an isometric platform for grounding. |
| `--tiles {1,4,9}` | `1` | Platform size. Values above `1` imply `--platform`. |
| `--sizes "<list>"` | *(none)* | Resize frames to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized frames. |

### Common Animation Types

| Type | Good for |
|---|---|
| `sway` | Trees, bushes, flags, banners |
| `flicker` | Torches, candles, lanterns |
| `burn` | Campfires, bonfires |
| `pulse` | Crystals, magic orbs, runes |
| `open` | Chests, gates, doors |
| `bob` | Floating items |
| `spin` | Coins, gems, gears |

### Examples

Looping torch flicker:

```bash
pixel-magic animate-object --set dungeon --name torch --animation flicker --frames 6
```

One-shot chest opening:

```bash
pixel-magic animate-object --set dungeon --name chest --animation open --frames 5 --no-loop
```

Looping campfire with resized outputs:

```bash
pixel-magic animate-object --set camp --name campfire --animation burn --frames 6 --sizes 32,64
```

### Output

```text
output/objects/<set-name>/animations/<object-name>/<animation>/
├── canvas_input.png
├── sheet_raw.png
├── sheet_cleaned.png       # Present when platform cleanup runs
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

## `pixel-magic effect`

Generate subjectless VFX animation sheets such as explosions, smoke, fire, and status effects.

```bash
pixel-magic effect (--name <effect> | --preset <preset>) [options]
```

### Required Arguments

| Argument | Description |
|---|---|
| `--name <effect>` | Generate a single named effect such as `explosion` or `fire`. |
| `--preset <preset>` | Generate all effects in a preset group: `combat`, `magic`, `nature`, `status`, or `custom`. |

### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--names "<a,b,c>"` | *(none)* | Required when using `--preset custom`. |
| `--description "<desc>"` | effect name | Optional extra description for the effect. |
| `--frames <n>` | `6` | Total number of frames. Must be at least `2`. Looping effects need at least `3`. |
| `--loop` / `--no-loop` | auto-detected by effect type | Override the default looping behavior. |
| `--output-dir <path>` | `output` | Root output directory. |
| `--style "<style>"` | `16-bit SNES RPG style` | Style description passed to Gemini. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--chromakey {green,blue,pink}` | `pink` | Pink is the default to preserve green and blue VFX colors. |
| `--sizes "<list>"` | *(none)* | Resize frames to `16,32,48,64,96,128,256` or `all`. |
| `--num-colors <n>` | *(preserve original)* | Palette size for resized frames. |

### Presets

| Preset | Effects |
|---|---|
| `combat` | `explosion`, `slash`, `shield_hit` |
| `magic` | `magic_circle`, `healing_aura`, `energy_ball` |
| `nature` | `smoke`, `fire`, `water_splash` |
| `status` | `poison_cloud`, `stun_stars`, `buff_glow` |

### Examples

One-shot explosion:

```bash
pixel-magic effect --name explosion --frames 4 --no-loop
```

Looping fire with resized outputs:

```bash
pixel-magic effect --name fire --frames 4 --sizes 32
```

Generate a full preset group:

```bash
pixel-magic effect --preset combat --frames 6
```

Custom effect set:

```bash
pixel-magic effect --preset custom --names "ice_burst,lightning_arc,holy_flash" --frames 5
```

### Output

```text
output/effects/<effect-name>/
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

When you use `--preset`, the command nests effects under the preset name:

```text
output/effects/<preset>/<effect-name>/
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
