"""Tests for pipeline.projection — downsample and upscale."""

import numpy as np
from PIL import Image

from pixel_magic.pipeline.projection import project_to_grid, upscale_nearest


class TestProjectToGrid:
    def test_basic_downsample(self):
        """4x4 image with macro_size=2 → 2x2 output."""
        arr = np.zeros((4, 4, 4), dtype=np.uint8)
        arr[:2, :2] = [255, 0, 0, 255]
        arr[:2, 2:] = [0, 255, 0, 255]
        arr[2:, :2] = [0, 0, 255, 255]
        arr[2:, 2:] = [255, 255, 0, 255]
        img = Image.fromarray(arr)
        result = project_to_grid(img, macro_size=2)
        assert result.size == (2, 2)
        res_arr = np.array(result)
        assert tuple(res_arr[0, 0, :3]) == (255, 0, 0)
        assert tuple(res_arr[0, 1, :3]) == (0, 255, 0)

    def test_preserves_transparency(self):
        """Cells that are mostly transparent should remain transparent."""
        arr = np.zeros((4, 4, 4), dtype=np.uint8)
        # Top-left cell is transparent
        # Bottom-right cell is opaque
        arr[2:, 2:] = [128, 128, 128, 255]
        img = Image.fromarray(arr)
        result = project_to_grid(img, macro_size=2)
        res_arr = np.array(result)
        assert res_arr[0, 0, 3] == 0
        assert res_arr[1, 1, 3] == 255


class TestUpscaleNearest:
    def test_2x_upscale(self):
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        result = upscale_nearest(img, scale=2)
        assert result.size == (8, 8)

    def test_pixel_preservation(self):
        """Each pixel should become a scale×scale block."""
        arr = np.zeros((2, 2, 4), dtype=np.uint8)
        arr[0, 0] = [255, 0, 0, 255]
        arr[0, 1] = [0, 255, 0, 255]
        arr[1, 0] = [0, 0, 255, 255]
        arr[1, 1] = [255, 255, 0, 255]
        img = Image.fromarray(arr)
        result = upscale_nearest(img, scale=3)
        res_arr = np.array(result)
        # Top-left 3x3 block should all be red
        assert np.all(res_arr[:3, :3, 0] == 255)
        assert np.all(res_arr[:3, :3, 1] == 0)
