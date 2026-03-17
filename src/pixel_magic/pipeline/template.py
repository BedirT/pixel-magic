"""Grid template generation for guiding AI layout."""

from __future__ import annotations

from PIL import Image, ImageDraw


def generate_grid_template(
    count: int,
    cell_w: int,
    cell_h: int,
    separator_color: tuple[int, int, int, int] = (255, 0, 255, 255),
) -> Image.Image:
    """Create a transparent image with magenta vertical separators between cells.

    The AI receives this as a reference image so it knows exactly where to
    place each sprite/tile in a horizontal strip.
    """
    if count < 1:
        count = 1
    sep_w = 1
    total_w = count * cell_w + (count - 1) * sep_w
    img = Image.new("RGBA", (total_w, cell_h), (0, 0, 0, 0))

    if count > 1:
        draw = ImageDraw.Draw(img)
        for i in range(1, count):
            x = i * cell_w + (i - 1) * sep_w
            draw.line([(x, 0), (x, cell_h - 1)], fill=separator_color, width=1)

    return img
