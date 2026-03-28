"""Tests for the flood-fill chromakey background removal."""

import numpy as np
import pytest
from PIL import Image

from pixel_magic.background import remove_background


def _make_chromakey_image(
    w: int, h: int,
    sprite_rect: tuple[int, int, int, int],
    sprite_color: tuple[int, int, int] = (100, 80, 60),
    bg_color: tuple[int, int, int] = (0, 255, 0),
) -> Image.Image:
    """Create a fully opaque image with a sprite on a chromakey background."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :, :3] = bg_color
    arr[:, :, 3] = 255  # fully opaque

    y1, x1, y2, x2 = sprite_rect
    arr[y1:y2, x1:x2, :3] = sprite_color

    return Image.fromarray(arr, "RGBA")


class TestFloodFillRemoval:
    def test_green_background_removed(self):
        """Green chromakey background becomes transparent."""
        img = _make_chromakey_image(20, 20, (5, 5, 15, 15), bg_color=(0, 255, 0))
        result = remove_background(img, chromakey_color="green")
        arr = np.array(result)

        # Background pixels (outside sprite rect) should be transparent
        assert arr[0, 0, 3] == 0
        assert arr[19, 19, 3] == 0

        # Sprite pixels should be opaque
        assert arr[10, 10, 3] == 255

    def test_blue_background_removed(self):
        """Blue chromakey background becomes transparent."""
        img = _make_chromakey_image(20, 20, (5, 5, 15, 15), bg_color=(0, 0, 255))
        result = remove_background(img, chromakey_color="blue")
        arr = np.array(result)

        assert arr[0, 0, 3] == 0
        assert arr[10, 10, 3] == 255

    def test_binary_alpha_only(self):
        """Output has only alpha 0 or 255."""
        img = _make_chromakey_image(20, 20, (5, 5, 15, 15))
        result = remove_background(img)
        arr = np.array(result)

        unique_alpha = set(np.unique(arr[:, :, 3]))
        assert unique_alpha <= {0, 255}

    def test_approximate_green_removed(self):
        """Near-green background (JPEG compression artifacts) is removed."""
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        # Approximate green — not exact #00FF00
        arr[:, :, :3] = [5, 248, 3]
        # Sprite in center
        arr[5:15, 5:15, :3] = [100, 80, 60]

        img = Image.fromarray(arr, "RGBA")
        result = remove_background(img)
        result_arr = np.array(result)

        assert result_arr[0, 0, 3] == 0, "Approximate green should be removed"
        assert result_arr[10, 10, 3] == 255, "Sprite should remain"

    def test_interior_green_preserved(self):
        """Green pixels inside the sprite (not connected to border) are preserved."""
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        arr[:, :, :3] = [0, 255, 0]  # green background

        # Sprite body with black outline enclosing green interior
        arr[4:16, 4:16, :3] = [0, 0, 0]  # black outline box
        arr[5:15, 5:15, :3] = [0, 200, 0]  # green interior (orc skin)

        img = Image.fromarray(arr, "RGBA")
        result = remove_background(img)
        result_arr = np.array(result)

        # Interior green should be preserved (flood fill can't reach it)
        assert result_arr[10, 10, 3] == 255, "Interior green should be opaque"
        assert result_arr[10, 10, 1] >= 180, "Interior green color should be preserved"

    def test_does_not_leak_through_diagonal(self):
        """4-connectivity prevents flood fill from leaking through diagonal gaps."""
        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        arr[:, :, :3] = [0, 255, 0]  # green background

        # Sprite with diagonal outline (1px gap at corners)
        #   G G G G G G G G G G
        #   G G G G G G G G G G
        #   G G B G G G G G G G
        #   G G G B G G G G G G
        #   G G G G B G G G G G
        #   G G G G G B G G G G
        #   G G G G G G B G G G
        #   G G G G G G G G G G
        # The diagonal B pixels have diagonal gaps — 4-connectivity should NOT leak through
        for i in range(2, 7):
            arr[i, i, :3] = [0, 0, 0]

        img = Image.fromarray(arr, "RGBA")
        result = remove_background(img)
        result_arr = np.array(result)

        # The diagonal line pixels should remain opaque
        for i in range(2, 7):
            assert result_arr[i, i, 3] == 255, f"Diagonal pixel ({i},{i}) should be opaque"


class TestBoundaryDespill:
    def test_green_fringe_clamped(self):
        """Boundary pixels have green channel clamped to max(R, B)."""
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        arr[:, :, :3] = [0, 255, 0]  # green bg

        # Sprite with green-tinted edge pixels (JPEG bleed)
        arr[5:15, 5:15, :3] = [100, 80, 60]  # normal body
        arr[5, 5:15, :3] = [50, 150, 30]  # top edge — green-tinted

        img = Image.fromarray(arr, "RGBA")
        result = remove_background(img)
        result_arr = np.array(result)

        # Edge pixels should have green clamped: G <= max(R, B)
        opaque = result_arr[:, :, 3] == 255
        r = result_arr[:, :, 0][opaque]
        g = result_arr[:, :, 1][opaque]
        b = result_arr[:, :, 2][opaque]
        max_rb = np.maximum(r, b)
        # Allow small tolerance for rounding
        assert (g <= max_rb + 1).all(), "Green should be clamped on boundary"
