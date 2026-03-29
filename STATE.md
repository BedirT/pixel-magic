# Project State

## Current Status: Feature-Complete Core

Bare-bones CLI tool for pixel art generation. All four generation commands are working.

## What Works

- **Character generation** — `pixel-magic generate` with `--name`, `--description`, `--directions 4|8`, `--tiles 1|4|9`
- **Animation generation** — `pixel-magic animate` with walk/idle/attack/run/cast cycles, looping or one-shot, platform-guided perspective
- **Terrain tile generation** — `pixel-magic tile` with `--type` variants or `--theme` presets (forest, dungeon, desert, winter), diamond wireframe canvas
- **World object generation** — `pixel-magic object` with `--name` variants or `--preset` presets (forest, dungeon, village, camp, desert, winter), platform-guided canvas
- **Gemini provider** — canvas-based 2-pass pipeline (generate → cleanup), JSON-structured prompts, retry logic
- **Unified post-processing** — all commands share the same pipeline: background removal (flood-fill chromakey) → mask cleanup (chromakey rejection, island/hole removal, outline strip) → outline re-add (1px black via morphological erosion). Tile command adds `fit_tile()` after cleanup.
- **Pixel art resize** — optional `--sizes` flag on generate/tile/object. Uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) for grid detection + color sampling, then outline re-add + optional palette quantization.

## What's Not Done Yet

- [ ] Internal outline treatment (between body parts, armor pieces — same strip+re-add as outer outlines)
- [ ] Atlas packing (combine frames into sprite atlas)
- [ ] Tests

## Known Limitations

- **Chromakey color clash** — green chromakey can interfere with green-skinned characters (goblins, orcs). Use `--chromakey blue` for green characters, `--chromakey green` (default) for blue characters.
- **Green fringe on soft edges** — elements without strong black outlines (fire, smoke, glow effects) can retain faint color tinting from the chromakey background after removal. The despill pass handles most cases, but semi-transparent effects are inherently difficult. Enforcing black outlines via the prompt helps significantly.
- **Flames/particles resist outline enforcement** — the prompt instructs black outlines on all elements, but models don't always comply for fire, magic particles, and similar wispy effects.

## Architecture Decisions

- **Unified post-processing** — all commands share `_clean_sprite()` (remove background → cleanup mask → add outline) and `_resize_sprites()`. No per-command duplication. Only tile adds an extra `fit_tile()` step.
- **Outline strip + re-add at all sizes** — AI outlines are inconsistent (grey, varying thickness, sometimes missing). `cleanup_sprite()` strips the outermost dark boundary, then `add_outline()` paints a uniform 1px black outline via morphological erosion. This runs at native size, not just during resize.
- **Canvas-based 2-pass pipeline** — all canvas commands (generate, animate, tile, object) use the same pattern: build template → Gemini fills content → cleanup pass removes guides. Templates vary (platforms for characters/objects, wireframes for tiles).
- **Pink chromakey default for tile/object** — green backgrounds destroy grass/tree tiles, blue destroys water/ice. Pink preserves both. Character generation still defaults to green (from `.env`).
- **Flood-fill chromakey for background removal** — replaced rembg (U2-Net) which produced soft alpha (98.7% semi-transparent pixels). Flood fill from image borders with channel-ratio detection produces binary alpha by construction.
- **proper-pixel-art for resize** — AI sprites look pixelated but aren't real pixel art. proper-pixel-art detects the actual pixel grid via Canny edge detection + Hough line transform, then samples dominant color per cell.
- **JSON prompts** — models respond well to structured JSON describing the desired image. Better consistency than prose prompts.
- **CLI over MCP** — simpler, no server overhead, easy to script.

## Structure

```
src/pixel_magic/
    __init__.py
    __main__.py      # CLI entry point (argparse) + shared post-processing helpers
    config.py        # Settings from .env
    prompts.py       # JSON prompt builders for all commands
    animate.py       # Canvas building, grid layout, frame extraction
    tile.py          # Terrain tile generation (canvas, extraction, fitting)
    object.py        # World object generation (canvas, extraction)
    platform.py      # Isometric platform + tile outline generation
    background.py    # Flood-fill chromakey removal + boundary despill
    extract.py       # Smart sprite extraction from sheets
    cleanup.py       # Mask cleanup + outer outline stripping
    resize.py        # Pixel art resize (proper-pixel-art) + outline add
    providers/
        __init__.py
        base.py      # GenerationConfig / GenerationResult contracts
        gemini.py    # Gemini generation backend
docs/
    process.md       # Generation process flowchart
    cli.md           # CLI reference documentation
```
