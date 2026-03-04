"""Tests for pipeline.ingest — image loading, normalization, background removal."""

import numpy as np
from PIL import Image

from pixel_magic.pipeline.ingest import (
    apply_alpha_policy,
    load_image,
    normalize_sprite,
    remove_background,
    trim_transparent,
)


def _make_rgba(w: int, h: int, color: tuple = (255, 0, 0, 255)) -> Image.Image:
    """Create a solid RGBA image."""
    img = Image.new("RGBA", (w, h), color)
    return img


class TestLoadImage:
    def test_from_pil(self):
        img = _make_rgba(8, 8)
        result = load_image(img)
        assert result.mode == "RGBA"
        assert result.size == (8, 8)

    def test_from_bytes(self):
        img = _make_rgba(8, 8)
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = load_image(buf.getvalue())
        assert result.mode == "RGBA"

    def test_from_path(self, tmp_path):
        img = _make_rgba(8, 8)
        p = tmp_path / "test.png"
        img.save(p)
        result = load_image(p)
        assert result.mode == "RGBA"

    def test_rgb_converted_to_rgba(self):
        img = Image.new("RGB", (8, 8), (128, 128, 128))
        result = load_image(img)
        assert result.mode == "RGBA"


class TestAlphaPolicy:
    def test_binary_threshold(self):
        """Semi-transparent pixels should snap to 0 or 255."""
        img = Image.new("RGBA", (4, 4), (128, 0, 0, 100))
        result = apply_alpha_policy(img, "binary", threshold=0.5)
        arr = np.array(result)
        # 100 < int(0.5*255)=127 → alpha=0
        assert np.all(arr[:, :, 3] == 0)

    def test_binary_above_threshold(self):
        img = Image.new("RGBA", (4, 4), (128, 0, 0, 200))
        result = apply_alpha_policy(img, "binary", threshold=0.5)
        arr = np.array(result)
        assert np.all(arr[:, :, 3] == 255)

    def test_keep8bit_passthrough(self):
        img = Image.new("RGBA", (4, 4), (128, 0, 0, 100))
        result = apply_alpha_policy(img, "keep8bit")
        arr = np.array(result)
        assert np.all(arr[:, :, 3] == 100)


class TestRemoveBackground:
    def test_removes_solid_corner_color(self):
        """Background color sampled from corners should be made transparent."""
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        arr[:, :] = [0, 128, 0, 255]  # green bg
        arr[4:12, 4:12] = [255, 0, 0, 255]  # red sprite center
        img = Image.fromarray(arr)
        result = remove_background(img, color_tolerance=30)
        res_arr = np.array(result)
        # corners should now be transparent
        assert res_arr[0, 0, 3] == 0
        # center should remain opaque
        assert res_arr[8, 8, 3] == 255


class TestTrimTransparent:
    def test_trims_padding(self):
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        arr[4:8, 4:8] = [255, 0, 0, 255]
        img = Image.fromarray(arr)
        trimmed, bbox = trim_transparent(img)
        assert trimmed.size == (4, 4)
        assert bbox == (4, 4, 8, 8)

    def test_fully_transparent(self):
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        trimmed, bbox = trim_transparent(img)
        # Should return original if fully transparent
        assert trimmed.size[0] > 0


class TestNormalizeSprite:
    def test_basic_pipeline(self):
        img = _make_rgba(16, 16, (255, 0, 0, 255))
        result = normalize_sprite(img, alpha_policy="binary")
        assert result.mode == "RGBA"
        assert result.size[0] > 0
