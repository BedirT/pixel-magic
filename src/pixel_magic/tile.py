"""Isometric terrain tile generation — canvas building, extraction, and fitting."""

from __future__ import annotations

import math

from PIL import Image

from pixel_magic.animate import _draw_label, _grid_layout, _pick_image_size, _snap_gemini_ratio, extract_frames
from pixel_magic.platform import create_tile_outline

# Predefined theme → tile type mappings
TILE_THEMES: dict[str, list[str]] = {
    "forest": ["grass", "dirt path", "water", "dense grass", "flowers", "stone"],
    "dungeon": ["stone floor", "cracked stone", "mossy stone", "dark stone", "water puddle", "lava"],
    "desert": ["sand", "dry dirt", "sandstone", "rocky sand", "cactus patch", "oasis water"],
    "winter": ["snow", "ice", "frozen dirt", "pine patch", "frozen water", "slush"],
}


def resolve_tile_labels(
    tile_type: str | None,
    theme: str | None,
    custom_types: str,
    variants: int,
) -> tuple[str, list[str]]:
    """Resolve CLI args into a set name and list of tile labels.

    Returns (set_name, labels).
    """
    if tile_type:
        if variants < 1:
            raise ValueError("--variants must be >= 1")
        labels = [f"{tile_type} {i + 1}" for i in range(variants)]
        return tile_type, labels

    if theme == "custom":
        labels = [t.strip() for t in custom_types.split(",") if t.strip()]
        if not labels:
            raise ValueError("--types is required when using --theme custom")
        return "custom", labels

    labels = TILE_THEMES.get(theme, [])
    if not labels:
        available = ", ".join(sorted(TILE_THEMES.keys()))
        raise ValueError(f"Unknown theme '{theme}'. Available: {available}, custom")
    return theme, labels


def build_tile_canvas(
    tile_labels: list[str],
    tile_width: int = 128,
    depth: int = 4,
    chromakey_color: str = "green",
) -> tuple[Image.Image, int, tuple[int, int], str, str]:
    """Build a canvas with labeled diamond wireframes for Gemini to fill.

    Returns (canvas, cols, slot_size, aspect_ratio, image_size).
    """
    if not tile_labels:
        raise ValueError("tile_labels must not be empty")

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (255, 0, 255))

    outline = create_tile_outline(tile_width, depth)
    ow, oh = outline.size

    # Slot needs room for label above the tile
    label_margin = max(20, tile_width // 4)
    slot_w = ow + 20  # small horizontal padding
    slot_h = oh + label_margin + 10  # label above + padding below

    n_tiles = len(tile_labels)
    cols, rows = _tile_grid_layout(n_tiles, slot_w, slot_h)

    raw_w, raw_h = slot_w * cols, slot_h * rows
    aspect_ratio, canvas_w, canvas_h = _snap_gemini_ratio(raw_w, raw_h)
    image_size = _pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    for idx, label in enumerate(tile_labels):
        col = idx % cols
        row = idx // cols
        cell_x = col * cell_w
        cell_y = row * cell_h

        # Center outline horizontally, place below label
        ox = cell_x + (cell_w - ow) // 2
        oy = cell_y + label_margin

        canvas.paste(outline, (ox, oy), outline)

        # Draw label centered at top of cell
        _draw_label(canvas, label, cell_x + cell_w // 2, cell_y + 4, cell_w)

    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size


def _tile_grid_layout(n_tiles: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Prefer exact small layouts to avoid unlabeled empty cells."""
    if n_tiles <= 3:
        return n_tiles, 1
    return _grid_layout(n_tiles, slot_w, slot_h)


def extract_tiles(
    sheet: Image.Image,
    tile_labels: list[str],
    cols: int,
    slot_size: tuple[int, int],
) -> dict[str, Image.Image]:
    """Extract individual tiles from a generated sheet by grid position.

    Returns a dict mapping tile label to its cropped image.
    """
    frames = extract_frames(sheet, len(tile_labels), cols=cols, slot_size=slot_size)
    return dict(zip(tile_labels, frames))


def fit_tile(
    tile: Image.Image,
    target_width: int,
    depth: int = 0,
) -> Image.Image:
    """Resize and center a tile into a standard bounding box.

    Flat tiles (depth=0): bounding box is target_width × (target_width // 2).
    3D tiles (depth>0): bounding box is target_width × (target_width // 2 + depth).
    """
    diamond_h = target_width // 2
    box_h = diamond_h + depth

    # Scale tile to fit within the bounding box, preserving aspect ratio
    tw, th = tile.size
    if tw == 0 or th == 0:
        return Image.new("RGBA", (target_width, box_h), (0, 0, 0, 0))

    scale = min(target_width / tw, box_h / th)
    new_w = max(1, int(tw * scale))
    new_h = max(1, int(th * scale))
    resized = tile.resize((new_w, new_h), Image.NEAREST)

    # Center on transparent canvas
    result = Image.new("RGBA", (target_width, box_h), (0, 0, 0, 0))
    x = (target_width - new_w) // 2
    y = (box_h - new_h) // 2
    result.paste(resized, (x, y), resized if resized.mode == "RGBA" else None)
    return result
