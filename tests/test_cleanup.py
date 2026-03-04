"""Tests for pipeline.cleanup — AA removal, islands, holes, outlines."""

import numpy as np
from PIL import Image

from pixel_magic.pipeline.cleanup import (
    cleanup_sprite,
    enforce_outline,
    fill_holes,
    remove_aa_artifacts,
    remove_islands,
)


def _make_sprite_with_islands() -> Image.Image:
    """8x8 sprite with a solid 4x4 center and isolated 1px islands."""
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[2:6, 2:6] = [255, 0, 0, 255]  # main body
    arr[0, 0] = [0, 255, 0, 255]  # isolated pixel
    arr[7, 7] = [0, 0, 255, 255]  # isolated pixel
    return Image.fromarray(arr)


class TestRemoveIslands:
    def test_removes_single_pixel(self):
        img = _make_sprite_with_islands()
        result = remove_islands(img, min_size=2)
        arr = np.array(result)
        assert arr[0, 0, 3] == 0  # island removed
        assert arr[7, 7, 3] == 0  # island removed
        assert arr[3, 3, 3] == 255  # main body kept


class TestFillHoles:
    def test_fills_single_hole(self):
        arr = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        arr[4, 4] = [0, 0, 0, 0]  # hole
        img = Image.fromarray(arr)
        result = fill_holes(img, max_size=2)
        res_arr = np.array(result)
        assert res_arr[4, 4, 3] == 255  # hole filled


class TestEnforceOutline:
    def test_adds_outline_to_edges(self):
        arr = np.zeros((8, 8, 4), dtype=np.uint8)
        arr[2:6, 2:6] = [255, 0, 0, 255]
        img = Image.fromarray(arr)
        result = enforce_outline(img, outline_color=(0, 0, 0, 255))
        res_arr = np.array(result)
        # Edge pixels should be outline color
        assert tuple(res_arr[2, 2]) == (0, 0, 0, 255) or tuple(res_arr[1, 2]) == (0, 0, 0, 255)


class TestRemoveAA:
    def test_snaps_off_palette_pixel(self):
        """An off-palette pixel adjacent to palette pixels should be snapped."""
        arr = np.zeros((4, 4, 4), dtype=np.uint8)
        arr[:, :] = [255, 0, 0, 255]
        arr[1, 1] = [240, 10, 10, 255]  # slightly off palette
        img = Image.fromarray(arr)
        palette_colors = [(255, 0, 0, 255)]
        result = remove_aa_artifacts(img, palette_colors)
        res_arr = np.array(result)
        assert tuple(res_arr[1, 1]) == (255, 0, 0, 255)


class TestCleanupSprite:
    def test_full_pipeline(self):
        img = _make_sprite_with_islands()
        palette_colors = [(255, 0, 0, 255)]
        result = cleanup_sprite(
            img, palette_colors=palette_colors, min_island_size=2, max_hole_size=2
        )
        assert result.mode == "RGBA"
        assert result.size == (8, 8)
