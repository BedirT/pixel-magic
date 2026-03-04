"""Grid inference — detect macro-pixel size from an image."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class GridResult:
    """Result of grid inference."""

    macro_size: int
    offset_x: int
    offset_y: int
    confidence: float
    scores: dict[int, float]  # size → best score


def infer_grid(
    image: Image.Image,
    size_range: tuple[int, int] = (2, 32),
    target_resolution: tuple[int, int] | None = None,
) -> GridResult:
    """Infer the macro-pixel grid size from an image.

    If target_resolution is known (e.g., we generated a 64x64 sprite at 1024x1024),
    we can compute the grid size directly.

    Otherwise, search candidate sizes and score by intra-cell variance.
    """
    w, h = image.size

    # Fast path: if target resolution is known, compute directly
    if target_resolution is not None:
        tw, th = target_resolution
        sx = w // tw if tw > 0 else 1
        sy = h // th if th > 0 else 1
        macro = max(sx, sy, 1)
        return GridResult(
            macro_size=macro,
            offset_x=0,
            offset_y=0,
            confidence=1.0,
            scores={macro: 1.0},
        )

    arr = np.array(image).astype(np.float32)

    lo, hi = size_range
    lo = max(2, lo)
    hi = min(hi, min(w, h) // 2)

    scores: dict[int, float] = {}

    for s in range(lo, hi + 1):
        # Only consider sizes that divide the image dimensions reasonably
        # Allow a small remainder
        if w % s > s // 2 or h % s > s // 2:
            continue

        score = _score_grid(arr, s, 0, 0)
        scores[s] = score

    if not scores:
        # Fallback: try all sizes without the divisibility filter
        for s in range(lo, hi + 1):
            score = _score_grid(arr, s, 0, 0)
            scores[s] = score

    if not scores:
        return GridResult(macro_size=1, offset_x=0, offset_y=0, confidence=0.0, scores={})

    # Best score = lowest variance
    best_size = min(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_size]

    # Confidence: how much better is the best vs the median
    all_scores = sorted(scores.values())
    median_score = all_scores[len(all_scores) // 2] if all_scores else 1.0
    if median_score > 0:
        confidence = max(0.0, min(1.0, 1.0 - best_score / median_score))
    else:
        confidence = 1.0

    return GridResult(
        macro_size=best_size,
        offset_x=0,
        offset_y=0,
        confidence=confidence,
        scores=scores,
    )


def _score_grid(arr: np.ndarray, size: int, ox: int, oy: int) -> float:
    """Score a candidate grid by mean intra-cell variance.

    Lower score = more uniform cells = more likely to be the correct grid.
    """
    h, w = arr.shape[:2]
    channels = arr.shape[2] if arr.ndim == 3 else 1

    # Crop to aligned region
    usable_h = ((h - oy) // size) * size
    usable_w = ((w - ox) // size) * size
    if usable_h < size or usable_w < size:
        return float("inf")

    region = arr[oy : oy + usable_h, ox : ox + usable_w]

    # Reshape into cells
    rows = usable_h // size
    cols = usable_w // size
    cells = region.reshape(rows, size, cols, size, channels)
    cells = cells.transpose(0, 2, 1, 3, 4)  # (rows, cols, size, size, channels)
    cells = cells.reshape(rows * cols, size * size, channels)

    # Mean intra-cell variance across all channels
    variance = np.var(cells, axis=1).mean()
    return float(variance)
