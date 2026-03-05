"""Tests for generation.extractor — frame extraction from composite images."""

import numpy as np
from PIL import Image

from pixel_magic.generation.extractor import (
    _detect_separator_lines,
    _extract_by_separators,
    _remove_magenta_bleed,
    extract_frames,
    normalize_frame_sizes,
)
from pixel_magic.models.asset import CompositeLayout

_MAGENTA = (255, 0, 255, 255)


def _make_strip(count: int, frame_w: int = 32, frame_h: int = 32) -> Image.Image:
    """Create a horizontal strip with distinct colored frames."""
    rng = np.random.RandomState(42)
    w = count * frame_w
    arr = np.zeros((frame_h, w, 4), dtype=np.uint8)
    for i in range(count):
        color = rng.randint(50, 255, size=3)
        arr[:, i * frame_w : (i + 1) * frame_w, :3] = color
        arr[:, i * frame_w : (i + 1) * frame_w, 3] = 255
    return Image.fromarray(arr)


def _make_separated_strip(
    count: int, frame_w: int = 32, frame_h: int = 32, sep_w: int = 1
) -> Image.Image:
    """Create a horizontal strip with magenta separator lines between frames."""
    rng = np.random.RandomState(42)
    total_w = count * frame_w + (count - 1) * sep_w
    arr = np.zeros((frame_h, total_w, 4), dtype=np.uint8)

    x = 0
    for i in range(count):
        color = rng.randint(50, 200, size=3)
        arr[:, x : x + frame_w, :3] = color
        arr[:, x : x + frame_w, 3] = 255
        x += frame_w
        if i < count - 1:
            arr[:, x : x + sep_w, :3] = [255, 0, 255]
            arr[:, x : x + sep_w, 3] = 255
            x += sep_w

    return Image.fromarray(arr)


class TestExtractFrames:
    def test_horizontal_strip(self):
        strip = _make_strip(4, 32, 32)
        frames = extract_frames(strip, CompositeLayout.HORIZONTAL_STRIP, expected_count=4)
        assert len(frames) == 4
        for f in frames:
            assert f.size == (32, 32)

    def test_vertical_strip(self):
        # Make a vertical strip (tall image)
        rng = np.random.RandomState(42)
        arr = np.zeros((128, 32, 4), dtype=np.uint8)
        for i in range(4):
            color = rng.randint(50, 255, size=3)
            arr[i * 32 : (i + 1) * 32, :, :3] = color
            arr[i * 32 : (i + 1) * 32, :, 3] = 255
        img = Image.fromarray(arr)
        frames = extract_frames(img, CompositeLayout.VERTICAL_STRIP, expected_count=4)
        assert len(frames) == 4

    def test_grid_layout(self):
        # 2x3 grid = 6 frames
        arr = np.zeros((64, 96, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        img = Image.fromarray(arr)
        frames = extract_frames(img, CompositeLayout.GRID, expected_count=6, grid_cols=3)
        assert len(frames) == 6

    def test_frames_have_content(self):
        strip = _make_strip(3, 32, 32)
        frames = extract_frames(strip, CompositeLayout.HORIZONTAL_STRIP, expected_count=3)
        for f in frames:
            arr = np.array(f)
            assert arr[:, :, 3].max() > 0  # not fully transparent


class TestNormalizeFrameSizes:
    def test_pads_to_largest(self):
        frames = [
            Image.new("RGBA", (30, 32), (255, 0, 0, 255)),
            Image.new("RGBA", (32, 32), (0, 255, 0, 255)),
            Image.new("RGBA", (28, 30), (0, 0, 255, 255)),
        ]
        normalized = normalize_frame_sizes(frames)
        sizes = [f.size for f in normalized]
        assert all(s == sizes[0] for s in sizes)


class TestDetectSeparatorLines:
    def test_finds_magenta_columns(self):
        img = _make_separated_strip(4, frame_w=32, frame_h=32, sep_w=1)
        arr = np.array(img)
        cols = _detect_separator_lines(arr)
        assert len(cols) == 3  # 3 separator columns for 4 frames

    def test_multi_pixel_separators(self):
        img = _make_separated_strip(3, frame_w=32, frame_h=32, sep_w=3)
        arr = np.array(img)
        cols = _detect_separator_lines(arr)
        assert len(cols) == 6  # 2 separators × 3px each

    def test_no_separators(self):
        img = _make_strip(4, 32, 32)
        arr = np.array(img)
        cols = _detect_separator_lines(arr)
        assert len(cols) == 0


class TestExtractBySeparators:
    def test_extracts_correct_count(self):
        img = _make_separated_strip(4, frame_w=32, frame_h=32, sep_w=1)
        frames = _extract_by_separators(img, expected_count=4)
        assert frames is not None
        assert len(frames) == 4

    def test_frame_sizes_reasonable(self):
        img = _make_separated_strip(3, frame_w=48, frame_h=48, sep_w=2)
        frames = _extract_by_separators(img, expected_count=3)
        assert frames is not None
        for f in frames:
            assert f.width == 48
            assert f.height == 48

    def test_returns_none_for_wrong_count(self):
        img = _make_separated_strip(4, frame_w=32, frame_h=32, sep_w=1)
        result = _extract_by_separators(img, expected_count=6)
        assert result is None

    def test_returns_none_without_separators(self):
        img = _make_strip(4, 32, 32)
        result = _extract_by_separators(img, expected_count=4)
        assert result is None

    def test_single_frame_returns_none(self):
        img = _make_strip(1, 32, 32)
        result = _extract_by_separators(img, expected_count=1)
        assert result is None

    def test_smart_strip_prefers_separators(self):
        """When magenta separators are present, smart_strip should use them."""
        img = _make_separated_strip(4, frame_w=32, frame_h=32, sep_w=1)
        frames = extract_frames(img, CompositeLayout.HORIZONTAL_STRIP, expected_count=4)
        assert len(frames) == 4


class TestRemoveMagentaBleed:
    def test_clears_edge_magenta(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :, :3] = [100, 100, 100]
        arr[:, :, 3] = 255
        # Add magenta on left edge
        arr[:, 0, :3] = [255, 0, 255]
        img = Image.fromarray(arr, "RGBA")
        cleaned = _remove_magenta_bleed(img, margin=2)
        cleaned_arr = np.array(cleaned)
        assert cleaned_arr[:, 0, 3].max() == 0  # magenta edge made transparent

    def test_preserves_interior(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :, :3] = [100, 200, 100]
        arr[:, :, 3] = 255
        img = Image.fromarray(arr, "RGBA")
        cleaned = _remove_magenta_bleed(img, margin=2)
        cleaned_arr = np.array(cleaned)
        # Interior pixels should be untouched
        assert cleaned_arr[:, 16, 3].min() == 255
