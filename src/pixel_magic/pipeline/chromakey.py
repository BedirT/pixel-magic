"""Chromakey background removal for providers that cannot generate transparency."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np
from PIL import Image

# HSV ranges for supported chromakey colors (OpenCV scale: H 0-180, S/V 0-255)
_CHROMAKEY_HSV_RANGES: dict[str, tuple[tuple[int, int], int, int]] = {
    "green": ((30, 90), 100, 150),  # relaxed for AI-generated greens, preserves dark greens
    "blue": ((100, 130), 200, 200),  # pure saturated bright blue only
}


def chromakey_color_to_rgb(
    color: Literal["green", "blue"],
) -> tuple[int, int, int]:
    """Return the canonical RGB value for a chromakey preset."""
    if color == "blue":
        return (0, 0, 255)
    return (0, 255, 0)


def remove_chromakey(
    image: Image.Image,
    color: Literal["green", "blue"] = "green",
) -> Image.Image:
    """Remove a solid chromakey background using HSV-based detection.

    Designed for AI-generated images where the model was instructed to use
    a solid green or blue background instead of transparency.

    Args:
        image: RGBA PIL Image.
        color: Chromakey preset — ``"green"`` (#00FF00) or ``"blue"`` (#0000FF).

    Returns:
        RGBA image with the chromakey background made transparent.
    """
    arr = np.array(image.convert("RGBA"))
    alpha = arr[:, :, 3]

    # Skip if image is already mostly transparent
    opaque_ratio = np.sum(alpha > 240) / alpha.size
    if opaque_ratio < 0.5:
        return image

    # Convert RGB to HSV for robust color matching
    rgb = arr[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    h_range, s_min, v_min = _CHROMAKEY_HSV_RANGES[color]
    h_lo, h_hi = h_range

    # Build chromakey mask: pixels matching the target color's HSV range
    mask = (
        (hsv[:, :, 0] >= h_lo)
        & (hsv[:, :, 0] <= h_hi)
        & (hsv[:, :, 1] >= s_min)
        & (hsv[:, :, 2] >= v_min)
    )

    # Set matched pixels to transparent
    result = arr.copy()
    result[mask, 3] = 0

    # Clean up alpha: threshold at 64 for binary edges
    new_alpha = result[:, :, 3]
    new_alpha = np.where(new_alpha < 64, np.uint8(0), np.uint8(255))
    result[:, :, 3] = new_alpha

    return Image.fromarray(result, "RGBA")
