"""Lattice projection — cell-wise downsample to the pixel grid."""

from __future__ import annotations

import numpy as np
from PIL import Image


def project_to_grid(
    image: Image.Image,
    macro_size: int,
    offset_x: int = 0,
    offset_y: int = 0,
    alpha_threshold: float = 0.5,
) -> Image.Image:
    """Downsample image to its pixel grid using cell-wise robust estimators.

    For each macro-cell:
    - Color: median in RGB (OKLab conversion deferred to palette stage for simplicity)
    - Alpha: majority vote (binary threshold applied per cell)

    Returns an image at the target pixel resolution.
    """
    arr = np.array(image).astype(np.float32)
    h, w = arr.shape[:2]

    # Compute target dimensions
    out_h = (h - offset_y) // macro_size
    out_w = (w - offset_x) // macro_size

    if out_h < 1 or out_w < 1:
        return image

    # Crop to aligned region
    region = arr[offset_y : offset_y + out_h * macro_size,
                 offset_x : offset_x + out_w * macro_size]

    # Reshape into cells: (out_h, macro_size, out_w, macro_size, 4)
    cells = region.reshape(out_h, macro_size, out_w, macro_size, 4)
    # Transpose to (out_h, out_w, macro_size, macro_size, 4)
    cells = cells.transpose(0, 2, 1, 3, 4)
    # Flatten spatial dims within each cell: (out_h, out_w, macro_size*macro_size, 4)
    cells = cells.reshape(out_h, out_w, macro_size * macro_size, 4)

    # RGB: median of each cell (more robust than mean against AA pixels)
    rgb_median = np.median(cells[:, :, :, :3], axis=2)

    # Alpha: majority vote — count pixels above threshold
    alpha_vals = cells[:, :, :, 3]
    thresh = alpha_threshold * 255
    alpha_above = np.sum(alpha_vals >= thresh, axis=2)
    total = macro_size * macro_size
    alpha_out = np.where(alpha_above > total / 2, 255.0, 0.0)

    # Combine
    result = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    result[:, :, :3] = np.clip(rgb_median, 0, 255).astype(np.uint8)
    result[:, :, 3] = alpha_out.astype(np.uint8)

    return Image.fromarray(result, "RGBA")


def upscale_nearest(image: Image.Image, scale: int) -> Image.Image:
    """Upscale with nearest-neighbor (for preview/verification)."""
    w, h = image.size
    return image.resize((w * scale, h * scale), Image.NEAREST)
