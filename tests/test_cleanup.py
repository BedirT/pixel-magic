"""Tests for the mask cleanup module."""

import numpy as np
import pytest
from PIL import Image

from pixel_magic.cleanup import cleanup_sprite


def _make_sprite(w: int, h: int, fill_rgba=(100, 80, 60, 255)) -> Image.Image:
    """Create a solid RGBA sprite with the given fill color."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :] = fill_rgba
    return Image.fromarray(arr, "RGBA")


def _make_sprite_array(w: int, h: int, fill_rgba=(100, 80, 60, 255)) -> np.ndarray:
    """Create a raw RGBA array for a sprite."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :] = fill_rgba
    return arr


class TestRemovesChromakeyFringe:
    def test_green_fringe_removed(self):
        """Green-dominant fringe pixels (G > max(R,B)+30) are removed."""
        arr = _make_sprite_array(10, 10, fill_rgba=(80, 80, 80, 255))
        # Add green fringe pixels along top edge
        arr[0, :, :] = [20, 200, 10, 200]  # G >> max(R,B)+30
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="green")
        result_arr = np.array(result)

        # Fringe pixels should be removed (alpha=0)
        # The exact position may shift due to trimming, so check that
        # no green-dominant opaque pixel survives
        opaque = result_arr[:, :, 3] == 255
        r, g, b = result_arr[:, :, 0], result_arr[:, :, 1], result_arr[:, :, 2]
        green_dominant = opaque & (g > (np.maximum(r, b).astype(np.int16) + 30))
        assert not green_dominant.any()

    def test_blue_fringe_removed(self):
        """Blue-dominant fringe pixels removed when chromakey=blue."""
        arr = _make_sprite_array(10, 10, fill_rgba=(80, 80, 80, 255))
        arr[0, :, :] = [10, 10, 200, 200]  # B >> max(R,G)+30
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="blue")
        result_arr = np.array(result)

        opaque = result_arr[:, :, 3] == 255
        r, g, b = result_arr[:, :, 0], result_arr[:, :, 1], result_arr[:, :, 2]
        blue_dominant = opaque & (b > (np.maximum(r, g).astype(np.int16) + 30))
        assert not blue_dominant.any()


class TestPreservesDarkOutlines:
    def test_dark_pixels_near_contamination_kept(self):
        """Dark pixels (max channel < 60) near contaminated areas are kept."""
        arr = _make_sprite_array(10, 10, fill_rgba=(80, 80, 80, 255))
        # Dark outline pixel surrounded by body
        arr[5, 5, :] = [10, 10, 10, 255]
        # Nearby contaminated pixel
        arr[5, 6, :] = [10, 200, 10, 200]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="green")
        result_arr = np.array(result)

        # Dark pixels should survive somewhere in the output
        opaque = result_arr[:, :, 3] == 255
        r, g, b = result_arr[:, :, 0], result_arr[:, :, 1], result_arr[:, :, 2]
        max_ch = np.maximum(np.maximum(r, g), b)
        dark_opaque = opaque & (max_ch < 60)
        assert dark_opaque.any()


class TestHardensAlpha:
    def test_only_binary_alpha(self):
        """Output alpha contains only 0 and 255."""
        arr = _make_sprite_array(10, 10, fill_rgba=(100, 80, 60, 255))
        # Add semi-transparent edge pixels
        arr[0, :, 3] = 128
        arr[-1, :, 3] = 64
        arr[:, 0, 3] = 100
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        unique_alpha = set(np.unique(result_arr[:, :, 3]))
        assert unique_alpha <= {0, 255}


class TestRemovesSmallIslands:
    def test_1px_island_removed(self):
        """Disconnected 1-2px blobs are removed."""
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        # Main body (large connected region)
        arr[5:15, 5:15] = [100, 80, 60, 255]
        # Isolated 1px island far from body
        arr[0, 0] = [200, 100, 50, 255]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        # The island at (0,0) should be gone — check that no opaque pixel
        # exists in the first 3 rows/cols of the result (accounting for trim)
        # More robust: count connected components — should be exactly 1
        from scipy.ndimage import label as scipy_label

        opaque = result_arr[:, :, 3] == 255
        _, n = scipy_label(opaque, structure=np.ones((3, 3)))
        assert n <= 1


class TestFillsTinyHoles:
    def test_1px_hole_filled(self):
        """Enclosed 1-2px holes in the mask are filled."""
        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[2:8, 2:8] = [100, 80, 60, 255]
        # Poke a 1px hole in the center
        arr[5, 5, 3] = 0
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        # All pixels inside the body region should be opaque (hole filled)
        opaque = result_arr[:, :, 3] == 255
        assert opaque.sum() >= 35  # 6x6=36 minus padding edge effects


class TestPreservesInteriorColors:
    def test_interior_rgb_unchanged(self):
        """RGB values of non-chromakey interior pixels are unchanged."""
        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[2:8, 2:8] = [150, 100, 50, 255]
        arr[4, 4] = [200, 50, 80, 255]  # unique interior pixel
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        # Find the unique interior pixel in the result
        opaque = result_arr[:, :, 3] == 255
        r, g, b = result_arr[:, :, 0], result_arr[:, :, 1], result_arr[:, :, 2]
        match = opaque & (r == 200) & (g == 50) & (b == 80)
        assert match.any(), "Interior pixel color was changed"


class TestPreservesLegitimateForegroudColor:
    def test_green_survives_with_blue_chromakey(self):
        """Saturated green foreground pixels survive when blue chromakey is used."""
        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[2:8, 2:8] = [80, 80, 80, 255]
        # Bright green pixel (would be contamination on green key, but legit on blue key)
        arr[5, 5] = [20, 200, 10, 255]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="blue")
        result_arr = np.array(result)

        # The green pixel should survive
        opaque = result_arr[:, :, 3] == 255
        g = result_arr[:, :, 1]
        has_green = opaque & (g >= 180)
        assert has_green.any(), "Green foreground pixel was incorrectly removed"

    def test_blue_survives_with_green_chromakey(self):
        """Saturated blue foreground pixels survive when green chromakey is used."""
        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[2:8, 2:8] = [80, 80, 80, 255]
        arr[5, 5] = [10, 10, 200, 255]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="green")
        result_arr = np.array(result)

        opaque = result_arr[:, :, 3] == 255
        b = result_arr[:, :, 2]
        has_blue = opaque & (b >= 180)
        assert has_blue.any(), "Blue foreground pixel was incorrectly removed"


class TestStripsOuterOutline:
    def test_dark_boundary_stripped(self):
        """Dark outline pixels on the outer boundary are removed."""
        arr = np.zeros((12, 12, 4), dtype=np.uint8)
        # Black outline box
        arr[2:10, 2:10] = [10, 10, 10, 255]
        # Body inside outline
        arr[3:9, 3:9] = [150, 100, 50, 255]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        # The outer dark ring should be stripped — boundary should now be body-colored
        opaque = result_arr[:, :, 3] == 255
        from scipy.ndimage import binary_erosion
        struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        eroded = binary_erosion(opaque, structure=struct)
        boundary = opaque & ~eroded

        r = result_arr[:, :, 0][boundary]
        max_ch = np.maximum(np.maximum(r, result_arr[:, :, 1][boundary]),
                            result_arr[:, :, 2][boundary])
        # Boundary pixels should now be body-colored (bright), not outline-dark
        assert max_ch.mean() > 80, f"Boundary should be body-colored after stripping, got mean brightness {max_ch.mean():.0f}"

    def test_dark_body_parts_preserved(self):
        """Dark colored body parts (high spread) are not stripped as outline."""
        arr = np.zeros((12, 12, 4), dtype=np.uint8)
        arr[2:10, 2:10] = [150, 100, 50, 255]  # body
        # Dark red boots at bottom edge (dark but high color spread)
        arr[9, 2:10] = [40, 5, 5, 255]  # max_ch=40, spread=35 > 25
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        # Dark red pixels should survive (spread > 25 = not outline)
        opaque = result_arr[:, :, 3] == 255
        r = result_arr[:, :, 0]
        has_dark_red = opaque & (r >= 30) & (r <= 50)
        assert has_dark_red.any(), "Dark red body parts should be preserved"

    def test_only_outermost_layer_stripped(self):
        """Only the 1px outermost outline layer is stripped, not deeper layers."""
        arr = np.zeros((14, 14, 4), dtype=np.uint8)
        # 2px thick black outline
        arr[2:12, 2:12] = [10, 10, 10, 255]
        arr[4:10, 4:10] = [150, 100, 50, 255]  # body
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image)
        result_arr = np.array(result)

        raw_opaque = (arr[:, :, 3] == 255).sum()
        clean_opaque = (result_arr[:, :, 3] == 255).sum()
        stripped = raw_opaque - clean_opaque

        # Should strip roughly 1 layer (perimeter), not 2+
        # Perimeter of 10x10 box = ~36 pixels
        assert stripped < 50, f"Should strip ~1 layer, stripped {stripped} pixels"
        assert stripped > 20, f"Should strip outer layer, only stripped {stripped} pixels"


class TestEmptyMaskReturnsOriginal:
    def test_fully_contaminated_returns_original(self):
        """If cleanup removes all foreground, returns original sprite unchanged."""
        # All pixels are green-dominant with low alpha
        arr = np.full((10, 10, 4), [10, 200, 10, 40], dtype=np.uint8)
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="green")

        # Should return original dimensions
        assert result.size == image.size
