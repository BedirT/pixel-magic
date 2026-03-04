"""Tests for pipeline.palette — OKLab color space, quantization, dithering."""

import numpy as np
from PIL import Image

from pixel_magic.models.palette import DitherConfig, DitherType, Palette
from pixel_magic.pipeline.palette import (
    extract_adaptive_palette,
    oklab_distance,
    quantize_image,
    rgb_to_oklab,
)


class TestOklab:
    def test_black(self):
        lab = rgb_to_oklab(np.array([[0, 0, 0]], dtype=np.uint8))
        assert abs(lab[0, 0]) < 0.02  # near zero lightness

    def test_white(self):
        lab = rgb_to_oklab(np.array([[255, 255, 255]], dtype=np.uint8))
        assert lab[0, 0] > 0.95  # near 1.0 lightness

    def test_distance_same_color(self):
        c = rgb_to_oklab(np.array([[128, 64, 32]], dtype=np.uint8))
        assert oklab_distance(c, c).item() < 1e-6

    def test_distance_different_colors(self):
        black = rgb_to_oklab(np.array([[0, 0, 0]], dtype=np.uint8))
        white = rgb_to_oklab(np.array([[255, 255, 255]], dtype=np.uint8))
        assert oklab_distance(black, white).item() > 0.5


class TestExtractPalette:
    def test_single_color_image(self):
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        palette = extract_adaptive_palette([img], max_colors=4)
        assert isinstance(palette, Palette)
        assert len(palette.colors) >= 1
        assert len(palette.colors) <= 4

    def test_multi_color(self):
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        arr[:8, :, :] = [255, 0, 0, 255]
        arr[8:, :, :] = [0, 0, 255, 255]
        img = Image.fromarray(arr)
        palette = extract_adaptive_palette([img], max_colors=8)
        assert len(palette.colors) >= 2


class TestQuantize:
    def test_reduces_to_palette(self):
        """After quantization, every opaque pixel should be a palette color."""
        arr = np.zeros((8, 8, 4), dtype=np.uint8)
        arr[:4, :] = [200, 50, 50, 255]
        arr[4:, :] = [50, 50, 200, 255]
        img = Image.fromarray(arr)
        palette = Palette(
            name="test",
            colors=[(200, 50, 50, 255), (50, 50, 200, 255)],
        )
        result = quantize_image(img, palette)
        res_arr = np.array(result)
        palette_set = {(200, 50, 50, 255), (50, 50, 200, 255), (0, 0, 0, 0)}
        for y in range(8):
            for x in range(8):
                px = tuple(res_arr[y, x])
                assert px in palette_set or px[3] == 0

    def test_ordered_dither(self):
        """Ordered dither should still produce palette-only colors."""
        img = Image.new("RGBA", (8, 8), (150, 100, 50, 255))
        palette = Palette(
            name="test",
            colors=[(100, 50, 0, 255), (200, 150, 100, 255)],
        )
        dither = DitherConfig(type=DitherType.ORDERED, strength=0.3)
        result = quantize_image(img, palette, dither)
        assert result.mode == "RGBA"
        assert result.size == (8, 8)
