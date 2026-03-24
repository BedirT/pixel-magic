# Generation Process Flowchart

## Overview

pixel-magic generates multi-view isometric pixel art character sprites using AI image generation models. The pipeline takes a text description and produces a sprite reference sheet with consistent character views across multiple directions.

## Process Flow

```
                        ┌─────────────────┐
                        │   CLI Invocation │
                        │  pixel-magic     │
                        │    generate      │
                        └────────┬────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Load Configuration    │
                    │                         │
                    │  1. Parse CLI arguments │
                    │  2. Load .env settings  │
                    │  3. Resolve provider    │
                    │     (CLI flag > .env)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Build JSON Prompt     │
                    │                         │
                    │  Structured JSON with:  │
                    │  - Character description│
                    │  - View definitions     │
                    │  - Art style rules      │
                    │  - Background rules     │
                    │  - Layout instructions  │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                                     │
   ┌──────────▼──────────┐             ┌────────────▼───────────┐
   │   OpenAI Provider   │             │   Gemini Provider      │
   │                     │             │                        │
   │  Model: gpt-image-  │             │  Model: gemini-3.1-    │
   │         1.5         │             │   flash-image-preview  │
   │                     │             │                        │
   │  Background:        │             │  Background:           │
   │    native alpha     │             │    chromakey green      │
   │    transparency     │             │    (#00FF00)            │
   │                     │             │                        │
   │  Output: base64     │             │  Output: inline        │
   │          PNG        │             │          binary        │
   │                     │             │                        │
   │  Retry: 3 attempts  │             │  Retry: 3 attempts     │
   │  Delay: 1s base     │             │  Delay: 5s base        │
   │  Backoff: 2x        │             │  Backoff: 2x           │
   └──────────┬──────────┘             └────────────┬───────────┘
              │                                     │
              └──────────────────┬──────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Save Raw Output       │
                    │                         │
                    │  output/<name>/raw.png   │
                    │  (untouched model output)│
                    └────────────┬────────────┘
                                 │
                         ┌───────▼───────┐
                         │ Provider is   │
                         │   Gemini?     │
                         └───┬───────┬───┘
                          yes│       │no
                             │       │
              ┌──────────────▼──┐    │
              │  Background     │    │
              │  Removal        │    │
              │                 │    │
              │  1. rembg       │    │
              │     (U2-Net     │    │
              │     segmentation│    │
              │     model)      │    │
              │                 │    │
              │  2. Green       │    │
              │     despill     │    │
              │     (clamp G to │    │
              │     max(R,B) on │    │
              │     edge pixels)│    │
              │                 │    │
              │  output/<name>/ │    │
              │    sheet.png    │    │
              └────────┬───────┘    │
                       │            │
                       └──────┬─────┘
                              │
                    ┌─────────▼──────────────┐
                    │   Sprite Extraction     │
                    │                         │
                    │  1. Alpha mask          │
                    │     (non-transparent    │
                    │      pixels)            │
                    │                         │
                    │  2. Connected-component │
                    │     labeling            │
                    │     (8-connectivity)    │
                    │                         │
                    │  3. Noise filtering     │
                    │     (drop tiny blobs)   │
                    │                         │
                    │  4. Proximity merging   │
                    │     (join nearby parts  │
                    │      of same sprite)    │
                    │                         │
                    │  5. Adaptive merge      │
                    │     (if expected count  │
                    │      known, increase    │
                    │      gap until match)   │
                    │                         │
                    │  6. Sort left-to-right  │
                    │     & crop with padding │
                    │                         │
                    │  output/<name>/views/   │
                    │    <direction>.png      │
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼─────────┐
                    │      Done         │
                    └───────────────────┘
```

## Stage Details

### 1. CLI Invocation

The user runs `pixel-magic generate` with required `--name` and `--description` flags, plus optional overrides for directions, provider, style, resolution, colors, and palette hints.

### 2. Configuration Resolution

Settings are resolved in priority order:
1. CLI arguments (highest priority)
2. `.env` file values (prefixed with `PIXEL_MAGIC_`)
3. Built-in defaults (lowest priority)

### 3. JSON Prompt Construction

The prompt is built as structured JSON, not prose. This gives models a clear, parseable specification. The prompt includes:

- **View definitions** — 2 views for 4-direction mode (front-left, back-right), 5 views for 8-direction mode (back, back-right, right, front-right, front)
- **Background rules** — OpenAI gets transparency instructions; Gemini gets chromakey green (#00FF00) instructions
- **Art style** — pixel density, shading rules, black outline enforcement, anti-aliasing prohibition, perspective angle, resolution target, color limit
- **Layout** — horizontal row arrangement with generous spacing between views
- **Consistency rule** — all views must depict the exact same character with only facing direction changing

### 4. Image Generation

A single API call generates all views in one composite image. This ensures visual consistency across directions — the model sees the whole sheet as one coherent piece.

- **OpenAI** — returns base64-encoded PNG with native alpha transparency
- **Gemini** — returns inline binary image data with solid green (#00FF00) chromakey background

Both providers implement exponential backoff retry logic for transient API errors.

### 5. Raw Output Save

The model's output is saved as-is to `output/<name>/raw.png` with zero processing. This preserves the original for debugging and comparison.

### 6. Background Removal (Gemini only)

Since Gemini cannot produce transparent backgrounds, a two-stage post-processing pipeline removes the green chromakey:

**Stage A: U2-Net Segmentation (rembg)**
- A pre-trained U2-Net neural network segments foreground (sprite) from background
- Produces a clean alpha mask that handles complex shapes, fine details, and semi-transparent areas
- Much more accurate than simple color-distance thresholding

**Stage B: Green Despill**
- rembg leaves residual green color bleed on edge pixels where the model anti-aliased against the green background
- The despill pass identifies edge pixels: partially transparent pixels + fully opaque pixels within 3px of the alpha boundary
- For these pixels, the green channel is clamped: `G = min(G, max(R, B))`
- This neutralizes green tinting without affecting non-green sprite colors

The cleaned result is saved to `output/<name>/sheet.png`.

### 7. Sprite Extraction

The composite sheet (whether from OpenAI with native transparency or Gemini after background removal) is split into individual view PNGs using connected-component analysis on the alpha channel.

**Step A: Alpha Masking** — all non-transparent pixels (alpha > 0) form a binary mask.

**Step B: Connected-Component Labeling** — `scipy.ndimage.label` with 8-connectivity identifies distinct blobs of non-transparent pixels.

**Step C: Noise Filtering** — blobs smaller than 0.5% of the largest blob's area are discarded (stray pixels, artifacts).

**Step D: Proximity Merging** — blobs within 8px of each other are merged into a single bounding box. This handles cases where parts of the same character (e.g., a sword tip) are separated by a few transparent pixels.

**Step E: Adaptive Merge** — if the expected view count is known (2 for 4-dir, 5 for 8-dir) and too many blobs remain, the merge gap is progressively increased (8px → 16px → 24px → ...) until the count matches.

**Step F: Sort & Crop** — merged blobs are sorted left-to-right (matching the prompt's view order) and cropped with 2px padding. Each sprite is saved with its direction label (`front_left.png`, `back_right.png`, etc.).

## Output Structure

```
output/
└── <character-name>/
    ├── raw.png      # Untouched model output (always saved)
    ├── sheet.png    # Background-removed version (Gemini only)
    └── views/       # Individual extracted sprites
        ├── front_left.png
        ├── back_right.png
        └── ...
```
