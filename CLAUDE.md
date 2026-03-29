# pixel-magic

AI-powered pixel art asset generation CLI. Generates isometric character sheets, animation sprite sheets, terrain tiles, world objects, and VFX effects using Google Gemini with a canvas-based pipeline.

## Tech Stack

- Python 3.12+, uv package manager
- Google Gemini image generation API (multimodal)
- Jinja2 for prompt templates
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
- All prompts are JSON-structured Jinja2 templates in `prompts/templates/`
- One feature at a time — get it working before adding the next thing

## Structure

```
src/pixel_magic/
    __main__.py     # CLI entry point (argparse)
    config.py       # Settings from .env
    canvas.py       # Shared canvas utilities (grid layout, frame extraction)
    animate.py      # Animation orchestration + character generation canvas
    tile.py         # Terrain tile generation (canvas, extraction, fitting)
    object.py       # World object generation (canvas, extraction)
    effect.py       # VFX effect presets and resolution
    platform.py     # Isometric platform + tile outline generation
    background.py   # Chromakey removal (flood-fill + despill)
    extract.py      # Sprite extraction (connected-component)
    cleanup.py      # Mask cleanup (chromakey rejection, binary alpha)
    resize.py       # Pixel art resizing (proper-pixel-art + contour regularization)
    prompts/        # Jinja2 JSON prompt templates
        __init__.py         # Public API (prompt builder functions)
        _engine.py          # Jinja2 rendering engine
        _data.py            # Shared constants (views, animation descriptions)
        templates/          # .json.j2 template files
    providers/      # Gemini generation backend
```
