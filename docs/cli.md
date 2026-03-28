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
├── sheet.png         # Background-removed version (Gemini provider only)
├── views/            # Cleaned canonical sprites (binary alpha, mask hardened)
│   ├── front_left.png
│   └── back_right.png
└── views_raw/        # Raw extracted sprites before cleanup (for debugging)
    ├── front_left.png
    └── back_right.png
```

- **raw.png** — Exactly what the model returned, zero processing. Gemini images have a solid green (#00FF00) background.
- **sheet.png** — Background removed via U2-Net segmentation (rembg) with chromakey despill.
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

---

## Environment Configuration

Settings are loaded from a `.env` file in the project root. CLI arguments override `.env` values.

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | *(required)* | Google AI API key |
| `PIXEL_MAGIC_GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Gemini model name |
| `PIXEL_MAGIC_DIRECTION_MODE` | `4` | Default direction count |
| `PIXEL_MAGIC_MAX_COLORS` | `16` | Default color limit |
| `PIXEL_MAGIC_CHROMAKEY_COLOR` | `green` | Chromakey color (`green` or `blue`) |
| `PIXEL_MAGIC_OUTPUT_DIR` | `output` | Default output directory |

Example `.env`:
```env
GOOGLE_API_KEY=AI...
PIXEL_MAGIC_CHROMAKEY_COLOR=green
```
