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

### JSON vs Narrative Prompts

**Tried:** Both narrative prose prompts and structured JSON prompts for character sheet generation.

**Result:** JSON prompts produce more consistent, structured output. Models respond well to JSON because:
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

## Provider Comparison

### OpenAI (gpt-image-1.5)

**Strengths:**
- Native alpha transparency — no background removal needed
- Higher resolution output (~1024px)
- More literal prompt following — JSON structure is respected closely

**Weaknesses:**
- More expensive per generation
- Can over-detail sprites (too many colors, too complex)
- Sometimes ignores the "16 colors" constraint

**Best for:** High-detail character sheets where you want maximum fidelity and can accept more colors.

### Gemini (gemini-3.1-flash-image-preview)

**Strengths:**
- Cheaper per generation
- Better at pixel art style — produces cleaner, more retro output
- Multimodal input — can accept reference images for animation
- Faster generation times
- `image_config` allows aspect ratio and output size control

**Weaknesses:**
- Cannot produce transparent backgrounds — requires chromakey + post-processing
- Chromakey sometimes bleeds into the sprite (especially green-tinted characters)
- Output size defaults to 1K unless explicitly configured

**Best for:** Pixel art sprites, animation (multimodal), cost-sensitive batch generation.

### Why We Use Both

`generate` command supports both providers via `--provider`. Gemini is the default for the `animate` command because it's the only provider supporting multimodal input (reference image + prompt).

---

## Background Handling

### The Chromakey Problem

Gemini can't produce transparent backgrounds. It generates sprites on a solid colored background. We chose chromakey (solid green #00FF00 or blue #0000FF) because:

1. Pure green/blue are maximally distant from typical sprite colors
2. Standard chroma keying is a well-understood technique
3. It's easy to specify in prompts: "every non-sprite pixel must be exactly #00FF00"

**Green vs Blue chromakey:**
- Green (#00FF00) is the default — works for most characters
- Blue (#0000FF) is the fallback — use for green-skinned characters (goblins, orcs, plants)
- Configurable via `--chromakey blue` or `PIXEL_MAGIC_CHROMAKEY_COLOR=blue`

### Background Removal Pipeline

Simple color thresholding (replace all green pixels with alpha) doesn't work because:
- Models anti-alias sprite edges against the chromakey color
- Semi-transparent fringe pixels contain a mix of sprite + background color
- Hard thresholding leaves visible halos or eats into the sprite

Our two-stage pipeline:

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

AI-generated sprites are ~300-500px, rendered at model resolution. For game use, we need true pixel art at 32×32, 64×64, etc. Naive downscaling (bilinear/bicubic) blurs everything — pixel art needs nearest-neighbor, but you need to know the underlying pixel grid first.

### Our Approach (proper-pixel-art library)

1. **Grid detection** — Canny edge detection finds pixel boundaries, morphological closing fills gaps, probabilistic Hough line transform identifies the grid spacing
2. **Color sampling** — For each cell in the detected grid, sample the dominant color using offset binning (dual-grid approach that avoids boundary artifacts)
3. **Palette quantization** (optional) — PIL MAXCOVERAGE reduces to N colors with dithering disabled
4. **Nearest-neighbor resize** — Scale to target size preserving hard edges
5. **Center on canvas** — Place on transparent NxN canvas

**Why not just resize with NEAREST?** Because the AI output isn't aligned to a pixel grid. A 300px sprite with an underlying 32px grid has ~9.4 model pixels per game pixel. NEAREST sampling at arbitrary ratios produces artifacts. Detecting the actual grid first ensures clean downscaling.

**Valid target sizes:** 16, 32, 48, 64, 96, 128, 256

---

## Key Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| Prompt format | JSON (generation), Narrative (animation) | JSON for structure, narrative for creative freedom |
| Default provider | Gemini | Cheaper, better pixel art, multimodal |
| Background | Chromakey + rembg + despill | Neural segmentation > thresholding |
| Extraction | Connected-component analysis | Handles inconsistent model placement |
| Resizing | Grid detection + nearest-neighbor | Preserves true pixel grid |
| View count | 2 views (4-dir), 5 views (8-dir) | Fewer views = better consistency, mirror the rest |
| Color limit | 16 by default | Forces model into retro pixel art discipline |
| Raw output | Always saved untouched | Debugging + comparison baseline |

---

## Cost Reference

| Provider | Model | Cost/generation | Quality |
|----------|-------|----------------|---------|
| OpenAI | gpt-image-1.5 | ~$0.02-0.08 | High detail, sometimes over-detailed |
| Gemini | gemini-3.1-flash | ~$0.01 | Clean pixel art, needs bg removal |

---

## What Could Be Improved

1. **Higher-resolution base sprites** — 256×256 base instead of 64×64 for more detail per view
2. **Multi-pass generation** — Generate each view separately for better consistency, then composite
3. **Style transfer from reference** — Use an existing sprite as a style reference for new characters
4. **Automatic quality evaluation** — Detect and retry when views are inconsistent or malformed
5. **Palette extraction + enforcement** — Extract palette from frame 1, enforce on subsequent generations
