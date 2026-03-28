# Sprite Generation Research — What We Tried & Learned

**Date:** March 2026
**Goal:** Generate multi-view isometric pixel art character sprites from text descriptions, ready for use in games.

---

## The Problem

We need to generate a character sprite sheet from a text description: multiple isometric views of the same character (front-left, back-right, etc.) with consistent proportions, palette, and style across all views. The output must be:

1. True pixel art (hard edges, limited palette, no anti-aliasing)
2. Isometric 3/4 top-down perspective (like SNES RPGs)
3. Transparent background (for compositing into games)
4. Consistent character across all views (only facing direction changes)
5. Individually extractable as separate sprite PNGs

---

## Prompt Engineering

### From Plain Prompts to JSON

**First attempt:** Plain natural language prompts — "draw a pixel art samurai facing 4 directions on a transparent background." This produced usable results but with inconsistent layouts, view placement, and style adherence. The model would sometimes arrange views vertically, sometimes diagonally, sometimes overlapping.

**What worked:** Moving to structured JSON prompts. Models respond much better to JSON because:
- Clear separation of concerns (views, style, background rules are discrete fields)
- Explicit per-view facing descriptions prevent ambiguity
- Structured layout instructions reduce hallucinated arrangements
- Rules can be enumerated without getting lost in prose

Our JSON prompt structure:
```json
{
  "image_type": "pixel_art",
  "style": "isometric",
  "purpose": "character_sprite_reference_sheet",
  "background": { "type": "...", "rule": "...", "instruction": "..." },
  "views": [ { "position": "...", "facing": "...", "description": "..." } ],
  "character": { "description": "...", "pose": "standing idle", "consistency_rule": "..." },
  "art_details": { "shading": "...", "outline": "...", "perspective": "...", ... },
  "layout": { "arrangement": "...", "spacing": "...", "centering": "..." }
}
```

**Key lesson:** For *generation* (text-to-image), JSON beats narrative. For *animation* (image editing), narrative beats JSON — the model needs freedom to interpret visual context.

### View Definitions

**4-direction mode (2 views):**
- Front-left (3/4 view, south-east facing) — face and chest visible
- Back-right (3/4 view, north-east facing) — back and top of head visible
- Remaining 2 directions derived by horizontal mirroring

**8-direction mode (5 views):**
- Back (north), back-right (NE), right (east), front-right (SE), front (south)
- Remaining 3 directions derived by mirroring

**Why these specific views?** Isometric RPGs need at minimum 4 directions. The 3/4 top-down angle (~30 degrees from above) is the standard for SNES/Genesis-era games (Final Fantasy Tactics, Tactics Ogre, Chrono Trigger). We generate the "right-facing" variants and mirror for "left-facing" — this is how classic games worked.

**Why 2 views for 4-dir, not 4?** Generating 2 unique views + mirroring is more reliable than asking the model for 4 views. The model maintains better consistency with fewer views, and mirroring guarantees symmetry.

### Art Style Rules

Critical prompt rules that significantly affect output quality:

1. **"1-pixel black (#000000) outline on ALL elements"** — Without this, models produce soft-edged, painterly output. The black outline constraint forces pixel art discipline.

2. **"No anti-aliasing — every edge is a hard pixel step"** — Models default to smoothing. Explicit prohibition is necessary.

3. **"Simple 2-3 tone stepped shading per color area"** — Prevents gradient fills that break the pixel art aesthetic.

4. **"max_colors: 16"** — Forces the model to think in terms of a limited palette, producing more cohesive sprites.

5. **Style references: "Final Fantasy Tactics, Tactics Ogre, Chrono Trigger"** — Concrete examples ground the model's interpretation better than abstract style descriptions.

---

## Provider: Gemini

We use **Gemini (gemini-3.1-flash-image-preview)** exclusively.

**Strengths:**
- Better pixel art generation quality — produces cleaner, more retro-looking output
- Cheaper per generation (~$0.01)
- Multimodal input — required for the canvas-based pipeline (reference image + prompt)
- Faster generation times
- `image_config` allows aspect ratio and output size control (`512`, `1K`, `2K`, `4K`)

**Weaknesses:**
- Cannot produce transparent backgrounds — requires chromakey + post-processing
- Chromakey sometimes bleeds into the sprite (especially green-tinted characters)
- Output size defaults to 1K unless explicitly configured via `image_config`

### Why not OpenAI?

OpenAI (gpt-image-1.5) was evaluated. It offered native alpha transparency (no background removal needed) and higher resolution output. However:
1. **No multimodal input** — can't send a reference canvas image, which the platform pipeline requires
2. **More expensive** per generation
3. **Over-details** sprites — ignores the 16-color constraint, produces too-complex output
4. **Simpler codebase** — one provider means less branching, fewer edge cases

The provider abstraction (`providers/base.py`) remains if someone wants to add OpenAI back.

---

## Background Handling

### The Transparency Problem

When we asked Gemini to produce a transparent background, it generated fake transparency — grey and white checkerboard patterns mimicking what transparency looks like in image editors. The model doesn't understand actual alpha channels; it renders what transparency *looks like* visually.

**The solution:** Ask for a solid color background instead, then remove it programmatically. We chose chromakey (solid green #00FF00 or blue #0000FF) because:

1. Pure green/blue are maximally distant from typical sprite colors
2. Standard chroma keying is a well-understood technique
3. It's easy to specify in prompts: "every non-sprite pixel must be exactly #00FF00"

**Green vs Blue chromakey:**
- Green (#00FF00) is the default — works for most characters
- Blue (#0000FF) is the fallback for green-skinned characters (goblins, orcs, plants) where green chromakey bleeds into the sprite
- Configurable via `--chromakey blue` or `PIXEL_MAGIC_CHROMAKEY_COLOR=blue`

### Background Removal Pipeline

We tried several approaches for removing the chromakey background:

1. **Simple color thresholding** (replace all green pixels with alpha) — leaves ugly halos because models anti-alias sprite edges against the background color
2. **Color-distance thresholding** (remove pixels within a color distance from green) — either eats into the sprite or misses fringe pixels, no good threshold exists
3. **rembg (U2-Net segmentation)** — neural network approach, much better edge quality but leaves residual color on edge pixels
4. **rembg + color-aware despill** — best results for chromakey removal, what we ship
5. **OpenAI Responses API with `background="transparent"`** — hybrid approach: Gemini generates on chromakey, then OpenAI edits the image with native transparent output. When it works, the results are excellent (clean alpha, no artifacts). But it's hit-or-miss — OpenAI sometimes modifies the character pixels, changes proportions, or produces inconsistent results between runs. Not reliable enough for a pipeline.

The two-stage pipeline we use:

**Stage 1: U2-Net Segmentation (rembg)**
- Neural network trained for salient object detection
- Produces a high-quality alpha mask that handles complex shapes and fine details
- Works regardless of background color — not limited to simple thresholding
- Much better edge quality than color-distance approaches

**Stage 2: Color-Aware Despill**
- rembg leaves residual chromakey color on edge pixels
- Identifies edge pixels: partially transparent + fully opaque within 3px of alpha boundary
- Green despill: clamps `G = min(G, max(R, B))` — removes green tint without affecting other colors
- Blue despill: clamps `B = min(B, max(R, G))`
- Preserves the sprite's actual colors while removing background contamination

**Key insight:** The despill formula `G = min(G, max(R, B))` means: "green channel should never exceed the maximum of the other two channels." This is aggressive enough to remove green fringe but safe enough to preserve naturally green elements (like a green hat or emerald).

---

## Sprite Extraction

### Why Not Fixed Grid Splitting?

AI models don't place views in a perfectly even grid. Views vary in:
- Size (some views show more of the character)
- Position (horizontal spacing is inconsistent)
- Separation (some views overlap or have artifacts between them)

Fixed grid splitting (divide width by N) fails because:
- Views aren't equally sized
- Cuts through sprites if spacing is uneven
- Can't handle unexpected artifact blobs

### Connected-Component Approach

We use scipy's `ndimage.label()` with 8-connectivity to find distinct blobs:

1. **Alpha mask** — binary image of non-transparent pixels
2. **Label connected components** — each contiguous region gets a unique ID
3. **Filter noise** — drop blobs < 0.5% of the largest blob's area
4. **Merge nearby blobs** — blobs within 8px are likely parts of the same sprite (e.g., a sword tip separated by 3px from the hand)
5. **Adaptive merge** — if we know the expected count (2 for 4-dir, 5 for 8-dir), progressively increase the merge distance until the count matches
6. **Sort left-to-right** — matches the prompt's view order

This handles all the edge cases: uneven spacing, stray pixels, separated accessories, oversized views.

---

## Pixel Art Resizing

### The Problem

AI-generated sprites are ~300-500px, rendered at model resolution. For game use, we need true pixel art at 32×32, 64×64, etc. The AI output *looks like* pixel art but isn't actually grid-aligned — pixels are slightly irregular, colors aren't perfectly flat, and edges have subtle anti-aliasing. It's "AI pixel art" not "real pixel art."

### First Attempt: Manual Resizing

We first tried writing our own resize pipeline: nearest-neighbor downscaling at various ratios, followed by color quantization. This produced mediocre results because the AI output's pixel grid doesn't align cleanly to any integer ratio. You get artifacts, misaligned edges, and color bleeding.

### Solution: proper-pixel-art Library

We found the [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) library which does exactly what we need — it converts "AI pixel art" to actual pixel art by detecting the underlying grid and resampling properly:

1. **Grid detection** — Canny edge detection finds pixel boundaries, morphological closing fills gaps, probabilistic Hough line transform identifies the grid spacing
2. **Color sampling** — For each cell in the detected grid, sample the dominant color using offset binning (dual-grid approach that avoids boundary artifacts)
3. **Palette quantization** (optional) — PIL MAXCOVERAGE reduces to N colors with dithering disabled
4. **Nearest-neighbor resize** — Scale to target size preserving hard edges
5. **Center on canvas** — Place on transparent NxN canvas

**Why this works better than naive NEAREST:** The library detects the *actual* pixel grid in the AI output (which might be 9.4 model pixels per intended game pixel), then resamples one true color per cell. This eliminates the artifacts that come from downscaling at arbitrary non-integer ratios.

**Valid target sizes:** 16, 32, 48, 64, 96, 128, 256

---

## Canvas-Based Generation with Platforms (Current Default)

Platform-guided generation is now the **default** for `pixel-magic generate`. Text-only generation is available via `--no-platform` for maximum creative freedom.

### Pipeline

1. **Build a canvas** with empty isometric platforms in a grid on chromakey background (no text labels — see "Labels vs Quality" below)
2. **Send canvas + structured JSON prompt** to Gemini (multimodal) — the prompt describes which platform position gets which facing direction
3. **Second pass** removes platforms
4. **Flood-fill chromakey removal + despill** removes remaining chromakey background
5. **Extract sprites** via connected-component analysis

### Why platforms work for generation

- Establishes the isometric ground plane — model maintains consistent 3/4 top-down angle across all views
- Tile size communicates character footprint — a 2×2 platform tells the model this is a larger creature
- Grid layout matches Gemini's supported aspect ratios — better output quality
- Pixelated platform rendering reinforces the pixel art aesthetic (see "Platform rendering" below)

### Canvas sizing: top-down approach

**Evolution:**
1. **v1 — Bottom-up:** Start from tile size → compute slot size → snap canvas to nearest Gemini ratio. Problem: final canvas dimensions were unpredictable, and the ratio-snapping padding created awkward empty regions.
2. **v2 — Top-down (current):** Start from a fixed Gemini output size, divide into cells, fit platforms inside. Canvas dimensions are always exact Gemini output pixels — no snapping or padding needed.

**How it works:**
1. Pick a fixed canvas size based on view count and tile footprint (see table below)
2. Divide the canvas into cells: `cell_w = canvas_w / cols`, `cell_h = canvas_h / rows`
3. Size the platform to fill `platform_fill` (default 55%) of the cell width
4. Back-solve `tile_width = target_platform_width / grid_size` so the platform fits the budget
5. Position the platform vertically using character height estimation (see below)

**Canvas size mapping:**

| Views | Tiles | Size | Ratio | Pixels |
|-------|-------|------|-------|--------|
| 2 (4-dir) | 1, 4 | 1K | 4:3 | 1024×768 |
| 2 (4-dir) | 9 | 2K | 16:9 | 2048×1152 |
| 5 (8-dir) | any | 2K | 16:9 | 2048×1152 |

Rule: `image_size` = longest edge in pixels, ratio determines the short edge. E.g., 1K + 4:3 = 1024×768.

### Grid layout

- 4-dir (2 views): side by side in one row (2×1)
- 8-dir (5 views): 3 top, 2 bottom centered (3×2)

### Platform placement: the centering problem

Placing the platform in the center of a cell seems natural, but when the character is drawn ON the platform, the character's head extends upward and may clip the top of the cell. Conversely, placing the platform at the very bottom wastes vertical space with an ocean of green above.

**Solution:** Estimate the character height, then vertically center the entire character+platform composite unit in the cell.

```
Cell layout (conceptual):
┌──────────────────┐
│   [headroom]     │
│   ┌──────────┐   │  ← estimated head position
│   │ character │   │
│   │   body    │   │
│   └──feet────┘   │  ← feet on platform surface
│   ╱────────────╲ │
│  │   platform   ││
│  ╲──────────────╱│
│   [padding]      │
└──────────────────┘
```

**The math:**

1. **Estimate character height:** `char_height = platform_width × char_ratio`
   - `char_ratio` (default 1.2) = character is 1.2× as tall as the platform is wide
   - Using platform width as reference keeps proportions consistent across tile counts (platform width ≈ `cell_w × platform_fill` regardless of grid_size)
2. **Find the feet point:** Character feet land at the center of the diamond top face
   - `diamond_h = grid_size × tile_width / 2`
   - `feet_offset = diamond_h / 2` (y from top of platform image)
3. **Compute composite height:** `composite_h = char_height + (platform_height - feet_offset)`
   - Everything from the character's head down to the platform's bottom edge
4. **Center it:** `top_margin = (cell_h - composite_h) / 2`
   - Platform y = `top_margin + char_height - feet_offset`
5. **Clamp:** If composite exceeds cell height, reduce char_height to fit with minimal margins

**`--char-ratio` tuning:**
- Default 1.2 works for typical isometric RPG sprites
- Lower (0.8–1.0) for squat/chibi characters — pushes platform higher
- Higher (1.5–2.0) for tall tactical RPG sprites — pushes platform lower
- The model isn't bound by this estimate — it controls platform placement, not character size

### Labels vs Quality — A Critical Finding

**Problem:** When text labels (direction names like "front-left", "back-right") were rendered on the canvas, Gemini's output quality degraded significantly. The generated characters looked like mobile game illustrations rather than pixel art — smoother gradients, anti-aliased edges, blended green backgrounds. Removing labels restored clean pixel art quality.

**Why this happens:** Gemini matches the visual style of the input image. Text on the canvas — even pixel-style fonts — signals "this is a UI/diagram" rather than "this is pixel art." The model shifts its output style accordingly. Without labels, the pixelated platforms alone set the visual tone, and the prompt's pixel art instructions fully control the output style.

**The evolution:**
1. **v1 — Bitmap pixel text:** Custom 3×5 pixel bitmaps for each character. Hard pixel edges but limited readability.
2. **v2 — System font with anti-aliasing:** `ImageFont.load_default()` — readable but anti-aliased edges bled into the chromakey background and further degraded pixel art quality.
3. **v3 — Pixelify Sans with alpha thresholding:** Google's pixel-art font rendered with alpha snapped to 0/255 (no blending). Better style fit, but still degraded output.
4. **v4 — No labels (current):** Labels removed entirely. Facing directions communicated through position-based descriptions in the prompt ("left platform: front-left facing"). Best output quality.

**Key insight:** For generation, Gemini doesn't need visual text labels to follow directions — structured prompt descriptions with grid positions work just as well. This is different from animation, where a reference frame already establishes the visual style (see note below).

**Animation canvas labels are fine:** The animation pipeline uses frame numbers on the canvas, and these don't cause the same quality degradation. The likely reason: the animation canvas already contains a reference frame (a fully-rendered pixel art character), which dominates the style signal. The small frame numbers are noise against a strong pixel art example. Generation canvases have no reference frame — only platforms — so any text has outsized influence on the perceived style.

**Future fallback:** If facing directions become unreliable without labels, small pixel-art arrows drawn on the platforms (pointing in the facing direction) could provide visual cues without the text-based style degradation. Not currently needed — position-based prompt descriptions work well.

### Platform rendering

Platforms are composited from individual tiles rendered at a small "native" pixel-art resolution, then scaled up with nearest-neighbor interpolation to create chunky, unmistakably pixel-art-looking platforms.

**Rendering evolution:**
1. **v1 — Tile pasting at canvas resolution:** Created individual isometric tiles at the target canvas size and pasted them in a diamond grid. The tiles were smooth polygons drawn at high resolution — they looked like clean 3D renders, not pixel art. This caused Gemini to generate smooth, non-pixel-art characters to match.
2. **v2 — Unified block with grid lines:** Drew one large isometric block with grid division lines. Cleaner visually, but same smooth-render problem — Gemini matched the smooth style.
3. **v3 — Native resolution + NEAREST upscale (current):** Draw tiles at a small native resolution based on `target_res` (e.g., 24px wide for 64×64 sprites), then scale up with `Image.NEAREST`. Every pixel becomes a visible block. This primes Gemini to generate chunky pixel art.

**How native resolution scaling works:**
- `native_tile_w = target_res × 3/8` (e.g., 64 → 24px, 128 → 48px, 256 → 96px)
- Draw the platform at native resolution (tiny, hard pixels)
- Scale factor = `round(target_platform_width / native_platform_width)`
- `platform.resize((w × scale, h × scale), Image.NEAREST)` — pure nearest-neighbor, no smoothing
- Lower `target_res` = chunkier pixels = stronger pixel art signal

**Platform sizing:**
- `platform_fill` (default 0.55) controls what fraction of the cell width the platform occupies
- Platform width ≈ `cell_w × 0.55` regardless of grid_size — consistent visual weight

### Prompt format for canvas generation

**Critical finding:** The canvas prompt must use the same structured JSON format as the text-only prompt. An earlier version used free-form narrative text for the canvas prompt while the text-only prompt used JSON. The text-only prompt consistently produced better pixel art. Switching the canvas prompt to JSON brought quality closer to parity.

Key JSON fields that affect quality:
- `"target_resolution_per_view": "64x64"` — tells Gemini the intended pixel density, crucial for pixel art discipline
- `"background.type": "chromakey"` (not "transparent") — avoids confusing the model about background handling
- `"style_reference"` — concrete game references (Final Fantasy Tactics, etc.) ground the output style
- `"platform_position"` per view — spatial descriptions ("left platform", "top-right platform") replace visual labels

### Text-only fallback (`--no-platform`)

Disables the platform canvas pipeline entirely. Uses a JSON-structured prompt with view definitions, style rules, and layout instructions — no reference image sent. This gives the model more creative freedom but less perspective control. Useful when platforms interfere with the character design (e.g., flying characters, characters that don't stand on ground)

### Verification Snapshot — March 27, 2026

Several manual validation runs were used to check whether the current pipeline still behaves as described above.

**Observed behavior:**
- Platform-guided generation remained stable across small, medium, and oversized character footprints. The expected number of views were extracted in each validated platform case.
- Text-only generation with `--directions 4` usually behaved correctly. In repeated validation, the common result was the intended 2-view output.
- At least one text-only outlier returned extra visible poses even though the prompt requested only 2 isometric views.

**What this means:**
- The text-only 4-dir prompt itself is correct. It still requests **2** isometric views (`front-left` and `back-right`) and relies on mirroring for the other directions.
- The extra-pose failure mode appears to be **model noncompliance / drift**, not a prompt-format bug.
- The recovery path is still brittle when Gemini freelances. In the observed outlier, connected-component analysis found 4 valid sprite boxes, but the adaptive merge logic increased the merge gap from 8px to 16px in order to force the count back toward the expected 2. At 16px, all 4 poses merged into a single large crop. This is a pipeline weakness even if the underlying cause is occasional model drift.
- Large multi-tile platform runs completed successfully, but the cleanup pass was noticeably slower than smaller runs.

---

## Key Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| Provider | Gemini only | Cheaper, better pixel art, multimodal input required for canvas pipeline |
| Default generation | Platform-guided canvas | Perspective grounding, tile footprint communication |
| Canvas sizing | Top-down (fixed Gemini output → divide → fit) | Predictable dimensions, no ratio-snapping artifacts |
| Platform placement | Centered char+platform composite | Prevents head clipping and wasted space |
| Platform rendering | Individual tiles at native res, NEAREST upscale | Chunky pixels prime Gemini for pixel art style |
| Canvas labels | None — directions in prompt only | Text on canvas degrades pixel art quality (see Labels vs Quality) |
| Prompt format | JSON for both text-only and canvas generation | Structured format produces better pixel art; narrative for animation only |
| Background | Chromakey + flood fill + despill | Binary alpha, fewer dependencies, preserves pixel edges |
| Extraction | Connected-component analysis | Handles inconsistent model placement |
| Resizing | Grid detection + nearest-neighbor | Preserves true pixel grid |
| View count | 2 views (4-dir), 5 views (8-dir) | Fewer views = better consistency, mirror the rest |
| Color limit | 16 by default | Forces model into retro pixel art discipline |
| Raw output | Always saved untouched | Debugging + comparison baseline |

---

## Cost Reference

| Provider | Model | Cost/generation | Quality |
|----------|-------|----------------|---------|
| Gemini | gemini-3.1-flash | ~$0.01 (single pass), ~$0.02 (with platform cleanup) | Clean pixel art, needs bg removal |

OpenAI (gpt-image-1.5) was evaluated and removed. It offered native alpha transparency but was more expensive, sometimes over-detailed sprites, and couldn't accept reference images for the canvas pipeline. The provider abstraction (`providers/base.py`) remains if someone wants to add it back.

---

## Post-Processing Pipeline (March 2026)

After extraction, sprites go through cleanup and outline processing before resize. See `docs/research/background-removal.md` for detailed research on background removal approaches.

### Background Removal: Flood Fill Chromakey

Replaced rembg (U2-Net neural network) with flood-fill-from-edges chromakey removal. rembg produced soft alpha (98.7% of pixels semi-transparent) that destroyed pixel art quality. The flood fill approach uses channel-ratio green detection (`G > max(R,B) + 30`) with 4-connected BFS from image borders, producing binary alpha by construction. Saves ~92MB of dependencies (onnxruntime, scikit-image, pymatting).

### Outline Strategy: Strip and Re-Add

The AI's outlines are inconsistent (varying thickness, grey instead of black, sometimes missing). Rather than trying to reinforce them through downscaling, we:

1. **Strip** the outermost dark boundary pixels (max_ch < 35, spread < 20) in the high-res sprite — single pass only, to avoid eating into dark body regions
2. **Pixelate** the clean body via proper-pixel-art (grid detection works better without noisy dark edge pixels)
3. **Re-add** a guaranteed uniform 1px black outline at the target size via morphological erosion

This produces 100% black boundary coverage at both 64x64 and 128x128, compared to 69% at 64x64 with the old approach.

**Future work:** Internal outlines (between arm and body, armor pieces) still survive pixelation naturally but have the same quality issues. The strip+re-add approach could be extended to detect and normalize internal dark linear features.

---

## What Could Be Improved

1. **Internal outline normalization** — Detect dark linear features between distinct color regions, strip them, re-add clean 1px dark lines at color boundaries after pixelation
2. **Multi-pass generation** — Generate each view separately for better consistency, then composite
3. **Style transfer from reference** — Use an existing sprite as a style reference for new characters
4. **Automatic quality evaluation** — Detect and retry when views are inconsistent or malformed
5. **Palette extraction + enforcement** — Extract palette from frame 1, enforce on subsequent generations
6. **Adaptive char_ratio** — Auto-detect character proportions from the first successful generation to improve placement on subsequent runs
7. **Direction arrows on platforms** — If position-based prompt descriptions prove unreliable for facing directions, draw small pixel-art arrows on platforms pointing in the intended facing direction. Visual cue without the text-based quality degradation. Not currently needed.
8. **Resolution-aware font scaling** — The Pixelify Sans font (in `assets/fonts/`) is available for UI/overlay use. Tiny5 and Jacquarda Bastarda 9 are also available for different aesthetic needs. These should NOT be rendered on generation canvases (see Labels vs Quality) but can be used for animation frame numbers or post-processing overlays.
9. **Safer extraction fallback when the model returns extra valid views** — If the prompt expects 2 views but Gemini returns 4 clearly separated poses, do not blindly merge until the count drops. Prefer reporting the mismatch, saving all candidate crops, or using layout-aware grouping before aggressive merging.

---

## Tile Generation Notes — March 28, 2026

The `pixel-magic tile` command uses the same broad canvas-first idea as the character pipeline, but the constraints are different enough that the lessons are not identical.

### Why tile canvases keep text labels

Character generation dropped canvas labels because the labels degraded pixel art quality and the prompt could still bind views by position (`left platform`, `right platform`, etc.). Tile generation is different:

- Tile slots often differ only by material, not silhouette.
- Custom sets (`mud`, `brick`, `poison swamp`) do not have a predefined spatial meaning.
- Removing the label text from the input canvas caused more slot drift than it saved in quality.

Current choice: **keep the text labels on the tile reference canvas** and strip them in the cleanup pass. This favors correct slot-to-material binding over a perfectly clean reference image.

### Why tile chromakey defaults to pink

The tile pipeline originally inherited the repo-wide chromakey defaults:

- **Green** preserved water/ice but erased grass-heavy tiles during cleanup.
- **Blue** preserved grass but erased water-heavy and ice-heavy tiles.

Observed failures:
- `grass` and `dense grass` were partially or fully eaten on green chromakey.
- `ice`, `frozen water`, and `water puddle` were partially eaten on blue chromakey.

Current choice: **tile defaults to vivid pink (`#FF00FF`)** because natural terrain almost never uses saturated magenta as a dominant surface color. Pink chromakey is now supported by flood-fill background removal, despill, and cleanup.

### Custom sets and empty-cell hallucinations

The first custom tile layout used a generic grid search. For a 3-tile custom set, that produced a `2x2` layout with one empty cell. Gemini often treated the unlabeled empty space as permission to invent extra tiles, which then bled into extraction and produced broken custom outputs.

Current choice:
- 3-tile custom sets use a **`3x1` layout**
- the prompt explicitly says **generate exactly the labeled tiles**
- any unlabeled or outline-free space must remain solid chromakey background

This materially reduced hallucinated extra rows in manual validation.

### Remaining weaknesses in the tile pipeline

These are still real even after the pink/default and `3x1` custom fixes:

1. **Material quality is still model-driven** — the pipeline now preserves more valid pixels, but it cannot force a good aesthetic result every run.
2. **Labels remain a tradeoff** — text improves slot binding, but it still adds visual clutter. A future iteration may replace full material names on-canvas with small numeric IDs plus prompt-side mapping.
3. **Cleanup is conservative** — it removes obvious guide/text artifacts, but faint remnants can still survive in some runs. `raw.png` and `sheet_cleaned.png` remain essential debugging artifacts.
4. **Surface-specific prompt tuning is still open** — liquids, transparent ice, swampy tiles, and glossy materials likely need dedicated wording to improve consistency.
