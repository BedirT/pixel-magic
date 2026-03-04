"""Ingest & normalize — RGBA normalization, background removal, alpha policy."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image


def load_image(source: bytes | Path | Image.Image) -> Image.Image:
    """Load and normalize an image to RGBA."""
    if isinstance(source, Image.Image):
        return source.convert("RGBA")
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGBA")
    return Image.open(source).convert("RGBA")


def apply_alpha_policy(image: Image.Image, policy: str = "binary", threshold: float = 0.5) -> Image.Image:
    """Enforce alpha policy on an RGBA image.

    - "binary": snap alpha to 0 or 255 based on threshold.
    - "keep8bit": leave alpha as-is.
    """
    if policy == "keep8bit":
        return image

    arr = np.array(image)
    alpha = arr[:, :, 3]
    thresh_val = int(threshold * 255)
    alpha = np.where(alpha >= thresh_val, np.uint8(255), np.uint8(0))
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def remove_background(
    image: Image.Image,
    color_tolerance: int = 30,
) -> Image.Image:
    """Remove solid background by sampling corners and making matching pixels transparent.

    Useful for providers that don't support native transparency.
    """
    arr = np.array(image)
    h, w = arr.shape[:2]

    # Sample 4 corners (5x5 patches) to find dominant background color
    corner_size = min(5, h // 4, w // 4)
    corners = [
        arr[:corner_size, :corner_size],
        arr[:corner_size, -corner_size:],
        arr[-corner_size:, :corner_size],
        arr[-corner_size:, -corner_size:],
    ]
    corner_pixels = np.concatenate([c.reshape(-1, 4) for c in corners], axis=0)

    # Use median as the background color estimate (robust to outliers)
    bg_color = np.median(corner_pixels, axis=0).astype(np.uint8)

    # If background is already mostly transparent, skip
    if bg_color[3] < 128:
        return image

    # Compute color distance for RGB channels
    rgb = arr[:, :, :3].astype(np.int16)
    bg_rgb = bg_color[:3].astype(np.int16)
    dist = np.sqrt(np.sum((rgb - bg_rgb) ** 2, axis=2))

    # Make matching pixels transparent
    mask = dist < color_tolerance
    arr[mask, 3] = 0

    return Image.fromarray(arr, "RGBA")


def trim_transparent(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Trim transparent borders. Returns (trimmed_image, (left, top, right, bottom) offsets)."""
    arr = np.array(image)
    alpha = arr[:, :, 3]

    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)

    if not rows.any():
        # Fully transparent — return as-is
        return image, (0, 0, image.width, image.height)

    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))

    trimmed = image.crop((left, top, right, bottom))
    return trimmed, (left, top, right, bottom)


def normalize_sprite(
    source: bytes | Path | Image.Image,
    alpha_policy: str = "binary",
    alpha_threshold: float = 0.5,
    remove_bg: bool = False,
    bg_tolerance: int = 30,
) -> Image.Image:
    """Full ingest pipeline: load → optional bg removal → alpha policy."""
    img = load_image(source)

    if remove_bg:
        img = remove_background(img, bg_tolerance)

    img = apply_alpha_policy(img, alpha_policy, alpha_threshold)

    return img
