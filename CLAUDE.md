# pixel-magic

AI-powered pixel art asset generation CLI. Generates isometric character sheets, animation sprite sheets, terrain tiles, world objects, and VFX effects using Google Gemini with a canvas-based pipeline.

## Tech Stack

- Python 3.12+, uv package manager
- Google Gemini image generation API (multimodal)
- Pillow for image handling
- pydantic-settings for config (.env)

## Commands

- `pixel-magic generate` — multi-view isometric character sheets
- `pixel-magic animate` — animation frames for existing characters
- `pixel-magic animate-object` — animation frames for existing objects
- `pixel-magic tile` — isometric terrain tilesets
- `pixel-magic object` — world objects/props on labeled platforms
- `pixel-magic effect` — subjectless VFX animations (explosions, fire, magic, etc.)
- Full CLI reference: `docs/cli.md`

## Workflow

- Simplicity above all — minimal code, minimal dependencies, minimal abstractions
- Canvas-based pipeline — build guide template, Gemini fills content, cleanup pass removes guides
- JSON-structured prompts for generation, narrative prompts for animation
- One feature at a time — get it working before adding the next thing

## Structure

```
src/pixel_magic/
    __main__.py     # CLI entry point (argparse)
    config.py       # Settings from .env
    prompts.py      # Prompt builders for generation + animation
    animate.py      # Canvas building, grid layout, frame extraction
    tile.py         # Terrain tile generation (canvas, extraction, fitting)
    object.py       # World object generation (canvas, extraction)
    effect.py       # VFX effect presets and resolution
    platform.py     # Isometric platform + tile outline generation
    background.py   # Chromakey removal (flood-fill + despill)
    extract.py      # Sprite extraction (connected-component)
    cleanup.py      # Mask cleanup (chromakey rejection, binary alpha)
    resize.py       # Pixel art resizing (proper-pixel-art + contour regularization)
    providers/      # Gemini generation backend
```
