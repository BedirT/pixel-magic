# Project State

## Current Status: CLI Rewrite (cli-rewrite branch)

Scrapped the over-engineered MCP server (13k+ lines, 40+ files, 13 deps) and rebuilt as a bare-bones CLI tool.

## What Works

- **Character generation** — `pixel-magic generate` with `--name`, `--description`, `--directions 4|8`
- **OpenAI provider** — gpt-image-1.5 with native transparency, retry logic
- **Gemini provider** — gemini-3.1-flash-image-preview with chromakey green background, retry logic
- **JSON-structured prompts** — multi-view isometric character reference sheets (2 views for 4-dir, 5 views for 8-dir), black outline enforcement on all elements
- **Raw output** — saves exactly what the model returns, zero processing
- **Background removal (Gemini)** — two-stage pipeline: rembg (U2-Net segmentation) for alpha mask + green despill for edge cleanup. Saves `sheet.png` alongside `raw.png`
- **Sprite extraction** — connected-component analysis on alpha channel to split composite sheets into individual view PNGs. Handles inconsistent LLM placement via proximity merging, noise filtering, and adaptive merge when expected view count is known. Saves to `output/<name>/views/`

## What's Not Done Yet

- [ ] Animation support (walk, idle, attack frame strips)
- [ ] Tileset generation
- [ ] Effect/UI/item generation
- [ ] Atlas packing (combine frames into sprite atlas)
- [ ] Tests

## Known Limitations

- **Green fringe on soft edges** — elements without strong black outlines (fire, smoke, glow effects) can retain faint green tinting from the chromakey background after removal. The despill pass handles most cases, but semi-transparent effects are inherently difficult. Enforcing black outlines via the prompt helps significantly.
- **Flames/particles resist outline enforcement** — the prompt instructs black outlines on all elements, but models don't always comply for fire, magic particles, and similar wispy effects.

## Architecture Decisions

- **No post-processing on raw output** — the old pipeline (alpha thresholding, island removal, palette quantization, outline enforcement) corrupted model output. Raw is preserved untouched.
- **rembg for background removal** — U2-Net segmentation is far more accurate than heuristic chromakey (color-distance thresholding) which ate into sprite edges. The model handles complex shapes and fine details properly.
- **Green despill** — after rembg, edge pixels retain green color bleed from the chromakey. Clamping `G = min(G, max(R,B))` on edge pixels (partial alpha + opaque within 3px of boundary) neutralizes the green without affecting sprite colors.
- **JSON prompts** — models respond well to structured JSON describing the desired image. Better consistency than prose prompts.
- **Single API call per character** — generate all views in one image for consistency across directions.
- **CLI over MCP** — simpler, no server overhead, easy to script.

## Structure

```
src/pixel_magic/
    __init__.py
    __main__.py      # CLI entry point (argparse)
    config.py        # Settings from .env
    prompts.py       # JSON prompt builder for character sheets
    background.py    # Background removal (rembg + despill)
    extract.py       # Smart sprite extraction from sheets
    providers/
        __init__.py
        base.py      # GenerationConfig / GenerationResult contracts
        openai.py    # OpenAI generation backend
        gemini.py    # Gemini generation backend
docs/
    process.md       # Generation process flowchart
    cli.md           # CLI reference documentation
```

## Old Codebase (main branch)

The previous implementation is preserved on `main`. It had: MCP server, LLM agent orchestration, multi-stage executor, deterministic QA, vision QA, OpenTelemetry tracing, usage tracking. All removed in favor of simplicity.
