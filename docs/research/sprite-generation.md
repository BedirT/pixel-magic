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

1. **Build a canvas** with empty isometric platforms in a grid, each labeled with its facing direction (e.g. "FRONT LEFT", "BACK RIGHT")
2. **Send canvas + prompt** to Gemini (multimodal) — the model sees the platforms and draws characters on them
3. **Second pass** removes platforms and direction labels
4. **rembg + despill** removes remaining chromakey background
5. **Extract sprites** via connected-component analysis

### Why platforms work for generation

- Establishes the isometric ground plane — model maintains consistent 3/4 top-down angle across all views
- Direction labels are unambiguous — model knows exactly which way each view should face
- Tile size communicates character footprint — a 2×2 platform tells the model this is a larger creature
- Grid layout matches Gemini's supported aspect ratios — better output quality

### Grid layout

- 4-dir (2 views): side by side in one row
- 8-dir (5 views): 3 top, 2 bottom centered
- Canvas padded to nearest Gemini ratio (1:1, 5:4, 4:3, 3:2, 16:9)

### Platform rendering

Platforms are drawn as unified isometric blocks with tile division grid lines — not by pasting individual tiles. This eliminates visible seams between tiles.

**Evolution:**
1. **v1 — Tile pasting:** Created individual isometric tiles and pasted them in a diamond grid. This produced visible seam artifacts where tiles overlapped, and tile outlines doubled up at edges.
2. **v2 — Unified block with grid lines:** Draws one large isometric block (top face, left face, right face as filled polygons), then overlays tile division lines on the top face only. Grid lines are drawn by linear interpolation along the diamond edges. Much cleaner rendering.

**Tile scaling for multi-tile grids:**
- Grid sizes > 1 scale down the individual tile width to prevent platforms from dominating the canvas
- Scale factors: 1-tile = 1.0×, 2×2 = 0.7×, 3×3 = 0.45× of the base `tile_width` (256px)
- Slot dimensions stay based on the base tile_width — only the platform inside shrinks
- This keeps canvas sizes manageable while still giving Gemini the visual cue of a larger floor area

**Character placement (`--char-ratio`):**
- `char_ratio` (default 1.2) controls the space above the platform reserved for the character
- Character height = `tile_width × char_ratio`
- Character feet positioned at the center of the platform's diamond top face
- Higher ratio = more headroom, lower ratio = character fills more of the slot

### Text-only fallback (`--no-platform`)

Disables the platform canvas pipeline entirely. Uses a JSON-structured prompt with view definitions, style rules, and layout instructions — no reference image sent. This gives the model more creative freedom but less perspective control. Useful when platforms interfere with the character design (e.g., flying characters, characters that don't stand on ground)

---

## Key Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| Provider | Gemini only | Cheaper, better pixel art, multimodal input required for canvas pipeline |
| Default generation | Platform-guided canvas | Perspective grounding, direction labels, tile footprint communication |
| Prompt format | JSON (text-only generation), Narrative (platform generation + animation) | JSON for structure, narrative for creative freedom with visual context |
| Background | Chromakey + rembg + despill | Neural segmentation > thresholding |
| Extraction | Connected-component analysis | Handles inconsistent model placement |
| Resizing | Grid detection + nearest-neighbor | Preserves true pixel grid |
| View count | 2 views (4-dir), 5 views (8-dir) | Fewer views = better consistency, mirror the rest |
| Color limit | 16 by default | Forces model into retro pixel art discipline |
| Platform rendering | Unified block + grid lines | Cleaner than tile pasting, no seam artifacts |
| Raw output | Always saved untouched | Debugging + comparison baseline |

---

## Cost Reference

| Provider | Model | Cost/generation | Quality |
|----------|-------|----------------|---------|
| Gemini | gemini-3.1-flash | ~$0.01 (single pass), ~$0.02 (with platform cleanup) | Clean pixel art, needs bg removal |

OpenAI (gpt-image-1.5) was evaluated and removed. It offered native alpha transparency but was more expensive, sometimes over-detailed sprites, and couldn't accept reference images for the canvas pipeline. The provider abstraction (`providers/base.py`) remains if someone wants to add it back.

---

## What Could Be Improved

1. **Multi-pass generation** — Generate each view separately for better consistency, then composite
2. **Style transfer from reference** — Use an existing sprite as a style reference for new characters
3. **Automatic quality evaluation** — Detect and retry when views are inconsistent or malformed
4. **Palette extraction + enforcement** — Extract palette from frame 1, enforce on subsequent generations
5. **Platform grid line alignment** — Grid lines on the top face of multi-tile platforms need to properly extend down the side faces for visual consistency (currently top-face only)
