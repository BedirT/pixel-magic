# Background Removal Research — What We Tried & Why

**Date:** March 2026
**Goal:** Remove the solid chromakey background from Gemini-generated pixel art sprites, producing clean binary-alpha (0 or 255) output.

---

## The Problem

Gemini cannot generate transparent backgrounds. It outputs fully opaque images with a solid chromakey background (green #00FF00 or blue #0000FF). We need to remove this background and produce RGBA sprites with binary alpha — every pixel either fully opaque (part of the sprite) or fully transparent (background).

**Complication: Gemini's green isn't exact.** Due to a known JPEG compression issue (Gemini returns JPEG bytes despite claiming PNG — [Issue #1824](https://github.com/googleapis/python-genai/issues/1824)), the background color is approximate. Typical values are `(2-14, 241-249, 3-6)` instead of pure `(0, 255, 0)`. There is also a 5-10 pixel anti-aliasing zone at sprite-background boundaries where colors blend.

---

## Approaches Evaluated

### 1. rembg / U2-Net Neural Network (REJECTED — was default, now replaced)

**How it works:** U2-Net is a deep learning model trained for salient object detection. It produces a soft alpha mask predicting foreground/background probability per pixel.

**Why we tried it:** It handles complex shapes well and doesn't require knowing the background color. It was the initial choice because simple thresholding was eating into sprite edges.

**Why we rejected it:**
- **Produces soft alpha** — 98.7% of sprite pixels end up semi-transparent (alpha 128-254) instead of fully opaque. This is correct for natural photos but catastrophic for pixel art.
- **Destroys pixel art quality** — promoting semi-transparent pixels to opaque bakes in blended/washed-out colors. The sprite body appears dimmer and desaturated.
- **Heavyweight dependency** — pulls in onnxruntime (63MB), scikit-image (25MB), pymatting, and U2-Net model weights. ~92MB of dependencies for something that should be a color match.
- **Wrong tool for a known-color background** — U2-Net is designed for unknown backgrounds in natural photos. We know the exact background color.

**Measured impact:**
- Only 1.3% of raw sprite pixels were fully opaque (alpha=255) after rembg
- Mean brightness of body pixels dropped significantly due to alpha blending
- Required a complex despill pass + alpha hardening in cleanup.py to recover usable output

### 2. Exact Color Matching (REJECTED)

**How it works:** `pixel == (0, 255, 0) → transparent`

**Why we rejected it:** Gemini never produces exact #00FF00. Across all test images, zero pixels matched. JPEG compression shifts background values to approximately (2-14, 241-249, 3-6). This approach would leave the background almost entirely intact.

### 3. Euclidean Color-Distance Thresholding (REJECTED)

**How it works:** `sqrt((R-0)² + (G-255)² + (B-0)²) < threshold → transparent`

**Tradeoffs:**
- Threshold ~60-70 removes most JPEG-noisy green background
- Edge pixels that are blends of sprite+green (e.g., (70, 173, 22)) have distance ~111 from pure green — outside the threshold, leaving a green fringe
- Increasing threshold to ~100+ starts eating into green-tinted sprite pixels (green clothing, orc skin)

**Why we rejected it:** Fundamental tradeoff between leaving fringe (threshold too low) and destroying green foreground pixels (threshold too high). Also, doesn't distinguish interior green (part of the sprite) from exterior green (background).

### 4. Channel-Ratio / Green Dominance (USED — as part of hybrid)

**How it works:** `G > max(R, B) + margin → background`

**Strengths:** Tests the relationship between channels rather than proximity to a fixed point. More robust to JPEG compression. A blended edge pixel (70, 173, 22) has G exceeding max(R,B)=70 by 103 — correctly identified.

**Limitation:** Can't distinguish interior green from exterior green on its own. An orc's green skin (30, 120, 30) has G exceeding max(R,B) by 90 — falsely flagged. Mitigated by combining with flood fill.

**Current use:** The green-dominance test is the detection function used by the flood fill. Also used in cleanup.py for residual interior contamination with a dark-pixel exemption.

### 5. HSV Chroma Keying (CONSIDERED — not used)

**How it works:** Convert to HSV, threshold on hue range (~80-160°) and minimum saturation (~40%).

**Strengths:** More perceptually accurate than RGB distance. Hue is relatively stable under JPEG compression.

**Why we didn't use it:** The channel-ratio approach achieves similar results with simpler code and no color space conversion. HSV would be marginally better at distinguishing saturated greens from olive/mossy tones, but this edge case is already handled by the `--chromakey blue` flag for green characters.

### 6. Flood Fill from Edges (CHOSEN — current implementation)

**How it works:**
1. Identify chromakey-dominant pixels using channel-ratio test
2. Seed BFS from all border pixels that pass the test
3. 4-connected flood fill — only expand to neighbors that also pass
4. Everything reached = background (alpha=0), everything else = foreground (alpha=255)

**Why this works best:**
- **Exploits known background color** — direct, simple
- **Preserves interior green** — flood fill can't reach green pixels inside the sprite (orc skin, emerald gems, green clothing) because they're separated by the sprite outline
- **4-connectivity prevents leaking** — won't leak through diagonal 1px gaps in sprite outlines
- **Binary alpha by construction** — no soft edges, no semi-transparency
- **Fast** — ~30ms vs ~3-10s for rembg
- **Zero new dependencies** — uses only numpy and collections.deque
- **Simple** — ~40 lines of code

**Followed by boundary despill:** After flood fill, the 1px sprite boundary gets green channel clamped to max(R,B) to remove JPEG-induced color fringe.

### 7. GrabCut (REJECTED)

**How it works:** Iterative graph-cut segmentation with Gaussian Mixture Models for foreground/background color distributions. Can be initialized with a color-based mask.

**Why we evaluated it:** OpenCV is already installed (transitive dep of proper-pixel-art), so zero additional dependency cost. Could potentially handle the anti-aliasing zone better than simple flood fill.

**Why we rejected it:**
- **Problem is too easy for GrabCut** — designed for unknown, complex backgrounds (photos of people in rooms). We know the background is green.
- **Smoothness prior hurts pixel art** — GrabCut penalizes high-frequency color changes, which is exactly what pixel art is (sharp 1px transitions). Could erode fine sprite details.
- **10-30x slower** — ~0.5-1.5s per image vs ~30ms for flood fill
- **GMM overkill** — 5-Gaussian mixture models per class are designed for photographic color gradients, not limited pixel art palettes
- **Worse for green characters** — GMM would merge foreground/background distributions when both are green, making it perform worse than the flood fill approach for this specific edge case

### 8. Canny Edge Detection + Flood Fill (REJECTED)

**How it works:** Detect sprite boundary via Canny edge detection, then flood fill from outside the Canny contour.

**Why we evaluated it:** Canny works exceptionally well on pixel art (sharp, high-contrast edges). Could produce very clean boundary detection.

**Why we rejected it:**
- **Fragile to edge gaps** — if Canny misses even one pixel gap in the edge map (common at thin weapon tips, wispy effects), the flood fill leaks through and marks foreground as background. Catastrophic failure mode.
- **Needs gap-closing morphology** — requires dilation/closing to connect broken edges, which thickens the boundary and can merge nearby separate features
- **Still needs color info** — Canny detects edges but doesn't know which side is foreground vs background. You still need the color-based test, making Canny an additional step for marginal gain.
- **Parameter sensitivity** — Canny thresholds (sigma, low/high) need careful tuning for pixel art, and the right values may differ across sprite styles

Canny could be useful as a future refinement step (snap the flood-fill boundary to true edges), but the added complexity isn't justified by the improvement.

### 9. Alpha Matting from Known Background (REJECTED)

**How it works:** Given `rendered_pixel = alpha * sprite_color + (1-alpha) * bg_color`, and knowing bg_color, solve for alpha and sprite_color.

**Simplified formula for green keying:** `alpha = 1.0 - max(0, (G - max(R, B)) / 255.0)`

**Why we rejected it:**
- **Produces soft alpha** — fractional values that need thresholding for pixel art, losing the theoretical advantage
- **JPEG noise makes estimates unreliable** — compression artifacts create noisy alpha with shimmering semi-transparent halos
- **Over-engineered** — the theoretical elegance doesn't survive the practical reality of JPEG-compressed pixel art

### 10. Hybrid: Flood Fill + Edge Cleanup (CONSIDERED — partially used)

**How it works:** Flood fill for bulk background, then Canny or color-distance cleanup on the boundary zone.

**Current status:** We use flood fill + boundary despill, which is a simpler form of this. The full hybrid with Canny edge snapping is available as a future improvement if needed, but the current despill-only approach produces clean enough results.

---

## Decision Summary

| Approach | Quality | Speed | Dependencies | Chosen? |
|----------|---------|-------|-------------|---------|
| rembg (U2-Net) | Soft alpha, washed colors | ~3-10s | +92MB | No (was default, removed) |
| Exact color match | Fails (0% match) | <1ms | None | No |
| Color-distance | Fringe or eats sprite | <1ms | None | No |
| Channel-ratio | Good detection | <1ms | None | Yes (as flood fill test) |
| HSV chroma key | Marginally better | ~5ms | None | No (channel-ratio simpler) |
| **Flood fill + despill** | **Binary alpha, clean** | **~30ms** | **None** | **Yes** |
| GrabCut | Over-smooths pixel art | ~1000ms | None (cv2 exists) | No |
| Canny + flood fill | Fragile to gaps | ~50ms | None (cv2 exists) | No |
| Alpha matting | Soft alpha, noisy | ~5ms | None | No |

---

## Current Pipeline

```
Gemini output (fully opaque, approx-green background)
  │
  ├─ Flood fill from borders (G > max(R,B) + 30, 4-connected)
  │   → binary background mask
  │
  ├─ Set background to transparent (alpha=0, RGB=0)
  │
  ├─ Boundary despill (1px sprite edge: G = min(G, max(R,B)))
  │
  └─ Output: RGBA with binary alpha (0 or 255)
```

**Key properties:**
- Zero new dependencies (numpy only)
- ~40 lines of code
- ~30ms per 1200x900 image
- Binary alpha by construction
- Interior green preserved (flood fill can't reach it)
- JPEG artifacts handled by channel-ratio tolerance
- Green characters: use `--chromakey blue`
