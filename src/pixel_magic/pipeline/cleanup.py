"""Cleanup — AA removal, island removal, hole filling, outline enforcement."""

from __future__ import annotations

import numpy as np
from PIL import Image


def remove_aa_artifacts(
    image: Image.Image,
    palette_colors: list[tuple[int, int, int, int]],
) -> Image.Image:
    """Snap edge-adjacent pixels with intermediate colors to nearest palette color.

    Finds pixels whose RGB isn't in the palette and snaps them.
    """
    arr = np.array(image)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]

    # Build set of palette RGB tuples for fast lookup
    pal_set = {(c[0], c[1], c[2]) for c in palette_colors}
    pal_arr = np.array([c[:3] for c in palette_colors], dtype=np.float32)

    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)

    # Find off-palette pixels
    is_palette = np.array(
        [tuple(int(v) for v in p) in pal_set for p in flat],
        dtype=bool,
    )
    off_palette = ~is_palette

    if not off_palette.any():
        return image

    # Snap off-palette pixels to nearest palette color (Euclidean in RGB)
    off_pixels = flat[off_palette].astype(np.float32)
    dists = np.linalg.norm(off_pixels[:, None, :] - pal_arr[None, :, :], axis=2)
    nearest_idx = np.argmin(dists, axis=1)
    flat[off_palette] = pal_arr[nearest_idx].astype(np.uint8)

    arr[:, :, :3] = flat.reshape(h, w, 3)
    return Image.fromarray(arr, "RGBA")


def remove_islands(image: Image.Image, min_size: int = 2) -> Image.Image:
    """Remove small disconnected opaque regions (islands) below min_size pixels."""
    try:
        from skimage import measure
    except ImportError:
        return image  # graceful fallback

    arr = np.array(image)
    alpha = arr[:, :, 3]
    binary = (alpha > 128).astype(np.uint8)

    labels = measure.label(binary, connectivity=1)
    for region in measure.regionprops(labels):
        if region.area < min_size:
            coords = region.coords
            arr[coords[:, 0], coords[:, 1], 3] = 0

    return Image.fromarray(arr, "RGBA")


def fill_holes(image: Image.Image, max_size: int = 2) -> Image.Image:
    """Fill small transparent holes within opaque regions."""
    try:
        from skimage import measure
    except ImportError:
        return image

    arr = np.array(image)
    alpha = arr[:, :, 3]
    transparent = (alpha <= 128).astype(np.uint8)

    labels = measure.label(transparent, connectivity=1)
    for region in measure.regionprops(labels):
        if region.area <= max_size:
            coords = region.coords
            # Check if this hole is fully surrounded by opaque pixels
            # (not touching the image border)
            min_r, min_c = coords.min(axis=0)
            max_r, max_c = coords.max(axis=0)
            h, w = alpha.shape
            if min_r > 0 and min_c > 0 and max_r < h - 1 and max_c < w - 1:
                # Fill with average of surrounding opaque pixels
                for r, c in coords:
                    neighbors = []
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and alpha[nr, nc] > 128:
                            neighbors.append(arr[nr, nc, :3])
                    if neighbors:
                        avg = np.mean(neighbors, axis=0).astype(np.uint8)
                        arr[r, c, :3] = avg
                        arr[r, c, 3] = 255

    return Image.fromarray(arr, "RGBA")


def enforce_outline(
    image: Image.Image,
    outline_color: tuple[int, int, int, int] = (0, 0, 0, 255),
) -> Image.Image:
    """Add a 1-pixel outline around the opaque silhouette."""
    arr = np.array(image)
    alpha = arr[:, :, 3]
    h, w = alpha.shape

    opaque = alpha > 128
    outline_mask = np.zeros_like(opaque)

    # Find edge pixels: transparent pixels adjacent to opaque pixels
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.zeros_like(opaque)
        src_y = slice(max(0, -dy), h - max(0, dy))
        src_x = slice(max(0, -dx), w - max(0, dx))
        dst_y = slice(max(0, dy), h - max(0, -dy))
        dst_x = slice(max(0, dx), w - max(0, -dx))
        shifted[dst_y, dst_x] = opaque[src_y, src_x]
        outline_mask |= shifted & ~opaque

    # Apply outline
    r, g, b, a = outline_color
    arr[outline_mask, 0] = r
    arr[outline_mask, 1] = g
    arr[outline_mask, 2] = b
    arr[outline_mask, 3] = a

    return Image.fromarray(arr, "RGBA")


def cleanup_sprite(
    image: Image.Image,
    palette_colors: list[tuple[int, int, int, int]] | None = None,
    min_island_size: int = 2,
    max_hole_size: int = 2,
    add_outline: bool = False,
) -> Image.Image:
    """Run the full cleanup pipeline on a sprite."""
    result = image

    if palette_colors:
        result = remove_aa_artifacts(result, palette_colors)

    result = remove_islands(result, min_island_size)
    result = fill_holes(result, max_hole_size)

    if add_outline:
        result = enforce_outline(result)

    return result
