"""Tests for the outline enforcement in resize.py."""

import numpy as np
from PIL import Image

from pixel_magic.resize import _regularize_contours


def _make_pixelated_sprite(pattern: list[list[tuple]]) -> Image.Image:
    """Create a small RGBA image from a 2D list of (R,G,B,A) tuples."""
    h = len(pattern)
    w = len(pattern[0])
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            arr[y, x] = pattern[y][x]
    return Image.fromarray(arr, "RGBA")


T = (0, 0, 0, 0)  # transparent
B = (0, 0, 0, 255)  # black (outline)
W = (200, 200, 200, 255)  # white/light (body)
R = (180, 50, 50, 255)  # red (body color)


class TestOutlineBoundary:
    def test_all_boundary_pixels_become_black(self):
        """Every outer boundary pixel is set to pure black."""
        pattern = [
            [T, T, T, T, T],
            [T, W, W, W, T],
            [T, W, W, W, T],
            [T, W, W, W, T],
            [T, T, T, T, T],
        ]
        img = _make_pixelated_sprite(pattern)
        result = _regularize_contours(img)
        arr = np.array(result)

        # All boundary pixels should be black
        for y, x in [(1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2), (3, 3)]:
            assert tuple(arr[y, x, :3]) == (0, 0, 0), \
                f"Boundary pixel ({y},{x}) should be black, got {arr[y, x, :3]}"

    def test_interior_pixels_unchanged(self):
        """Interior pixels are not modified."""
        pattern = [
            [T, T, T, T, T],
            [T, W, W, W, T],
            [T, W, R, W, T],
            [T, W, W, W, T],
            [T, T, T, T, T],
        ]
        img = _make_pixelated_sprite(pattern)
        result = _regularize_contours(img)
        arr = np.array(result)

        # Center pixel should remain red
        assert tuple(arr[2, 2, :3]) == R[:3]

    def test_already_black_boundary_unchanged(self):
        """Idempotent — running on already-outlined sprite changes nothing."""
        pattern = [
            [T, T, T, T, T],
            [T, B, B, B, T],
            [T, B, W, B, T],
            [T, B, B, B, T],
            [T, T, T, T, T],
        ]
        img = _make_pixelated_sprite(pattern)
        result = _regularize_contours(img)
        arr = np.array(result)

        for y, x in [(1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2), (3, 3)]:
            assert tuple(arr[y, x, :3]) == (0, 0, 0)
        assert tuple(arr[2, 2, :3]) == W[:3]

    def test_transparent_pixels_stay_transparent(self):
        """Transparent pixels are not affected."""
        pattern = [
            [T, T, T],
            [T, W, T],
            [T, T, T],
        ]
        img = _make_pixelated_sprite(pattern)
        result = _regularize_contours(img)
        arr = np.array(result)

        assert arr[0, 0, 3] == 0
        assert arr[0, 1, 3] == 0

    def test_highlight_preserved(self):
        """Interior highlights and texture details are not modified."""
        highlight = (240, 230, 220, 255)
        pattern = [
            [T, T, T, T, T, T],
            [T, B, B, B, B, T],
            [T, B, W, highlight, B, T],
            [T, B, W, W, B, T],
            [T, B, B, B, B, T],
            [T, T, T, T, T, T],
        ]
        img = _make_pixelated_sprite(pattern)
        result = _regularize_contours(img)
        arr = np.array(result)

        assert tuple(arr[2, 3, :3]) == highlight[:3], "Highlight should be preserved"
