"""Frame extraction from composite AI-generated images."""

from __future__ import annotations

import logging

import cv2
import numpy as np
from PIL import Image

from pixel_magic.models.asset import CompositeLayout

logger = logging.getLogger(__name__)


def extract_frames(
    composite: Image.Image,
    layout: CompositeLayout,
    expected_count: int,
    grid_cols: int | None = None,
) -> list[Image.Image]:
    """Extract individual sprite frames from a composite image.

    Args:
        composite: The composite image containing multiple sprites.
        layout: How the sprites are arranged.
        expected_count: How many frames we expect to find.
        grid_cols: For GRID layout, how many columns.

    Returns:
        List of extracted PIL Images (RGBA).
    """
    composite = composite.convert("RGBA")

    if layout == CompositeLayout.AUTO_DETECT:
        return _extract_auto(composite, expected_count)
    elif layout == CompositeLayout.HORIZONTAL_STRIP:
        return _extract_strip(composite, expected_count, horizontal=True)
    elif layout == CompositeLayout.VERTICAL_STRIP:
        return _extract_strip(composite, expected_count, horizontal=False)
    elif layout == CompositeLayout.GRID:
        cols = grid_cols or expected_count
        rows = max(1, (expected_count + cols - 1) // cols)
        return _extract_grid(composite, rows, cols, expected_count)
    else:
        return _extract_strip(composite, expected_count, horizontal=True)


def _extract_strip(
    composite: Image.Image, expected_count: int, horizontal: bool
) -> list[Image.Image]:
    """Extract frames from an evenly-divided strip."""
    w, h = composite.size
    frames = []

    if horizontal:
        frame_w = w // expected_count
        for i in range(expected_count):
            x = i * frame_w
            frame = composite.crop((x, 0, x + frame_w, h))
            frames.append(frame)
    else:
        frame_h = h // expected_count
        for i in range(expected_count):
            y = i * frame_h
            frame = composite.crop((0, y, w, y + frame_h))
            frames.append(frame)

    return frames


def _extract_grid(
    composite: Image.Image, rows: int, cols: int, expected_count: int
) -> list[Image.Image]:
    """Extract frames from a grid layout."""
    w, h = composite.size
    cell_w = w // cols
    cell_h = h // rows
    frames = []

    for r in range(rows):
        for c in range(cols):
            if len(frames) >= expected_count:
                break
            x = c * cell_w
            y = r * cell_h
            frame = composite.crop((x, y, x + cell_w, y + cell_h))
            frames.append(frame)

    return frames


def _extract_auto(composite: Image.Image, expected_count: int) -> list[Image.Image]:
    """Auto-detect sprite regions using connected component analysis on alpha."""
    arr = np.array(composite)
    alpha = arr[:, :, 3]

    # Threshold alpha to binary mask
    _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)

    # Dilate slightly to connect nearby components that belong to the same sprite
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(binary, kernel, iterations=3)

    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dilated, connectivity=8
    )

    # Collect bounding boxes (skip label 0 = background)
    bboxes = []
    for i in range(1, num_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        # Filter out very tiny components (noise)
        if area < 100:
            continue
        bboxes.append((x, y, w, h, area))

    # Sort by x position (left to right), then y (top to bottom)
    bboxes.sort(key=lambda b: (b[1] // 50, b[0]))

    # If we found more regions than expected, keep the largest ones
    if len(bboxes) > expected_count:
        bboxes.sort(key=lambda b: b[4], reverse=True)
        bboxes = bboxes[:expected_count]
        bboxes.sort(key=lambda b: (b[1] // 50, b[0]))

    frames = []
    for x, y, w, h, _area in bboxes:
        frame = composite.crop((x, y, x + w, y + h))
        frames.append(frame)

    if len(frames) != expected_count:
        logger.warning(
            "Auto-detect found %d regions but expected %d. "
            "Falling back to horizontal strip extraction.",
            len(frames), expected_count,
        )
        if len(frames) < expected_count:
            return _extract_strip(composite, expected_count, horizontal=True)

    return frames


def normalize_frame_sizes(frames: list[Image.Image]) -> list[Image.Image]:
    """Ensure all frames have the same dimensions (use the max size with centering)."""
    if not frames:
        return frames

    max_w = max(f.width for f in frames)
    max_h = max(f.height for f in frames)

    # If already uniform, return as-is
    if all(f.width == max_w and f.height == max_h for f in frames):
        return frames

    normalized = []
    for frame in frames:
        if frame.width == max_w and frame.height == max_h:
            normalized.append(frame)
        else:
            # Center the frame on a larger canvas
            canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
            offset_x = (max_w - frame.width) // 2
            offset_y = (max_h - frame.height) // 2
            canvas.paste(frame, (offset_x, offset_y))
            normalized.append(canvas)

    return normalized
