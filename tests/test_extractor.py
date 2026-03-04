"""Tests for generation.extractor — frame extraction from composite images."""

import numpy as np
from PIL import Image

from pixel_magic.generation.extractor import extract_frames, normalize_frame_sizes
from pixel_magic.models.asset import CompositeLayout


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
