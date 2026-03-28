"""Mask cleanup for extracted sprites.

Removes residual chromakey-dominant pixels that survived background
removal (e.g., interior contamination the flood fill couldn't reach),
cleans small islands and holes, and trims to bounds. Does not repaint
shading or texture — only the mask is modified.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion, binary_fill_holes, label


def cleanup_sprite(
    image: Image.Image, chromakey_color: str = "green"
) -> Image.Image:
    """Clean mask for a single extracted sprite.

    Removes residual chromakey-dominant pixels, small disconnected
    islands, and fills tiny holes. Does not repaint shading or texture.

    Args:
        image: RGBA sprite from extract_sprites().
        chromakey_color: "green" or "blue" — which channel to reject.

    Returns:
        RGBA image with binary alpha, trimmed to cleaned bounds.
    """
    arr = np.array(image.convert("RGBA"), dtype=np.uint8)

    candidate = _build_candidate_mask(arr, chromakey_color)
    candidate = _remove_small_islands(candidate, min_size=3)
    candidate = _fill_small_holes(candidate, max_size=2)
    candidate = _strip_outer_outline(arr, candidate)

    result = _rebuild_with_hard_alpha(arr, candidate)

    trimmed = _trim_to_bounds(result, candidate)
    if trimmed is None:
        return image  # cleanup removed everything — return original

    return Image.fromarray(trimmed, "RGBA")


def _build_candidate_mask(
    arr: np.ndarray, chromakey_color: str, margin: int = 30
) -> np.ndarray:
    """Build foreground mask from alpha + chromakey-dominance rejection."""
    alpha = arr[:, :, 3]
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    candidate = alpha > 0

    # Reject chromakey-dominant pixels
    if chromakey_color == "blue":
        contaminated = b > (np.maximum(r, g).astype(np.int16) + margin)
    else:
        contaminated = g > (np.maximum(r, b).astype(np.int16) + margin)

    # Preserve dark contour pixels even near contaminated areas
    is_dark = np.maximum(np.maximum(r, g), b) < 60
    candidate = candidate & (~contaminated | is_dark)

    return candidate


def _remove_small_islands(mask: np.ndarray, min_size: int = 3) -> np.ndarray:
    """Remove connected components smaller than min_size pixels."""
    result = mask.copy()
    labeled, n = label(result, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return result

    sizes = np.bincount(labeled.ravel())
    # sizes[0] is background — skip
    for i in range(1, n + 1):
        if sizes[i] < min_size:
            result[labeled == i] = False

    return result


def _fill_small_holes(mask: np.ndarray, max_size: int = 2) -> np.ndarray:
    """Fill enclosed holes up to max_size pixels."""
    filled = binary_fill_holes(mask)
    holes = filled & ~mask

    if not holes.any():
        return mask

    result = mask.copy()
    labeled_holes, n = label(holes, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return result

    sizes = np.bincount(labeled_holes.ravel())
    for i in range(1, n + 1):
        if sizes[i] <= max_size:
            result[labeled_holes == i] = True

    return result


def _strip_outer_outline(
    arr: np.ndarray, mask: np.ndarray,
    max_brightness: int = 35, max_spread: int = 20,
) -> np.ndarray:
    """Remove the 1px dark outline from the outer boundary of the sprite.

    Peels the outermost layer of near-black, low-saturation boundary
    pixels (the AI's outline). Only one pass — does not iterate, to
    avoid eating into dark body regions behind the outline.

    The outline is re-added algorithmically at the target size after
    pixelation.
    """
    result = mask.copy()
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    spread = max_ch.astype(np.int16) - min_ch.astype(np.int16)

    is_outline_color = (max_ch < max_brightness) & (spread < max_spread)

    struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)

    eroded = binary_erosion(result, structure=struct)
    boundary = result & ~eroded
    to_strip = boundary & is_outline_color

    result[to_strip] = False

    return result


def _rebuild_with_hard_alpha(arr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Set alpha to 0 or 255 based on mask. Zero RGB on transparent pixels."""
    result = arr.copy()
    result[:, :, 3] = np.where(mask, 255, 0)
    transparent = ~mask
    result[transparent, 0] = 0
    result[transparent, 1] = 0
    result[transparent, 2] = 0
    return result


def _trim_to_bounds(
    arr: np.ndarray, mask: np.ndarray, padding: int = 2
) -> np.ndarray | None:
    """Crop to mask bounding box plus padding. Returns None if mask is empty."""
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any():
        return None

    row_indices = np.where(rows)[0]
    col_indices = np.where(cols)[0]
    rmin, rmax = row_indices[0], row_indices[-1]
    cmin, cmax = col_indices[0], col_indices[-1]

    h, w = arr.shape[:2]
    rmin = max(0, rmin - padding)
    rmax = min(h - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(w - 1, cmax + padding)

    return arr[rmin : rmax + 1, cmin : cmax + 1]
