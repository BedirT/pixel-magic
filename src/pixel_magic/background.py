"""Background removal for Gemini-generated images using rembg."""

from __future__ import annotations

import numpy as np
from PIL import Image
from rembg import remove
from scipy.ndimage import binary_dilation


def remove_background(
    image: Image.Image, chromakey_color: str = "green"
) -> Image.Image:
    """Remove background using U2-Net segmentation, then despill color fringe."""
    result = remove(image)
    return _despill(result, chromakey_color)


def _despill(
    image: Image.Image, chromakey_color: str = "green", edge_radius: int = 3
) -> Image.Image:
    """Remove chromakey color spill from edge and near-edge pixels.

    Clamps the chromakey channel to max of the other two channels on:
    1. Partially transparent pixels (direct edge zone)
    2. Fully opaque pixels within `edge_radius` of the alpha boundary

    Args:
        image: RGBA image after background removal.
        chromakey_color: "green" or "blue" — which channel to despill.
        edge_radius: How far from transparency boundary to apply despill.
    """
    arr = np.array(image, dtype=np.uint8)
    alpha = arr[:, :, 3]

    # Partially transparent pixels
    partial_mask = (alpha > 0) & (alpha < 255)

    # Fully opaque pixels near the transparency boundary
    transparent_zone = alpha == 0
    dilated = binary_dilation(transparent_zone, iterations=edge_radius)
    opaque_edge_mask = dilated & (alpha == 255)

    # Combined mask: all pixels that might have spill
    spill_mask = partial_mask | opaque_edge_mask

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    if chromakey_color == "blue":
        # Clamp B to max(R, G)
        max_rg = np.maximum(r, g)
        arr[:, :, 2] = np.where(spill_mask, np.minimum(b, max_rg), b)
    else:
        # Clamp G to max(R, B)
        max_rb = np.maximum(r, b)
        arr[:, :, 1] = np.where(spill_mask, np.minimum(g, max_rb), g)

    return Image.fromarray(arr, "RGBA")
