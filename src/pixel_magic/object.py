"""Isometric world object generation — canvas building, extraction, and fitting."""

from __future__ import annotations

import math

from PIL import Image

from pixel_magic.animate import (
    _draw_label,
    _grid_layout,
    _pick_image_size,
    _snap_gemini_ratio,
    extract_frames,
)
from pixel_magic.platform import create_platform

# Predefined object set presets
OBJECT_PRESETS: dict[str, list[str]] = {
    "forest": ["oak tree", "pine tree", "bush", "rock", "log", "mushroom"],
    "dungeon": ["chest", "barrel", "crate", "torch", "skull pile", "potion"],
    "village": ["well", "crate", "signpost", "fence", "hay bale", "barrel"],
    "camp": ["campfire", "tent", "bedroll", "cooking pot", "backpack", "log seat"],
    "desert": ["cactus", "dead tree", "sandstone rock", "skull", "pottery", "palm tree"],
    "winter": ["snowy pine", "ice rock", "frozen bush", "snowman", "ice crystal", "snow pile"],
}


def resolve_object_labels(
    name: str | None,
    preset: str | None,
    custom_names: str,
    variants: int,
) -> tuple[str, list[str]]:
    """Resolve CLI args into a set name and list of object labels.

    Returns (set_name, labels).
    """
    if name:
        if variants < 1:
            raise ValueError("--variants must be >= 1")
        labels = [f"{name} {i + 1}" for i in range(variants)]
        return name, labels

    if preset == "custom":
        labels = [t.strip() for t in custom_names.split(",") if t.strip()]
        if not labels:
            raise ValueError("--names is required when using --preset custom")
        return "custom", labels

    labels = OBJECT_PRESETS.get(preset, [])
    if not labels:
        available = ", ".join(sorted(OBJECT_PRESETS.keys()))
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}, custom")
    return preset, labels


def build_object_canvas(
    object_labels: list[str],
    depth: int = 8,
    chromakey_color: str = "pink",
) -> tuple[Image.Image, int, tuple[int, int], str, str]:
    """Build a canvas with labeled platforms for Gemini to place objects on.

    Returns (canvas, cols, slot_size, aspect_ratio, image_size).
    """
    if not object_labels:
        raise ValueError("object_labels must not be empty")

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (255, 0, 255))

    # Create a platform at native pixel-art size
    platform_width = 64
    platform = create_platform(platform_width, depth)
    pw, ph = platform.size

    # Slot needs room for label above + object body above platform
    label_margin = 24
    # Object body gets ~2x platform height above it
    body_room = int(ph * 2.5)
    slot_w = pw + 40  # horizontal padding
    slot_h = label_margin + body_room + ph + 10  # label + body + platform + pad

    n_objects = len(object_labels)
    cols, rows = _object_grid_layout(n_objects, slot_w, slot_h)

    raw_w, raw_h = slot_w * cols, slot_h * rows
    aspect_ratio, canvas_w, canvas_h = _snap_gemini_ratio(raw_w, raw_h)
    image_size = _pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    for idx, label in enumerate(object_labels):
        col = idx % cols
        row = idx // cols
        cell_x = col * cell_w
        cell_y = row * cell_h

        # Scale platform up with NEAREST to fill ~50% of cell width
        scale = max(1, int(cell_w * 0.5 / pw))
        scaled_pw = pw * scale
        scaled_ph = ph * scale
        scaled_platform = platform.resize((scaled_pw, scaled_ph), Image.NEAREST)

        # Place platform near bottom of cell
        px = cell_x + (cell_w - scaled_pw) // 2
        py = cell_y + cell_h - scaled_ph - 10
        canvas.paste(scaled_platform, (px, py), scaled_platform)

        # Draw label centered above platform
        _draw_label(canvas, label, cell_x + cell_w // 2, cell_y + 4, cell_w)

    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size


def _object_grid_layout(n_objects: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Prefer exact small layouts to avoid unlabeled empty cells."""
    if n_objects <= 3:
        return n_objects, 1
    return _grid_layout(n_objects, slot_w, slot_h)


def extract_objects(
    sheet: Image.Image,
    object_labels: list[str],
    cols: int,
    slot_size: tuple[int, int],
) -> dict[str, Image.Image]:
    """Extract individual objects from a generated sheet by grid position.

    Returns a dict mapping object label to its cropped image.
    """
    frames = extract_frames(sheet, len(object_labels), cols=cols, slot_size=slot_size)
    return dict(zip(object_labels, frames))
