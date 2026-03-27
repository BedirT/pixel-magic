# pixel-magic

AI-powered pixel art character sprite generation and animation CLI. Generates isometric multi-view character sheets and animation sprite sheets using Google Gemini with a canvas-based pipeline: labeled isometric platforms provide perspective grounding, Gemini fills in characters, platforms are removed in a second pass.

## Tech Stack

- Python 3.12+, uv package manager
- Google Gemini image generation API (multimodal)
- Pillow for image handling
- pydantic-settings for config (.env)

## Commands

- Generate: `pixel-magic generate --name <name> --description "<desc>" --directions 4|8 --tiles 1|4|9`
- Animate: `pixel-magic animate --name <name> --animation walk|attack|cast --frames 6 --platform --tiles 1|4|9`
- Install deps: `uv sync`

## Workflow

- Simplicity above all — minimal code, minimal dependencies, minimal abstractions
- Canvas-based pipeline — build platform template, Gemini fills characters, cleanup pass removes platforms
- JSON-structured prompts for character generation, narrative prompts for animation
- One feature at a time — get it working before adding the next thing

## Structure

```
src/pixel_magic/
    __main__.py     # CLI entry point (argparse)
    config.py       # Settings from .env
    prompts.py      # Prompt builders for generation + animation
    animate.py      # Canvas building, grid layout, frame extraction
    platform.py     # Isometric platform tile generation
    background.py   # Chromakey removal (rembg + despill)
    extract.py      # Sprite extraction (connected-component)
    resize.py       # Pixel art resizing (proper-pixel-art)
    providers/      # Gemini generation backend
```
