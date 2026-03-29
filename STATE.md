# Project State

## Current Status: Feature-Complete Core

Bare-bones CLI tool for pixel art generation.

## What Works

- **Character generation:** Generate isometric character sheets, either 4 or 8 views.
- **Animation generation:** Generate animation frames for existing characters, any animation cycle.
- **Object animation:** Generate animation frames for existing props/objects with sway/flicker/burn/pulse/open/bob/spin cycles.
- **Terrain tile generation:** Generate terrain tiles with `--type` variants or `--theme` presets (forest, dungeon, desert, winter), diamond wireframe canvas.
- **World object generation:** Generate world objects with `--name` variants or `--preset` presets (forest, dungeon, village, camp, desert, winter), platform-guided canvas.
- **Effect generation:** Generate subjectless VFX sprites (explosion, fire, magic, status effects), with one-shot or looping sequences, preset groups, optional resize, guide cleanup, and deterministic loop closure.
- **Gemini provider:** Canvas-based 2-pass pipeline (generate → cleanup), JSON-structured prompts, retry logic.
- **Unified sprite post-processing** — sprite/effect/object flows share background removal (flood-fill chromakey) → mask cleanup (chromakey rejection, island/hole removal, outline strip) → outline re-add (1px black via morphological erosion). Tile command uses a separate tile cleanup path and adds `fit_tile()` after cleanup.
- **Pixel art resize** — optional `--sizes` flag on generate, animate-object, tile, object, and effect. Uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) for grid detection + color sampling, then outline re-add + optional palette quantization.
- **Targeted effect tests** — effect CLI validation, loop-default logic, loop-closure enforcement, and cleanup-pass behavior are covered in `tests/test_effect.py`

## What's Not Done Yet

- [ ] Internal outline treatment (between body parts, armor pieces — same strip+re-add as outer outlines)
- [ ] Atlas packing (combine frames into sprite atlas)
- [ ] Broader end-to-end / golden-image coverage for generated outputs
- [ ] Resolve the remaining full-suite collection failures in contour/resize tests

## Known Limitations

- **Chromakey color clash** — green chromakey can interfere with green-skinned characters (goblins, orcs). Use `--chromakey blue` for green characters, `--chromakey green` (default) for blue characters.
- **Green fringe on soft edges** — elements without strong black outlines (fire, smoke, glow effects) can retain faint color tinting from the chromakey background after removal. The despill pass handles most cases, but semi-transparent effects are inherently difficult. Enforcing black outlines via the prompt helps significantly.
- **Flames/particles resist outline enforcement** — the prompt instructs black outlines on all elements, but models don't always comply for fire, magic particles, and similar wispy effects.
- **Loop quality still depends on model motion quality** — looping effects now close exactly at frame 1/frame N, but the in-between motion is still model-generated and can vary in smoothness.

## Architecture Decisions

- **Unified sprite post-processing** — character, animation, object, and effect frames share `_clean_sprite()` (remove background → cleanup mask → add outline) and `_resize_sprites()`. Tile uses `_clean_tile()` so terrain edges are preserved instead of being outline-normalized.
- **Outline strip + re-add at all sizes** — AI outlines are inconsistent (grey, varying thickness, sometimes missing). `cleanup_sprite()` strips the outermost dark boundary, then `add_outline()` paints a uniform 1px black outline via morphological erosion. This runs at native size, not just during resize.
- **Canvas-based cleanup stays explicit** — guide-removal is not trusted to prompting alone. Character/object/tile/effect canvas flows save raw output and run an explicit cleanup pass when guide artifacts matter.
- **Single-pass effect generation** — effects use an empty numbered canvas. Gemini fills all slots in one call (prompt instructs painting over guide numbers). A cleanup pass removes any residual frame numbers, then local extraction + loop closure runs.
- **Pink chromakey default for non-character assets** — tile, object, animate-object, and effect flows default to pink so green foliage and blue water/ice/fire-adjacent colors survive extraction. Character generation still defaults to green (from `.env`).
- **Flood-fill chromakey for background removal** — replaced rembg (U2-Net) which produced soft alpha (98.7% semi-transparent pixels). Flood fill from image borders with channel-ratio detection produces binary alpha by construction.
- **proper-pixel-art for resize** — AI sprites look pixelated but aren't real pixel art. proper-pixel-art detects the actual pixel grid via Canny edge detection + Hough line transform, then samples dominant color per cell.
- **JSON prompts** — models respond well to structured JSON describing the desired image. Better consistency than prose prompts.
- **CLI over MCP** — simpler, no server overhead, easy to script.
