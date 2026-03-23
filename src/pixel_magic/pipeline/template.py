"""Grid template generation for guiding AI layout."""

from __future__ import annotations

from PIL import Image, ImageDraw


def _draw_tileset_guides(
    draw: ImageDraw.ImageDraw,
    count: int,
    cell_w: int,
    cell_h: int,
    sep_w: int,
    guide_color: tuple[int, int, int, int],
) -> None:
    """Draw a diamond guide in each tileset cell."""
    inset_x = 1
    inset_y = 1 if cell_h <= 16 else 2
    mid_y = cell_h // 2

    for index in range(count):
        left = index * (cell_w + sep_w)
        right = left + cell_w - 1
        center_x = left + cell_w // 2
        points = [
            (center_x, inset_y),
            (right - inset_x, mid_y),
            (center_x, cell_h - 1 - inset_y),
            (left + inset_x, mid_y),
            (center_x, inset_y),
        ]
        draw.line(points, fill=guide_color, width=1)


def _draw_ui_guides(
    draw: ImageDraw.ImageDraw,
    count: int,
    cell_w: int,
    cell_h: int,
    sep_w: int,
    guide_color: tuple[int, int, int, int],
) -> None:
    """Draw an inset panel guide in each UI cell."""
    pad_x = max(6, cell_w // 10)
    pad_y = max(6, cell_h // 10)

    for index in range(count):
        left = index * (cell_w + sep_w) + pad_x
        right = index * (cell_w + sep_w) + cell_w - pad_x - 1
        top = pad_y
        bottom = cell_h - pad_y - 1
        if right > left and bottom > top:
            draw.rectangle([(left, top), (right, bottom)], outline=guide_color, width=1)


def _draw_effect_guides(
    draw: ImageDraw.ImageDraw,
    count: int,
    cell_w: int,
    cell_h: int,
    sep_w: int,
    guide_color: tuple[int, int, int, int],
) -> None:
    """Draw a centered isometric footprint guide in each effect cell."""
    radius_x = max(8, cell_w // 4)
    radius_y = max(6, cell_h // 8)

    for index in range(count):
        left = index * (cell_w + sep_w)
        center_x = left + cell_w // 2
        center_y = cell_h // 2
        points = [
            (center_x, center_y - radius_y),
            (center_x + radius_x, center_y),
            (center_x, center_y + radius_y),
            (center_x - radius_x, center_y),
            (center_x, center_y - radius_y),
        ]
        draw.line(points, fill=guide_color, width=1)
        draw.point((center_x, center_y), fill=guide_color)


def generate_grid_template(
    count: int,
    cell_w: int,
    cell_h: int,
    separator_color: tuple[int, int, int, int] = (255, 0, 255, 255),
    asset_type: str | None = None,
    guide_color: tuple[int, int, int, int] = (0, 255, 255, 160),
) -> Image.Image:
    """Create a transparent layout reference image for multi-cell generations."""
    if count < 1:
        count = 1
    sep_w = 1
    total_w = count * cell_w + (count - 1) * sep_w
    img = Image.new("RGBA", (total_w, cell_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if count > 1:
        for i in range(1, count):
            x = i * cell_w + (i - 1) * sep_w
            draw.line([(x, 0), (x, cell_h - 1)], fill=separator_color, width=1)

    if asset_type == "tileset":
        _draw_tileset_guides(draw, count, cell_w, cell_h, sep_w, guide_color)
    elif asset_type == "effect":
        _draw_effect_guides(draw, count, cell_w, cell_h, sep_w, guide_color)
    elif asset_type == "ui":
        _draw_ui_guides(draw, count, cell_w, cell_h, sep_w, guide_color)

    return img
