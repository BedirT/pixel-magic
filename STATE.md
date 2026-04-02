# Project State

## Current Status: Single-Frame Animation (Active)

Bare-bones CLI tool for pixel art generation. Core generation pipeline is feature-complete. Animation pipeline has been rewritten from canvas-based multi-frame grid to **single-frame sequential generation** — one Gemini call per frame with reference + previous frame as context. Produces significantly better results than the grid approach.

## What Works

- **Character generation:** Generate isometric character sheets, either 4 or 8 views.
- **Animation generation:** Generate animation frames for existing characters using single-frame sequential generation. Each `--frame-poses` entry triggers one Gemini call with reference + previous frame as context. No frame count limit, no canvas grid, no cleanup pass needed. Thinking mode enabled.
- **Object animation:** Generate animation frames for existing props/objects using the same single-frame pipeline.
- **Effect generation:** Generate subjectless VFX sprites (explosion, fire, magic, status effects), with one-shot or looping sequences, optional resize, guide cleanup, and deterministic loop closure.
- **Terrain tile generation:** Generate terrain tiles with `--type` variants or `--theme` presets (forest, dungeon, desert, winter), diamond wireframe canvas.
- **World object generation:** Generate world objects with `--name` variants or `--preset` presets (forest, dungeon, village, camp, desert, winter), platform-guided canvas.
- **Gemini provider:** JSON-structured Jinja2 prompt templates, retry logic, thinking mode. Animation uses single-frame calls; tile/object/effect use canvas-based 2-pass pipeline (generate → cleanup).
- **Unified sprite post-processing** — sprite/effect/object flows share background removal (flood-fill chromakey) → mask cleanup (chromakey rejection, island/hole removal, outline strip) → outline re-add (1px black via morphological erosion). Tile command uses a separate tile cleanup path and adds `fit_tile()` after cleanup.
- **Pixel art resize** — optional `--sizes` flag on generate, animate-object, tile, object, and effect. Uses [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) for grid detection + color sampling, then outline re-add + optional palette quantization.
- **Prompt debug output** — every generation saves the rendered JSON prompt to the output directory for debugging. Animation saves per-frame prompts (`frame_02_prompt.json`, etc.).
- **Targeted tests** — effect CLI validation, loop-default logic, loop-closure enforcement, cleanup-pass behavior, and direction resolution are covered in `tests/`.

## What's Not Done Yet

### Bugs & Quality Issues

- [x] **Resize loses alpha on some objects** — fixed: preserve original alpha mask through proper-pixel-art pixelation and reapply after resize.
- [x] **Custom preset overwrites** — fixed: custom set names now derived from provided type/name labels instead of always "custom".
- [x] **Doubled output paths** — fixed: `_output_dir()` helper skips appending category when `--output-dir` already ends with it.
- [ ] **Internal outline treatment** — between body parts, armor pieces, etc. — same strip+re-add approach as outer outlines but needs detection of dark linear features between distinct color regions vs. shading/shadows.
- [x] **Resolve contour/resize test collection failures** — fixed: updated imports from `_regularize_contours` to `add_outline`.
- [x] **Font rendering ambiguity** — resolved by increasing font size and repositioning numbers to border corners where they're more visible.
- [ ] **East/West view naming** — fixed manually; view images had swapped east-west labels.

### Animation Quality (single-frame pipeline — active)

- [x] **Single-frame generation** — replaced canvas-based grid with sequential single-frame generation. Each frame gets full Gemini attention; reference + previous frame provide continuity context.
- [x] **Aspect ratio + image size constraints** — Gemini output constrained to match reference dimensions (portrait ratios supported: 3:4, 2:3, 9:16).
- [x] **Scale normalization** — generated frames rescaled to match reference height, then padded with bottom-center anchoring.
- [x] **Free-form animation descriptions** — `--animation-description` describes the overall animation.
- [x] **Per-frame pose descriptions** — `--frame-poses` required; each entry triggers one Gemini call. No frame count limit.
- [x] **Orientation in prompt** — character facing direction explicit in the prompt.
- [x] **Thinking mode** — Gemini thinking config (8192 budget) improves pose description adherence.
- [x] **Prompt debug output** — per-frame prompts saved alongside raw frames.
- [x] **Animation design agent** — agent that takes "walk" or "sword attack" and produces proper CLI commands with per-frame pose descriptions. Updated for single-frame pipeline.
- [ ] **Walk/idle animation quality** — improved with single-frame approach but subtle motions remain challenging.
- [ ] **Model comparison** — untested with single-frame pipeline. Grid-era finding: Pro produces better poses but adds shadow artifacts. Flash is cleaner but less expressive.

### Missing Features (v0.1 backlog)

- [x] **More animation types** — superseded by free-form `--animation-description`.
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
- **Animation quality depends on pose description quality** — the model follows detailed, physically-accurate descriptions well but ignores vague or generic ones. Writing good descriptions requires animation knowledge. Planned: animation design agent.
- **Walk/idle animations remain weak** — subtle motions are hardest for the model to differentiate from the reference pose. Attack/spell animations with dramatic motion changes produce the best results.
- **Frame number font ambiguity** — Pixelify Sans renders "5" similar to "8" at certain sizes. Mitigated by larger font but not fully solved.

## Architecture Decisions

- **Unified sprite post-processing** — character, animation, object, and effect frames share `_clean_sprite()` (remove background → cleanup mask → add outline) and `_resize_sprites()`. Tile uses `_clean_tile()` so terrain edges are preserved instead of being outline-normalized.
- **Outline strip + re-add at all sizes** — AI outlines are inconsistent (grey, varying thickness, sometimes missing). `cleanup_sprite()` strips the outermost dark boundary, then `add_outline()` paints a uniform 1px black outline via morphological erosion. This runs at native size, not just during resize.
- **Single-frame animation pipeline** — character/object animations generate one frame at a time. Each Gemini call receives the reference + previous frame as image context, plus a JSON prompt describing just that frame's pose. No canvas grid, no cleanup pass needed (no guides to remove). Generated frames are rescaled to match reference height, then padded to a uniform bounding box with bottom-center anchoring. Aspect ratio and image size passed to Gemini API to constrain output dimensions.
- **Single-pass effect generation** — effects use an empty numbered canvas. Gemini fills all slots in one call (prompt instructs painting over guide numbers). A cleanup pass removes any residual frame numbers, then local extraction + loop closure runs.
- **Reference + previous frame context** — each single-frame animation call sends [reference, previous_frame] as image context. Frame 2 gets just the reference; frames 3+ get both. This balances consistency (reference anchor) with continuity (smooth transitions).
- **Spatial rules system** — reusable animation constraints (ground line, center of mass, size consistency) in `_data.py`, replacing hardcoded per-animation-type descriptions.
- **No frame count limit** — single-frame pipeline has no batch size limit. Frame count = len(frame_poses) + 1 (reference). Each additional frame costs one Gemini call.
- **Pink chromakey default for non-character assets** — tile, object, animate-object, and effect flows default to pink so green foliage and blue water/ice/fire-adjacent colors survive extraction. Character generation still defaults to green (from `.env`).
- **Flood-fill chromakey for background removal** — replaced rembg (U2-Net) which produced soft alpha (98.7% semi-transparent pixels). Flood fill from image borders with channel-ratio detection produces binary alpha by construction.
- **proper-pixel-art for resize** — AI sprites look pixelated but aren't real pixel art. proper-pixel-art detects the actual pixel grid via Canny edge detection + Hough line transform, then samples dominant color per cell.
- **JSON prompts via Jinja2 templates** — prompts live as standalone `.json.j2` files in `prompts/templates/`, making them easy to read, edit, and iterate on independently from Python code. The `prompts/__init__.py` provides the same function signatures as before for backward compatibility.
- **Shared canvas utilities** — grid layout, frame extraction, and label drawing live in `canvas.py`, imported by animate, tile, object, and effect modules instead of being private functions in animate.py.
- **CLI over MCP** — simpler, no server overhead, easy to script.
