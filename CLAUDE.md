# pixel-magic

AI-powered pixel art character sprite generation CLI. Generates isometric multi-view character sheets using OpenAI (gpt-image-1.5) or Google Gemini, saving raw model output with zero post-processing.

## Tech Stack

- Python 3.12+, uv package manager
- OpenAI + Gemini image generation APIs
- Pillow for image handling
- pydantic-settings for config (.env)

## Commands

- Generate: `pixel-magic generate --name <name> --description "<desc>" --directions 4|8 --provider openai|gemini`
- Install deps: `uv sync`

## Workflow

- Simplicity above all — minimal code, minimal dependencies, minimal abstractions
- Save model output raw with zero processing — no alpha thresholding, no cleanup, no quantization
- JSON-structured prompts for character generation — models respond well to structured format
- One feature at a time — get it working before adding the next thing

## Structure

```
src/pixel_magic/
    __main__.py     # CLI entry point (argparse)
    config.py       # Settings from .env
    prompts.py      # JSON prompt builder for character sheets
    providers/      # OpenAI + Gemini generation backends
```
