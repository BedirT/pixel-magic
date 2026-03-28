# Project State

## Current Status: CLI Rewrite (cli-rewrite branch)

Scrapped the over-engineered MCP server (13k+ lines, 40+ files, 13 deps) and rebuilt as a bare-bones CLI tool.

## What Works

- **Character generation** — `pixel-magic generate` with `--name`, `--description`, `--directions 4|8`
- **OpenAI provider** — gpt-image-1.5 with native transparency, retry logic
- **Gemini provider** — gemini-3.1-flash-image-preview with chromakey background (green or blue), retry logic
- **JSON-structured prompts** — multi-view isometric character reference sheets (2 views for 4-dir, 5 views for 8-dir), black outline enforcement on all elements
- **Raw output** — saves exactly what the model returns, zero processing
- **Background removal (Gemini)** — flood-fill chromakey removal from image borders using channel-ratio detection (`G > max(R,B) + 30`), 4-connected BFS. Produces binary alpha (0 or 255 only). Boundary despill clamps chromakey channel on the 1px sprite edge. Supports green or blue chromakey via `--chromakey` flag.
- **Sprite extraction** — connected-component analysis on alpha channel to split composite sheets into individual view PNGs. Handles inconsistent LLM placement via proximity merging, noise filtering, and adaptive merge when expected view count is known. Raw extractions saved to `output/<name>/views_raw/`.
- **Mask cleanup + outline strip** — extracted sprites are cleaned: chromakey-dominant fringe rejection, island/hole removal, and outer outline stripping (removes the AI's 1px dark boundary so pixelation works on a clean body). Cleaned canonical sprites saved to `output/<name>/views/`.
- **Outline re-add** — after pixelation, a uniform 1px black outline is added algorithmically via morphological erosion. This replaces the AI's inconsistent outlines with a guaranteed clean silhouette at every target size.
- **Pixel art resize** — uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) to convert AI sprites to true pixel art at target sizes (16–256px). Detects the underlying pixel grid via edge detection + Hough line transform, samples dominant color per cell, optional palette quantization. `--sizes` and `--num-colors` flags.

## What's Not Done Yet

- [ ] Animation support (walk, idle, attack frame strips)
- [ ] Tileset generation
- [ ] Effect/UI/item generation
- [ ] Atlas packing (combine frames into sprite atlas)
- [ ] Tests

## Known Limitations

- **Chromakey color clash** — green chromakey can interfere with green-skinned characters (goblins, orcs). Use `--chromakey blue` for green characters, `--chromakey green` (default) for blue characters.
- **Green fringe on soft edges** — elements without strong black outlines (fire, smoke, glow effects) can retain faint color tinting from the chromakey background after removal. The despill pass handles most cases, but semi-transparent effects are inherently difficult. Enforcing black outlines via the prompt helps significantly.
- **Flames/particles resist outline enforcement** — the prompt instructs black outlines on all elements, but models don't always comply for fire, magic particles, and similar wispy effects.

## Architecture Decisions

- **No post-processing on raw output** — raw.png is always preserved untouched for debugging.
- **Flood-fill chromakey for background removal** — replaced rembg (U2-Net) which produced soft alpha (98.7% semi-transparent pixels). Flood fill from image borders with channel-ratio detection produces binary alpha by construction, preserves interior green pixels (orc skin), and removes ~92MB of dependencies. See `docs/research/background-removal.md` for full comparison of 10 approaches evaluated.
- **Boundary despill** — JPEG compression and AI rendering blend chromakey color into the 1px sprite edge. Despill clamps the chromakey channel to max of the other two on boundary pixels only.
- **Outline strip + re-add** — AI outlines are inconsistent (grey, varying thickness, sometimes missing). Rather than trying to preserve them through downscaling, we strip the outermost dark boundary in the high-res sprite and add a guaranteed uniform 1px black outline algorithmically at the target pixel art size. Produces 100% black boundary coverage at 64x64 and 128x128.
- **proper-pixel-art for resize** — AI sprites look pixelated but aren't real pixel art (anti-aliasing, sub-pixel gradients). proper-pixel-art detects the actual pixel grid via Canny edge detection + Hough line transform, then samples dominant color per cell using offset binning. This produces genuine pixel art at any target size.
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
    background.py    # Flood-fill chromakey removal + boundary despill
    extract.py       # Smart sprite extraction from sheets
    cleanup.py       # Mask cleanup + outer outline stripping
    resize.py        # Pixel art resize (proper-pixel-art) + outline re-add
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
