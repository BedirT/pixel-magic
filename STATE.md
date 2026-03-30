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

### Bugs & Quality Issues

- [ ] **Resize loses alpha on some objects** — the `--sizes` resize pipeline produces fully opaque (0% transparent) 64x64 PNGs for some objects. Native-size sprites have correct transparency. Likely a proper-pixel-art or quantization step drops the alpha channel.
- [ ] **Custom preset overwrites** — running `tile --theme custom` or `object --preset custom` multiple times overwrites the same `custom/` directory. Each custom run needs a unique output directory name (e.g., hash of the type names, or a user-provided `--set-name` flag).
- [ ] **Doubled output paths** — when `--output-dir` already contains a category subdirectory (e.g., `assets/tiles`), the CLI adds another `tiles/` inside, resulting in `tiles/tiles/custom/`. The output-dir should be the root, not per-category.
- [ ] **Internal outline treatment** — between body parts, armor pieces, etc. — same strip+re-add approach as outer outlines but needs detection of dark linear features between distinct color regions vs. shading/shadows.
- [ ] **Resolve contour/resize test collection failures** — `test_contour.py` and `test_resize_integration.py` import `_regularize_contours` which no longer exists in `resize.py`.

### Missing Features (v0.1 backlog)

- [ ] **More animation types** — missing common RPG animations: hurt, death, dodge, jump, block. The description library only has walk/idle/attack/run/cast.
- [ ] **Atlas packing** — combine extracted frames into a single sprite atlas PNG + JSON metadata (frame positions, sizes). Standard format for game engines.
- [ ] **Animated tiles** — tiles with animation frames (flowing water, bubbling lava, flickering torches). Currently tiles are static only.
- [ ] **Item/inventory generation** — non-isometric item sprites (swords, potions, scrolls) for inventory views. Front-facing 2D, not isometric.
- [ ] **UI components** — generate pixel art UI elements (buttons, panels, frames, health bars, dialog boxes).
- [ ] **Library API** — make everything usable programmatically (`from pixel_magic import generate_character`), not just via CLI.
- [ ] **Sprite viewer** — simple web UI or CLI viewer to display/preview generated sprites and animations.

### Quality & Testing

- [ ] **Broader end-to-end / golden-image test coverage** — validate full pipeline output against reference images.
- [ ] **Large sprite pixel-art quality** — tiles=4 and tiles=9 sprites come out more painterly than pixel-art at native resolution. The resize to 64x64/128x128 helps but the source is too detailed. May need stronger pixel-art enforcement in prompts for large canvases.
- [ ] **Prompt regression tests** — verify rendered Jinja2 templates produce semantically equivalent output to the old hardcoded prompts.

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
- **JSON prompts** — models respond well to structured JSON describing the desired image. Better consistency than prose prompts. All prompts (including animation/cleanup) are now JSON-structured Jinja2 templates.
- **Jinja2 prompt templates** — prompts live as standalone `.json.j2` files in `prompts/templates/`, making them easy to read, edit, and iterate on independently from Python code. The `prompts/__init__.py` provides the same function signatures as before for backward compatibility.
- **Shared canvas utilities** — grid layout, frame extraction, and label drawing live in `canvas.py`, imported by animate, tile, object, and effect modules instead of being private functions in animate.py.
- **CLI over MCP** — simpler, no server overhead, easy to script.
