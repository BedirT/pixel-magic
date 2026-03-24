"""Background removal for Gemini-generated images using rembg."""

from __future__ import annotations

import numpy as np
from PIL import Image
from rembg import remove
from scipy.ndimage import binary_dilation


def remove_background(image: Image.Image) -> Image.Image:
    """Remove background using U2-Net segmentation, then despill green fringe."""
    result = remove(image)
    return _despill_green(result)


def _despill_green(image: Image.Image, edge_radius: int = 3) -> Image.Image:
    """Remove green color spill from edge and near-edge pixels.

    Applies green despill (clamp G to max(R,B)) on:
    1. Partially transparent pixels (direct edge zone)
    2. Fully opaque pixels within `edge_radius` of the alpha boundary
    """
    arr = np.array(image, dtype=np.uint8)
    alpha = arr[:, :, 3]

    # Partially transparent pixels
    partial_mask = (alpha > 0) & (alpha < 255)

    # Fully opaque pixels near the transparency boundary
    transparent_zone = alpha == 0
    dilated = binary_dilation(transparent_zone, iterations=edge_radius)
    opaque_edge_mask = dilated & (alpha == 255)

    # Combined mask: all pixels that might have green spill
    spill_mask = partial_mask | opaque_edge_mask

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    max_rb = np.maximum(r, b)
    arr[:, :, 1] = np.where(spill_mask, np.minimum(g, max_rb), g)

    return Image.fromarray(arr, "RGBA")
