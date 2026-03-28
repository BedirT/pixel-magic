# CLI Reference

## Installation

```bash
uv sync
```

## Commands

### `pixel-magic generate`

Generate a multi-view isometric pixel art character sprite sheet.

```bash
pixel-magic generate --name <name> --description "<description>" [options]
```

#### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. Used as the output folder name under the output directory. Example: `--name "fire-mage"` creates `output/fire-mage/`. |
| `--description "<desc>"` | Character description in natural language. Be specific about clothing, weapons, colors, and distinguishing features. The more detail, the better the result. |

#### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--directions {4,8}` | `4` | Number of facing directions. **4-direction** generates 2 views (front-left 3/4, back-right 3/4). **8-direction** generates 5 views (back, back-right, right, front-right, front). The remaining directions are derived by mirroring. |
| `--tiles {1,4,9}` | `1` | Character tile footprint: 1 (default human-sized), 4 (2×2 — larger creature), 9 (3×3 — boss/mount). Larger tiles give the model more platform space per view. |
| `--output-dir <path>` | `output` | Root output directory. Character output is saved to `<output-dir>/<name>/`. |
| `--resolution <WxH>` | `64x64` | Target resolution per individual view in the prompt. This is a hint to the model — actual output size depends on the model. |
| `--max-colors <n>` | `16` | Maximum color count for the pixel art palette. Lower values produce more retro-looking sprites. |
| `--style "<style>"` | `16-bit SNES RPG style` | Art style description included in the prompt. |
| `--palette-hint "<hint>"` | *(none)* | Optional color palette guidance. Example: `--palette-hint "warm earth tones, no blue"`. |

#### Examples

Basic 4-direction character:
```bash
pixel-magic generate \
  --name "knight" \
  --description "A medieval knight with silver armor, blue cape, and a longsword"
```

8-direction with larger footprint:
```bash
pixel-magic generate \
  --name "fire-mage" \
  --description "A fire mage in red robes with a glowing staff and flame effects" \
  --directions 8 \
  --tiles 4
```

Custom style and palette:
```bash
pixel-magic generate \
  --name "cyberpunk-hacker" \
  --description "A cyberpunk hacker with neon visor, black trenchcoat, and holographic keyboard" \
  --style "GBA-era pixel art" \
  --max-colors 32 \
  --palette-hint "neon green, dark purple, black, electric blue"
```

#### Output

```
output/<name>/
├── raw.png           # Untouched model output (always)
├── sheet.png         # Background-removed version
├── views/            # Cleaned canonical sprites (binary alpha, mask hardened)
│   ├── front_left.png
│   └── back_right.png
└── views_raw/        # Raw extracted sprites before cleanup (for debugging)
    ├── front_left.png
    └── back_right.png
```

- **raw.png** — Exactly what the model returned, zero processing. Gemini images have a solid green (#00FF00) background.
- **sheet.png** — Background removed via chromakey flood fill from the image borders, then boundary despill clamps leftover key color on sprite edges.
- **views/** — Cleaned sprites with binary alpha (0 or 255 only). Chromakey-dominant fringe removed, small islands/holes cleaned. These are the canonical high-res sprites.
- **views_raw/** — Raw extracted sprites before cleanup, preserved for debugging and comparison.

### `pixel-magic animate`

Generate animation frames for an existing character sprite.

```bash
pixel-magic animate --name <name> --animation <type> [options]
```

#### Required Arguments

| Argument | Description |
|---|---|
| `--name <name>` | Character name. Must have existing sprites in `output/<name>/views/`. |

#### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--animation <type>` | `walk` | Animation type: `walk`, `idle`, `attack`, `run`, `cast` |
| `--description "<desc>"` | *(none)* | Character description (helps model consistency) |
| `--frames <n>` | `5` | Total frames in the animation cycle |
| `--loop` / `--no-loop` | `--loop` | Looping animation (first=last frame) or one-shot |
| `--direction <dir>` | `front_right` | Which extracted view to animate |
| `--reference <path>` | *(auto)* | Custom reference frame path (overrides auto-detect) |
| `--platform` / `--no-platform` | `--no-platform` | Add isometric platform tiles for perspective |
| `--tiles {1,4,9}` | `1` | Platform tile count: 1 (single), 4 (2×2 grid), 9 (3×3 grid). More tiles = more room for action poses. Implies `--platform`. |
| `--output-dir <path>` | `output` | Root output directory |
| `--chromakey {green,blue}` | from `.env` | Chromakey color |
| `--style "<style>"` | `16-bit SNES RPG style` | Art style |

#### Examples

Walk cycle (looping):
```bash
pixel-magic animate --name samurai --animation walk --frames 6 --platform --loop
```

Attack with extra floor space (one-shot):
```bash
pixel-magic animate --name samurai --animation attack --frames 4 --tiles 4 --no-loop
```

Spell cast with maximum floor space:
```bash
pixel-magic animate --name samurai --animation cast --frames 4 --tiles 9 --no-loop
```

#### Output

```
output/<name>/animations/<animation>/
├── canvas_input.png    # Input canvas sent to Gemini
├── sheet_raw.png       # Gemini raw output
├── sheet_cleaned.png   # After platform removal (if --platform)
├── sheet.png           # Final horizontal sprite sheet
├── frame_01.png        # Individual frames
├── frame_02.png
└── ...
```

### `pixel-magic tile`

Generate isometric terrain tilesets using a canvas-guided Gemini pipeline.

```bash
pixel-magic tile (--type <tile-type> | --theme <theme>) [options]
```

#### Required Arguments

| Argument | Description |
|---|---|
| `--type <tile-type>` | Generate variants of a single tile material, for example `grass`, `stone`, or `water`. Mutually exclusive with `--theme`. |
| `--theme <theme>` | Generate a predefined tile set: `forest`, `dungeon`, `desert`, `winter`, or `custom`. Mutually exclusive with `--type`. |

#### Optional Arguments

| Argument | Default | Description |
|---|---|---|
| `--variants <n>` | `4` | Number of variants for `--type` mode. Must be `>= 1`. |
| `--types "<a,b,c>"` | *(none)* | Required when using `--theme custom`. Comma-separated custom tile labels, for example `--types "mud,brick,poison swamp"`. |
| `--output-dir <path>` | `output` | Root output directory. Tiles are saved to `<output-dir>/tiles/<set-name>/`. |
| `--style "<style>"` | `16-bit SNES RPG style` | Art style description included in the prompt. |
| `--max-colors <n>` | `16` | Maximum color count in the prompt. |
| `--chromakey {green,blue,pink}` | `pink` for `tile` | Chromakey background for the tile pipeline. `tile` defaults to vivid pink even if the repo-wide `.env` default is green or blue. |
| `--depth <n>` | `4` | Side-face depth in pixels. Use `0` for flat top-only isometric diamonds. |
| `--sizes "<list>"` | *(none)* | Optional resized outputs, for example `32,64` or `all`. |
| `--num-colors <n>` | *(none)* | Optional palette size for resized outputs. |

#### Examples

Single material, multiple variants:
```bash
pixel-magic tile \
  --type grass \
  --variants 4 \
  --sizes 32,64
```

Predefined theme:
```bash
pixel-magic tile \
  --theme forest \
  --depth 4
```

Custom material set:
```bash
pixel-magic tile \
  --theme custom \
  --types "mud,brick,poison swamp"
```

Flat tiles:
```bash
pixel-magic tile \
  --type cobblestone \
  --variants 3 \
  --depth 0
```

#### Output

```
output/tiles/<set-name>/
├── canvas_input.png      # Labeled diamond canvas sent to Gemini
├── raw.png               # Gemini pass 1 output
├── sheet_cleaned.png     # Gemini pass 2 output after label/guide removal
├── <tile>.png            # Extracted high-res canonical tiles
├── 32x32/                # Optional resized outputs
│   └── <tile>.png
└── 64x64/
    └── <tile>.png
```

#### Tile Notes

- The tile canvas intentionally keeps text labels in the reference image. For terrain, the labels bind each slot to a specific material (`mud`, `brick`, `poison swamp`, etc.). Without them, custom sets drift more often than character views do.
- The cleanup pass removes those labels after generation. This means label readability matters less than material-slot binding.
- The tile pipeline defaults to **pink chromakey** because green backgrounds erase grass-like tiles and blue backgrounds erase water/ice-like tiles during chromakey cleanup.
- Small custom sets use an exact layout when possible. A 3-tile custom set uses a `3x1` canvas instead of a `2x2` grid with an empty cell, because empty cells encourage Gemini to hallucinate extra tiles.

#### Known Weaknesses

- Tile material quality is still model-driven. Even with the improved canvas, some materials need retries to get a strong result.
- Water-like and ice-like surfaces survive extraction better with pink chromakey, but their internal shading and edge design can still vary noticeably between runs.
- Text labels help slot binding, but they also add some visual noise to the input canvas. The current tradeoff favors correctness. A future iteration may switch to minimal numeric IDs in-canvas with the full label mapping moved into the prompt.
- The cleanup pass removes labels and guides, but faint model artifacts can still remain in rare runs. Keep `raw.png` and `sheet_cleaned.png` for debugging when a tile looks off.

---

## Environment Configuration

Settings are loaded from a `.env` file in the project root. CLI arguments override `.env` values.

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | *(required)* | Google AI API key |
| `PIXEL_MAGIC_GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Gemini model name |
| `PIXEL_MAGIC_DIRECTION_MODE` | `4` | Default direction count |
| `PIXEL_MAGIC_MAX_COLORS` | `16` | Default color limit |
| `PIXEL_MAGIC_CHROMAKEY_COLOR` | `green` | Default chromakey color for character generation and animation (`green` or `blue`). The `tile` command uses `pink` by default unless you override it with `--chromakey`. |
| `PIXEL_MAGIC_OUTPUT_DIR` | `output` | Default output directory |

Example `.env`:
```env
GOOGLE_API_KEY=AI...
PIXEL_MAGIC_CHROMAKEY_COLOR=green
```
