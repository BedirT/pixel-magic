# Pixel Magic

AI-powered pixel art sprite and terrain tile generation CLI built around a Gemini canvas pipeline. It generates isometric character sheets, animation sheets, and terrain tilesets, then cleans and extracts usable PNG assets.

## Quick Start

```bash
git clone https://github.com/BedirT/pixel-magic.git
cd pixel-magic
uv sync
cp .env.example .env
# set GOOGLE_API_KEY in .env
```

## Core Commands

Generate a character sheet:

```bash
pixel-magic generate \
  --name knight \
  --description "medieval knight with silver armor, blue cape, and longsword"
```

Generate an animation for an existing character:

```bash
pixel-magic animate \
  --name knight \
  --animation walk \
  --frames 6 \
  --platform
```

Generate terrain tiles:

```bash
pixel-magic tile \
  --theme forest \
  --sizes 32,64
```

## How It Works

- `generate` builds an isometric platform canvas, sends it to Gemini, removes the guides, then extracts per-view sprites.
- `animate` uses an existing character frame as reference and generates a horizontal sprite sheet.
- `tile` builds labeled diamond canvases so each slot stays bound to the intended material, then strips those labels in a cleanup pass.
- Optional resizing uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) to convert high-resolution AI output into true pixel art sizes.

## Current Caveats

- Character generation intentionally avoids text labels on the canvas because labels degrade pixel art quality there.
- Tile generation intentionally keeps labels on the canvas because custom material sets drift too much without slot labels.
- The tile pipeline defaults to vivid pink chromakey. Green backgrounds eat grass-like tiles and blue backgrounds eat water- and ice-like tiles.
- Tile quality is still model-driven. Liquids, ice, swamp materials, and glossy surfaces may need retries.

## Configuration

Settings are loaded from `.env` with the `PIXEL_MAGIC_` prefix where applicable:

- `GOOGLE_API_KEY`: Google AI API key
- `PIXEL_MAGIC_GEMINI_IMAGE_MODEL`: Gemini image model name
- `PIXEL_MAGIC_CHROMAKEY_COLOR`: default chromakey for character generation and animation (`green` or `blue`)
- `PIXEL_MAGIC_OUTPUT_DIR`: default output directory
- `PIXEL_MAGIC_MAX_COLORS`: default prompt color limit

The `tile` command uses pink chromakey by default unless you override it with `--chromakey`.

## Docs

- CLI reference: [`docs/cli.md`](/Users/bedirt/Documents/Github/pixel-magic/docs/cli.md)
- Process overview: [`docs/process.md`](/Users/bedirt/Documents/Github/pixel-magic/docs/process.md)
- Generation research notes: [`docs/research/sprite-generation.md`](/Users/bedirt/Documents/Github/pixel-magic/docs/research/sprite-generation.md)
- Background removal research: [`docs/research/background-removal.md`](/Users/bedirt/Documents/Github/pixel-magic/docs/research/background-removal.md)

## License

MIT
