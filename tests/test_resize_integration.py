"""Integration tests for the full cleanup → pixelate → regularize → resize pipeline."""

from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from scipy.ndimage import binary_erosion, label

from pixel_magic.cleanup import cleanup_sprite
from pixel_magic.resize import add_outline, resize_sprite


def _make_synthetic_sprite(size: int = 40) -> Image.Image:
    """Create a synthetic high-res sprite mimicking rembg output.

    Has: solid body, semi-transparent edges, a few chromakey-dominant fringe
    pixels, and some dark outline pixels.
    """
    arr = np.zeros((size, size, 4), dtype=np.uint8)

    # Body: solid interior
    margin = 6
    arr[margin : size - margin, margin : size - margin] = [120, 90, 70, 255]

    # Dark outline around body
    for y in range(margin, size - margin):
        for x in range(margin, size - margin):
            if (
                y == margin
                or y == size - margin - 1
                or x == margin
                or x == size - margin - 1
            ):
                arr[y, x] = [15, 15, 15, 255]

    # Semi-transparent edge fringe (simulating rembg soft edges)
    for y in range(margin - 1, size - margin + 1):
        if 0 <= y < size:
            if margin - 1 >= 0:
                arr[y, margin - 1] = [100, 80, 60, 128]
            if size - margin < size:
                arr[y, size - margin] = [100, 80, 60, 100]
    for x in range(margin - 1, size - margin + 1):
        if 0 <= x < size:
            if margin - 1 >= 0:
                arr[margin - 1, x] = [90, 70, 50, 140]
            if size - margin < size:
                arr[size - margin, x] = [90, 70, 50, 80]

    # A few green-dominant fringe pixels
    arr[margin - 2, margin : margin + 3] = [20, 180, 15, 50]

    return Image.fromarray(arr, "RGBA")


class TestCleanedSpriteBinaryAlpha:
    def test_full_pipeline_binary_alpha(self):
        """After cleanup + regularize, output has binary alpha."""
        sprite = _make_synthetic_sprite(40)

        cleaned = cleanup_sprite(sprite, chromakey_color="green")
        regularized = add_outline(cleaned)

        arr = np.array(regularized)
        unique_alpha = set(np.unique(arr[:, :, 3]))
        assert unique_alpha <= {0, 255}, f"Expected binary alpha, got {unique_alpha}"


class TestOuterBoundaryIsDark:
    def test_boundary_predominantly_dark(self):
        """Output outer boundary pixels are predominantly dark."""
        sprite = _make_synthetic_sprite(40)

        cleaned = cleanup_sprite(sprite, chromakey_color="green")
        regularized = add_outline(cleaned)

        arr = np.array(regularized)
        opaque = arr[:, :, 3] == 255

        if not opaque.any():
            pytest.skip("No opaque pixels")

        struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        eroded = binary_erosion(opaque, structure=struct)
        boundary = opaque & ~eroded

        boundary_count = boundary.sum()
        if boundary_count == 0:
            pytest.skip("No boundary pixels")

        r = arr[:, :, 0][boundary]
        g = arr[:, :, 1][boundary]
        b = arr[:, :, 2][boundary]
        max_ch = np.maximum(np.maximum(r, g), b)
        dark_count = (max_ch <= 40).sum()

        coverage = dark_count / boundary_count
        assert coverage >= 0.9, f"Dark boundary coverage {coverage:.2%} < 90%"


class TestNoChromakeyOnBoundary:
    def test_no_green_dominant_on_boundary(self):
        """No chromakey-dominant pixels survive on the opaque boundary."""
        sprite = _make_synthetic_sprite(40)

        cleaned = cleanup_sprite(sprite, chromakey_color="green")
        regularized = add_outline(cleaned)

        arr = np.array(regularized)
        opaque = arr[:, :, 3] == 255

        if not opaque.any():
            pytest.skip("No opaque pixels")

        struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        eroded = binary_erosion(opaque, structure=struct)
        boundary = opaque & ~eroded

        r = arr[:, :, 0][boundary]
        g = arr[:, :, 1][boundary]
        b = arr[:, :, 2][boundary]
        green_dominant = g > (np.maximum(r, b).astype(np.int16) + 30)

        assert not green_dominant.any(), "Green-dominant pixels found on boundary"


class TestResizePreservesAlpha:
    def test_alpha_survives_pixelate_returning_rgb(self):
        """Transparency is preserved even when pixelate drops the alpha channel."""
        # Create an RGBA sprite with a transparent border and opaque center
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[5:15, 5:15] = [120, 80, 60, 255]
        sprite = Image.fromarray(arr, "RGBA")

        # Mock pixelate to return an RGB image (simulating alpha loss)
        def fake_pixelate(img, num_colors=None):
            return img.convert("RGB").resize((10, 10), Image.NEAREST)

        with patch("proper_pixel_art.pixelate.pixelate", side_effect=fake_pixelate):
            result = resize_sprite(sprite, size=16)

        result_arr = np.array(result)
        unique_alpha = set(np.unique(result_arr[:, :, 3]))
        assert 0 in unique_alpha, "Transparent pixels should survive resize"
        assert 255 in unique_alpha, "Opaque pixels should survive resize"

    def test_alpha_preserved_when_pixelate_keeps_rgba(self):
        """Transparency is preserved when pixelate returns RGBA correctly."""
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[5:15, 5:15] = [120, 80, 60, 255]
        sprite = Image.fromarray(arr, "RGBA")

        # Mock pixelate to return RGBA with correct alpha
        def fake_pixelate(img, num_colors=None):
            return img.resize((10, 10), Image.NEAREST)

        with patch("proper_pixel_art.pixelate.pixelate", side_effect=fake_pixelate):
            result = resize_sprite(sprite, size=16)

        result_arr = np.array(result)
        unique_alpha = set(np.unique(result_arr[:, :, 3]))
        assert 0 in unique_alpha, "Transparent pixels should survive resize"
        assert 255 in unique_alpha, "Opaque pixels should survive resize"


class TestRegressionComponentIntegrity:
    def test_cleanup_does_not_merge_separate_components(self):
        """Cleanup preserves separate connected components."""
        # Two separate blobs
        arr = np.zeros((20, 30, 4), dtype=np.uint8)
        arr[3:9, 3:9] = [100, 80, 60, 255]
        arr[3:9, 15:21] = [100, 80, 60, 255]
        image = Image.fromarray(arr, "RGBA")

        result = cleanup_sprite(image, chromakey_color="green")
        result_arr = np.array(result)

        opaque = result_arr[:, :, 3] == 255
        _, n = label(opaque, structure=np.ones((3, 3), dtype=int))
        assert n == 2, f"Expected 2 components, got {n}"
