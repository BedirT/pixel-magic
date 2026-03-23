"""Regression tests for layout guides and deterministic QA guards."""

import numpy as np
from PIL import Image

from pixel_magic.models.metadata import QACheckName
from pixel_magic.pipeline.template import generate_grid_template
from pixel_magic.qa.deterministic import run_deterministic_qa


def _opaque_sprite(size: tuple[int, int] = (16, 16)) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(4, 12):
        for x in range(4, 12):
            image.putpixel((x, y), (255, 0, 0, 255))
    return image


def test_tileset_grid_template_draws_guides():
    image = generate_grid_template(3, 64, 32, asset_type="tileset")
    arr = np.array(image)
    guide_pixels = np.sum((arr[:, :, 0] == 0) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255) & (arr[:, :, 3] > 0))
    assert guide_pixels > 0


def test_ui_grid_template_draws_guides():
    image = generate_grid_template(2, 160, 128, asset_type="ui")
    arr = np.array(image)
    guide_pixels = np.sum((arr[:, :, 0] == 0) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255) & (arr[:, :, 3] > 0))
    assert guide_pixels > 0


def test_effect_grid_template_draws_guides():
    image = generate_grid_template(6, 64, 64, asset_type="effect")
    arr = np.array(image)
    guide_pixels = np.sum((arr[:, :, 0] == 0) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255) & (arr[:, :, 3] > 0))
    assert guide_pixels > 0


def test_run_deterministic_qa_fails_blank_frame():
    report = run_deterministic_qa([
        _opaque_sprite(),
        Image.new("RGBA", (16, 16), (0, 0, 0, 0)),
    ], expected_frame_count=2)

    check = next(check for check in report.checks if check.name == QACheckName.FRAME_NONEMPTY)
    assert not check.passed
    assert "1" in check.details