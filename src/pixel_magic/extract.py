"""Smart sprite extraction from character sheets.

LLMs place sprites inconsistently on the canvas, so we use connected-component
analysis on the alpha channel to find individual character views.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.ndimage import label, find_objects


def extract_sprites(
    image: Image.Image,
    expected_count: int | None = None,
    padding: int = 2,
    min_area_ratio: float = 0.005,
    gap_threshold: int = 8,
) -> list[Image.Image]:
    """Extract individual sprites from a sheet image.

    Uses connected-component labeling on non-transparent pixels, then merges
    nearby blobs (parts of the same character that have small gaps), filters
    noise, and returns cropped sprites sorted left-to-right.

    Args:
        image: RGBA sheet image.
        expected_count: If set, attempts to merge/split to hit this count.
        padding: Extra pixels around each sprite crop.
        min_area_ratio: Minimum blob area as fraction of largest blob to keep.
        gap_threshold: Max pixel gap between blobs to merge them as one sprite.
    """
    arr = np.array(image.convert("RGBA"))
    alpha = arr[:, :, 3]

    # Binary mask: any non-transparent pixel
    mask = alpha > 0

    if not mask.any():
        return []

    # Label connected components (8-connectivity)
    structure = np.ones((3, 3), dtype=int)  # 8-connectivity
    labeled, num_features = label(mask, structure=structure)

    if num_features == 0:
        return []

    # Get bounding boxes for each component
    slices = find_objects(labeled)
    boxes = []
    for s in slices:
        if s is None:
            continue
        y_start, y_end = s[0].start, s[0].stop
        x_start, x_end = s[1].start, s[1].stop
        area = (y_end - y_start) * (x_end - x_start)
        boxes.append((x_start, y_start, x_end, y_end, area))

    if not boxes:
        return []

    # Filter tiny noise blobs
    max_area = max(b[4] for b in boxes)
    boxes = [b for b in boxes if b[4] >= max_area * min_area_ratio]

    # Merge nearby blobs that likely belong to the same character
    boxes = _merge_nearby(boxes, gap_threshold)

    # Sort left-to-right
    boxes.sort(key=lambda b: b[0])

    # If we have expected count and too many boxes, increase merge aggressiveness
    if expected_count and len(boxes) > expected_count:
        merged = boxes
        for gap in range(gap_threshold, 200, 8):
            merged = _merge_nearby(boxes, gap)
            if len(merged) <= expected_count:
                break
        boxes = merged
        boxes.sort(key=lambda b: b[0])

    # Crop each sprite with padding
    h, w = arr.shape[:2]
    sprites = []
    for x0, y0, x1, y1, _ in boxes:
        x0 = max(0, x0 - padding)
        y0 = max(0, y0 - padding)
        x1 = min(w, x1 + padding)
        y1 = min(h, y1 + padding)
        sprites.append(image.crop((x0, y0, x1, y1)))

    return sprites


def _merge_nearby(
    boxes: list[tuple[int, int, int, int, int]], gap: int
) -> list[tuple[int, int, int, int, int]]:
    """Merge bounding boxes that are within `gap` pixels of each other."""
    if not boxes:
        return []

    merged = list(boxes)
    changed = True
    while changed:
        changed = False
        new_merged = []
        used = set()
        for i in range(len(merged)):
            if i in used:
                continue
            x0, y0, x1, y1, area = merged[i]
            for j in range(i + 1, len(merged)):
                if j in used:
                    continue
                ox0, oy0, ox1, oy1, oa = merged[j]
                # Check if boxes overlap or are within gap distance
                if (
                    x0 - gap <= ox1
                    and x1 + gap >= ox0
                    and y0 - gap <= oy1
                    and y1 + gap >= oy0
                ):
                    # Merge
                    x0 = min(x0, ox0)
                    y0 = min(y0, oy0)
                    x1 = max(x1, ox1)
                    y1 = max(y1, oy1)
                    area = (y1 - y0) * (x1 - x0)
                    used.add(j)
                    changed = True
            new_merged.append((x0, y0, x1, y1, area))
            used.add(i)
        merged = new_merged
    return merged
