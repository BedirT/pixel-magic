"""Background removal for Gemini-generated images using chromakey flood fill.

Gemini outputs fully opaque images with a solid chromakey background
(green #00FF00 or blue #0000FF). Due to JPEG compression and rendering,
the actual background color is approximate (never exact #00FF00).

This module removes the background using:
1. Flood fill from image borders — identifies connected green/blue regions
2. Boundary despill — clamps the chromakey channel on the 1px sprite edge
3. Binary alpha — every pixel is fully opaque or fully transparent
"""

from __future__ import annotations

from collections import deque

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation


def remove_background(
    image: Image.Image, chromakey_color: str = "green"
) -> Image.Image:
    """Remove chromakey background via flood fill from image borders.

    Args:
        image: Fully opaque RGBA image from Gemini with chromakey background.
        chromakey_color: "green" or "blue".

    Returns:
        RGBA image with binary alpha (0 or 255 only).
    """
    arr = np.array(image.convert("RGBA"), dtype=np.uint8)
    bg_mask = _flood_fill_background(arr, chromakey_color)

    # Set background to transparent
    arr[bg_mask, 3] = 0
    arr[bg_mask, :3] = 0

    # Despill boundary pixels
    arr = _despill_boundary(arr, bg_mask, chromakey_color)

    return Image.fromarray(arr, "RGBA")


def _is_chromakey(r: np.ndarray, g: np.ndarray, b: np.ndarray,
                  chromakey_color: str, margin: int = 30) -> np.ndarray:
    """Test whether pixels are chromakey-dominant."""
    if chromakey_color == "blue":
        return b > (np.maximum(r, g).astype(np.int16) + margin)
    return g > (np.maximum(r, b).astype(np.int16) + margin)


def _flood_fill_background(arr: np.ndarray, chromakey_color: str,
                           margin: int = 30) -> np.ndarray:
    """Flood fill from image borders to find the background region.

    Uses 4-connectivity (cardinal directions only) to prevent leaking
    through diagonal 1px gaps in sprite outlines.
    """
    h, w = arr.shape[:2]
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Pixels that look like the chromakey color
    is_key = _is_chromakey(r, g, b, chromakey_color, margin)

    # BFS flood fill from all border pixels that pass the chromakey test
    bg_mask = np.zeros((h, w), dtype=bool)
    queue = deque()

    # Seed from borders
    for x in range(w):
        if is_key[0, x]:
            bg_mask[0, x] = True
            queue.append((0, x))
        if is_key[h - 1, x]:
            bg_mask[h - 1, x] = True
            queue.append((h - 1, x))
    for y in range(1, h - 1):
        if is_key[y, 0]:
            bg_mask[y, 0] = True
            queue.append((y, 0))
        if is_key[y, w - 1]:
            bg_mask[y, w - 1] = True
            queue.append((y, w - 1))

    # 4-connected flood fill
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not bg_mask[ny, nx] and is_key[ny, nx]:
                bg_mask[ny, nx] = True
                queue.append((ny, nx))

    return bg_mask


def _despill_boundary(arr: np.ndarray, bg_mask: np.ndarray,
                      chromakey_color: str) -> np.ndarray:
    """Clamp chromakey channel on the 1px boundary of the sprite.

    Sprite edge pixels absorb chromakey color from JPEG compression
    and Gemini's anti-aliasing. Clamping the chromakey channel to
    max of the other two channels removes the color fringe.
    """
    result = arr.copy()
    opaque = arr[:, :, 3] == 255

    # Find opaque pixels adjacent to background (1px boundary)
    boundary = opaque & binary_dilation(bg_mask, iterations=1)

    r, g, b = result[:, :, 0], result[:, :, 1], result[:, :, 2]

    if chromakey_color == "blue":
        max_rg = np.maximum(r, g)
        result[:, :, 2] = np.where(boundary, np.minimum(b, max_rg), b)
    else:
        max_rb = np.maximum(r, b)
        result[:, :, 1] = np.where(boundary, np.minimum(g, max_rb), g)

    return result
