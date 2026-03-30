"""Resize sprites to true pixel art at target sizes.

AI-generated sprites look pixel-art-ish but are actually high-res with
anti-aliasing and sub-pixel detail. This module uses proper-pixel-art
(https://github.com/KennethJAllen/proper-pixel-art) to detect the
underlying pixel grid via edge detection + Hough line transform, sample
the dominant color per cell, and produce genuine pixel art.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion

# Supported target sizes (square)
VALID_SIZES = [16, 32, 48, 64, 96, 128, 256]


def resize_sprite(
    sprite: Image.Image,
    size: int,
    num_colors: int | None = None,
) -> Image.Image:
    """Convert a sprite to true pixel art at the target size.

    Uses proper-pixel-art to detect the real pixel grid in the AI output,
    then resizes to the target dimensions with nearest-neighbor to preserve
    hard pixel edges.

    Args:
        sprite: RGBA source sprite (any resolution).
        size: Target pixel grid size (e.g. 32 for 32x32).
        num_colors: Optional palette size for color quantization.
            None preserves original colors.

    Returns:
        RGBA image at exactly size x size.
    """
    sprite = sprite.convert("RGBA")

    # Detect pixel grid and produce true pixel art
    try:
        from proper_pixel_art.pixelate import pixelate
    except ImportError as exc:
        raise RuntimeError(
            "proper-pixel-art requires OpenCV runtime libraries (libGL). "
            "Install system OpenCV dependencies before calling resize_sprite."
        ) from exc

    # proper-pixel-art can drop alpha when quantizing colors.
    # Preserve the original alpha mask and reapply after pixelation.
    orig_alpha = sprite.getchannel("A")

    pixelated = pixelate(sprite, num_colors=num_colors)

    # Ensure RGBA — pixelate may return RGB when alpha is lost
    pixelated = pixelated.convert("RGBA")

    # Downscale original alpha to match pixelated size and reapply
    pix_w, pix_h = pixelated.size
    scaled_alpha = orig_alpha.resize((pix_w, pix_h), Image.NEAREST)
    # Use the stricter of the two: if pixelate kept some alpha info, AND it
    # with the original; otherwise just restore the original mask.
    pix_alpha = pixelated.getchannel("A")
    merged_alpha = Image.fromarray(
        np.minimum(np.array(scaled_alpha), np.array(pix_alpha))
    )
    pixelated.putalpha(merged_alpha)

    # Regularize contours on the small pixelated result
    pixelated = add_outline(pixelated)

    # Fit into target box preserving aspect ratio, nearest-neighbor
    w, h = pixelated.size
    scale = min(size / w, size / h)
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    resized = pixelated.resize((new_w, new_h), Image.NEAREST)

    # Center on transparent canvas
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    return canvas


def parse_sizes(sizes_str: str) -> list[int]:
    """Parse comma-separated size string, validating each value.

    Args:
        sizes_str: e.g. "16,32,64" or "all"

    Returns:
        Sorted list of valid sizes.

    Raises:
        ValueError: If any size is not in VALID_SIZES.
    """
    if sizes_str.strip().lower() == "all":
        return list(VALID_SIZES)

    sizes = []
    for part in sizes_str.split(","):
        s = int(part.strip())
        if s not in VALID_SIZES:
            raise ValueError(
                f"Invalid size {s}. Valid sizes: {', '.join(map(str, VALID_SIZES))}"
            )
        if s not in sizes:
            sizes.append(s)

    return sorted(sizes)


# ---------------------------------------------------------------------------
# Outline enforcement — adds 1px black outline on pixelated sprites
# ---------------------------------------------------------------------------


def add_outline(image: Image.Image) -> Image.Image:
    """Add a clean 1px black outline around a sprite.

    Works at any resolution. The AI's original outlines are stripped
    during cleanup; this adds a uniform 1px black outline back.
    """
    arr = np.array(image.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    opaque = alpha == 255

    if not opaque.any():
        return image

    # Find the 1px outer boundary (4-connectivity)
    struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    eroded = binary_erosion(opaque, structure=struct)
    boundary = opaque & ~eroded

    # Paint all boundary pixels black
    arr[boundary, 0] = 0
    arr[boundary, 1] = 0
    arr[boundary, 2] = 0

    return Image.fromarray(arr, "RGBA")
