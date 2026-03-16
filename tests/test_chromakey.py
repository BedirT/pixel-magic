"""Tests for pipeline.chromakey — HSV-based chromakey background removal."""

import numpy as np
from PIL import Image

from pixel_magic.pipeline.chromakey import chromakey_color_to_rgb, remove_chromakey


def _make_green_bg_sprite(
    size: int = 64,
    sprite_color: tuple[int, int, int] = (200, 50, 50),
    sprite_size: int = 30,
) -> Image.Image:
    """Create an image with a red sprite on a green chromakey background."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    # Fill with chromakey green
    arr[:, :, 1] = 255  # G=255
    arr[:, :, 3] = 255  # fully opaque

    # Place a sprite in the center
    offset = (size - sprite_size) // 2
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 0] = sprite_color[0]
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 1] = sprite_color[1]
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 2] = sprite_color[2]

    return Image.fromarray(arr, "RGBA")


def _make_blue_bg_sprite(size: int = 64, sprite_size: int = 30) -> Image.Image:
    """Create an image with a red sprite on a blue chromakey background."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, 2] = 255  # B=255
    arr[:, :, 3] = 255

    offset = (size - sprite_size) // 2
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 0] = 200
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 1] = 50
    arr[offset : offset + sprite_size, offset : offset + sprite_size, 2] = 50

    return Image.fromarray(arr, "RGBA")


def test_green_bg_removed():
    """Green background pixels become transparent, sprite preserved."""
    img = _make_green_bg_sprite()
    result = remove_chromakey(img, color="green")
    arr = np.array(result)

    # Green background corners should be transparent
    assert arr[0, 0, 3] == 0
    assert arr[0, -1, 3] == 0
    assert arr[-1, 0, 3] == 0
    assert arr[-1, -1, 3] == 0

    # Center sprite should be opaque
    cx, cy = 32, 32
    assert arr[cy, cx, 3] == 255
    assert arr[cy, cx, 0] == 200  # R preserved


def test_blue_bg_removed():
    """Blue background removed with color='blue' preset."""
    img = _make_blue_bg_sprite()
    result = remove_chromakey(img, color="blue")
    arr = np.array(result)

    assert arr[0, 0, 3] == 0
    assert arr[32, 32, 3] == 255


def test_forest_green_sprite_preserved():
    """Non-chromakey green (forest green #228B22) should be preserved."""
    img = _make_green_bg_sprite(sprite_color=(34, 139, 34), sprite_size=30)
    result = remove_chromakey(img, color="green")
    arr = np.array(result)

    # Background gone
    assert arr[0, 0, 3] == 0

    # Forest green sprite center preserved (different saturation/hue from #00FF00)
    cx, cy = 32, 32
    assert arr[cy, cx, 3] == 255


def test_already_transparent_passthrough():
    """Image with mostly transparent pixels should pass through unchanged."""
    arr = np.zeros((64, 64, 4), dtype=np.uint8)
    # Only a small opaque sprite in center
    arr[20:44, 20:44, :3] = [200, 50, 50]
    arr[20:44, 20:44, 3] = 255
    # Rest is transparent (alpha=0)

    img = Image.fromarray(arr, "RGBA")
    result = remove_chromakey(img, color="green")

    # Should be unchanged — the function skips mostly-transparent images
    result_arr = np.array(result)
    np.testing.assert_array_equal(result_arr, arr)


def test_magenta_separators_not_affected():
    """Magenta (#FF00FF) separator columns should survive green chromakey removal."""
    arr = np.zeros((64, 100, 4), dtype=np.uint8)
    # Green background
    arr[:, :, 1] = 255
    arr[:, :, 3] = 255

    # Add magenta separator columns at x=32 and x=65
    for sep_x in [32, 65]:
        arr[:, sep_x, 0] = 255
        arr[:, sep_x, 1] = 0
        arr[:, sep_x, 2] = 255

    img = Image.fromarray(arr, "RGBA")
    result = remove_chromakey(img, color="green")
    result_arr = np.array(result)

    # Green should be removed
    assert result_arr[0, 0, 3] == 0

    # Magenta separators should remain opaque
    assert result_arr[32, 32, 3] == 255
    assert result_arr[32, 65, 3] == 255


def test_chromakey_color_to_rgb():
    """Verify preset RGB values."""
    assert chromakey_color_to_rgb("green") == (0, 255, 0)
    assert chromakey_color_to_rgb("blue") == (0, 0, 255)
