# Pixel Magic

AI-powered pixel art character sprite generation CLI. Generates isometric multi-view character sheets using OpenAI (gpt-image-1.5) or Google Gemini, with proper pixel art resizing powered by [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art).

## Quick Start

```bash
git clone https://github.com/BedirT/pixel-magic.git
cd pixel-magic
uv sync
cp .env.example .env
# set OPENAI_API_KEY and/or GOOGLE_API_KEY
```

## Usage

```bash
# Generate a 4-direction character sheet
pixel-magic generate --name knight --description "medieval knight with sword and shield"

# 8-direction sheet with Gemini
pixel-magic generate --name mage --description "fire mage" --directions 8 --provider gemini

# Generate and resize to true pixel art
pixel-magic generate --name knight --description "medieval knight" --sizes 32,64

# Resize with color quantization (16-color palette)
pixel-magic generate --name knight --description "medieval knight" --sizes all --num-colors 16
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--name` | required | Character name (output folder) |
| `--description` | required | Character description |
| `--directions` | 4 | Number of views: 4 or 8 |
| `--provider` | from .env | `openai` or `gemini` |
| `--output-dir` | `output` | Output directory |
| `--resolution` | `64x64` | Target resolution per view |
| `--max-colors` | 16 | Max color count in prompt |
| `--style` | `16-bit SNES RPG style` | Art style |
| `--sizes` | | Resize to pixel art sizes (e.g. `32,64` or `all`) |
| `--num-colors` | | Palette size for resized sprites |

### Output Structure

```
output/knight/
  raw.png                    # Raw model output (1024x1024)
  sheet.png                  # Background-removed (Gemini only)
  views/
    front_left.png           # Extracted sprites
    back_right.png
    32x32/                   # True pixel art at 32x32
      front_left.png
      back_right.png
    64x64/                   # True pixel art at 64x64
      front_left.png
      back_right.png
```

## How Resizing Works

AI-generated sprites look pixel-art-ish but aren't — they're high-res images with anti-aliasing and sub-pixel detail. The `--sizes` flag uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) to:

1. Detect the underlying pixel grid via Canny edge detection + Hough line transform
2. Sample the dominant color per grid cell (not averaging — offset binning)
3. Optionally quantize to a limited palette (with `--num-colors`)
4. Resize to target dimensions with nearest-neighbor to preserve hard pixel edges

## Configuration

Set in `.env` with `PIXEL_MAGIC_` prefix:

- `PIXEL_MAGIC_PROVIDER` — `openai` or `gemini` (default: `openai`)
- `OPENAI_API_KEY` — OpenAI API key
- `GOOGLE_API_KEY` — Google Gemini API key
- `PIXEL_MAGIC_CHROMAKEY_COLOR` — `green` or `blue` for Gemini backgrounds

## Acknowledgments

- [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) by Kenneth J. Allen — the grid detection and pixelation engine that powers our sprite resizing. Converts noisy AI pixel art into true-resolution pixel art using edge detection, Hough line transform, and intelligent color sampling.

## License

MIT
