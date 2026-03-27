# Generation Process Flowchart

## Overview

pixel-magic generates multi-view isometric pixel art character sprites using Gemini image generation. The default pipeline builds a canvas with labeled isometric platforms, Gemini fills in characters, platforms are removed in a cleanup pass. An alternative text-only mode (`--no-platform`) uses JSON-structured prompts without visual references.

## Process Flow

```
                        ┌──────────────────┐
                        │   CLI Invocation  │
                        │  pixel-magic      │
                        │    generate       │
                        └────────┬─────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Load Configuration    │
                    │                         │
                    │  1. Parse CLI arguments │
                    │  2. Load .env settings  │
                    │  3. Resolve chromakey   │
                    │     (CLI flag > .env)   │
                    └────────────┬────────────┘
                                 │
                       ┌─────────▼─────────┐
                       │  --no-platform?   │
                       └───┬───────────┬───┘
                        yes│           │no (default)
                           │           │
              ┌────────────▼──┐  ┌─────▼────────────────┐
              │  Text-Only    │  │  Build Platform       │
              │  Pipeline     │  │  Canvas               │
              │               │  │                       │
              │  JSON prompt  │  │  1. Create isometric  │
              │  with views,  │  │     platforms per     │
              │  style rules, │  │     --tiles (1/4/9)   │
              │  chromakey    │  │  2. Arrange in grid   │
              │  background   │  │     with direction    │
              │               │  │     labels            │
              │  generate()   │  │  3. Pad to Gemini     │
              │               │  │     aspect ratio      │
              │               │  │                       │
              │               │  │  canvas_input.png     │
              │               │  └─────────┬────────────┘
              │               │            │
              │               │  ┌─────────▼────────────┐
              │               │  │  Gemini Pass 1:      │
              │               │  │  Fill Characters      │
              │               │  │                       │
              │               │  │  canvas + narrative   │
              │               │  │  prompt → Gemini      │
              │               │  │  (multimodal)         │
              │               │  │                       │
              │               │  │  raw.png              │
              │               │  └─────────┬────────────┘
              │               │            │
              │               │  ┌─────────▼────────────┐
              │               │  │  Gemini Pass 2:      │
              │               │  │  Remove Platforms     │
              │               │  │                       │
              │               │  │  Strip platforms +    │
              │               │  │  labels, replace with │
              │               │  │  chromakey fill       │
              │               │  │                       │
              │               │  │  sheet_cleaned.png    │
              └───────┬───────┘  └─────────┬────────────┘
                      │                    │
                      └────────┬───────────┘
                               │
                    ┌──────────▼─────────────┐
                    │   Background Removal    │
                    │                         │
                    │  1. rembg (U2-Net       │
                    │     segmentation model) │
                    │                         │
                    │  2. Color-aware despill  │
                    │     (clamp chromakey     │
                    │     channel on edge px)  │
                    │                         │
                    │  output/<name>/sheet.png │
                    └──────────┬─────────────┘
                               │
                    ┌──────────▼─────────────┐
                    │   Sprite Extraction     │
                    │                         │
                    │  1. Alpha mask          │
                    │  2. Connected-component │
                    │     labeling (8-conn)   │
                    │  3. Noise filtering     │
                    │  4. Proximity merging   │
                    │  5. Adaptive merge      │
                    │  6. Sort left-to-right  │
                    │                         │
                    │  output/<name>/views/   │
                    │    <direction>.png      │
                    └──────────┬─────────────┘
                               │
                       ┌───────▼───────┐
                       │ --sizes flag  │
                       │   provided?   │
                       └───┬───────┬───┘
                        yes│       │no
                           │       │
           ┌───────────────▼──┐    │
           │  Pixel Art       │    │
           │  Resize          │    │
           │                  │    │
           │  1. Detect pixel │    │
           │     grid (Canny  │    │
           │     + Hough)     │    │
           │  2. Sample color │    │
           │     per cell     │    │
           │  3. Quantize     │    │
           │     palette      │    │
           │  4. Resize with  │    │
           │     NEAREST      │    │
           │                  │    │
           │  views/<size>/   │    │
           └────────┬─────────┘    │
                    │              │
                    └──────┬───────┘
                           │
                    ┌──────▼──────┐
                    │    Done     │
                    └─────────────┘
```

## Stage Details

### 1. CLI Invocation

The user runs `pixel-magic generate` with required `--name` and `--description` flags, plus optional overrides for directions, style, resolution, colors, palette hints, chromakey color, tiles, char-ratio, resize sizes, and color quantization.

### 2. Configuration Resolution

Settings are resolved in priority order:
1. CLI arguments (highest priority)
2. `.env` file values (prefixed with `PIXEL_MAGIC_`)
3. Built-in defaults (lowest priority)

### 3. Platform Canvas (default) or Text-Only Prompt

**Platform mode (default):** Builds a canvas image with isometric platforms arranged in a grid. Each platform is labeled with its facing direction (pixel-art text in the top-left corner). Platforms are drawn as unified isometric blocks with tile division grid lines. The canvas is padded to match a Gemini-supported aspect ratio.

**Text-only mode (`--no-platform`):** Builds a JSON-structured prompt with view definitions, art style rules, background instructions, and layout hints. No reference image is sent.

### 4. Image Generation

**Platform mode** requires two Gemini API calls:
1. **Pass 1:** Canvas image + narrative prompt → Gemini fills in characters on each platform
2. **Pass 2:** Generated image + cleanup prompt → Gemini removes platforms and direction labels, replacing them with chromakey fill

**Text-only mode** uses a single Gemini API call with the JSON prompt.

Gemini returns inline binary image data with a solid chromakey background (green or blue). Exponential backoff retry logic handles transient API errors (429, 500, 503).

### 5. Raw Output Save

The model's output is saved as-is to `output/<name>/raw.png` with zero processing. This preserves the original for debugging and comparison.

### 6. Background Removal

Since Gemini cannot produce transparent backgrounds, a two-stage post-processing pipeline removes the chromakey background:

**Stage A: U2-Net Segmentation (rembg)**
- A pre-trained U2-Net neural network segments foreground (sprite) from background
- Produces a clean alpha mask that handles complex shapes, fine details, and semi-transparent areas
- Much more accurate than simple color-distance thresholding, which either eats into the sprite or misses fringe pixels

**Stage B: Color-Aware Despill**
- rembg leaves residual color bleed on edge pixels where the model anti-aliased against the chromakey background
- The despill pass identifies edge pixels: partially transparent pixels + fully opaque pixels within 3px of the alpha boundary
- For green chromakey: clamps `G = min(G, max(R, B))` — removes green tint without affecting other colors
- For blue chromakey: clamps `B = min(B, max(R, G))`
- Use `--chromakey blue` for green-skinned characters to avoid despill eating into the sprite

The cleaned result is saved to `output/<name>/sheet.png`.

### 7. Sprite Extraction

The composite sheet is split into individual view PNGs using connected-component analysis on the alpha channel.

**Step A: Alpha Masking** — all non-transparent pixels (alpha > 0) form a binary mask.

**Step B: Connected-Component Labeling** — `scipy.ndimage.label` with 8-connectivity identifies distinct blobs of non-transparent pixels.

**Step C: Noise Filtering** — blobs smaller than 0.5% of the largest blob's area are discarded (stray pixels, artifacts).

**Step D: Proximity Merging** — blobs within 8px of each other are merged into a single bounding box. This handles cases where parts of the same character (e.g., a sword tip) are separated by a few transparent pixels.

**Step E: Adaptive Merge** — if the expected view count is known (2 for 4-dir, 5 for 8-dir) and too many blobs remain, the merge gap is progressively increased (8px → 16px → 24px → ...) until the count matches.

**Step F: Sort & Crop** — merged blobs are sorted left-to-right (matching the prompt's view order) and cropped with 2px padding. Each sprite is saved with its direction label (`front_left.png`, `back_right.png`, etc.).

### 8. Pixel Art Resize (optional)

When `--sizes` is provided, each extracted sprite is converted to true pixel art using [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art):

**Step A: Grid Detection** — Canny edge detection + morphological closing + probabilistic Hough line transform detects the underlying pixel grid in the AI-generated sprite. This finds the actual grid spacing (which may be non-integer, e.g. 9.4 model pixels per intended game pixel).

**Step B: Color Sampling** — for each cell in the detected grid, the dominant color is selected using offset binning (a dual-grid approach that avoids quantization boundary artifacts).

**Step C: Palette Quantization (optional)** — if `--num-colors` is specified, PIL's MAXCOVERAGE quantization reduces the palette with dithering disabled for clean pixel art output.

**Step D: Target Resize** — the pixelated result is resized to the target dimensions (16-256px) using nearest-neighbor interpolation to preserve hard pixel edges, then centered on a transparent canvas.

Resized sprites are saved to `output/<name>/views/<size>x<size>/`.

## Output Structure

```
output/
└── <character-name>/
    ├── canvas_input.png  # Platform canvas sent to Gemini (platform mode)
    ├── raw.png           # Untouched model output (always saved)
    ├── sheet_cleaned.png # After platform removal (platform mode)
    ├── sheet.png         # Background-removed version
    └── views/            # Individual extracted sprites
        ├── front_left.png
        ├── back_right.png
        ├── 32x32/        # True pixel art at 32x32 (if --sizes used)
        │   ├── front_left.png
        │   └── back_right.png
        └── ...
```
