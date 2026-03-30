"""Shared canvas utilities for grid-based sprite sheet generation."""

from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def slugify(text: str) -> str:
    """Sanitize text into a safe filesystem slug (lowercase, alphanum + hyphens)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unnamed"


# Gemini-supported aspect ratios — landscape/square only (w, h)
# Portrait ratios excluded: animation grids read left-to-right
GEMINI_RATIOS: list[tuple[int, int]] = [
    (1, 1), (5, 4), (4, 3), (3, 2), (16, 9),
]

FONT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / "PixelifySans-Regular.ttf"


def draw_label(
    canvas: Image.Image,
    text: str,
    center_x: int,
    y: int,
    cell_w: int,
) -> None:
    """Draw a direction label centered at (center_x, y) using Pixelify Sans.

    White text with black outline for readability on chromakey background.
    Font size scales with cell width. Alpha is thresholded to avoid
    anti-aliased blending with the chromakey background.
    """
    font_size = max(18, cell_w // 18)
    font = ImageFont.truetype(str(FONT_PATH), size=font_size)
    stroke = max(2, font_size // 12)

    # Render text onto a temp image, then threshold alpha to kill anti-aliasing
    bbox = ImageDraw.Draw(canvas).textbbox((0, 0), text, font=font, stroke_width=stroke)
    # bbox origin can be negative (ascenders) — offset drawing to keep everything visible
    ox, oy = -bbox[0] + stroke, -bbox[1] + stroke
    tw, th = bbox[2] + ox + stroke, bbox[3] + oy + stroke
    tmp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text(
        (ox, oy), text, font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255),
    )
    # Snap alpha to 0 or 255 — no blending with chromakey background
    r, g, b, a = tmp.split()
    a = a.point(lambda v: 255 if v > 128 else 0)
    tmp = Image.merge("RGBA", (r, g, b, a))

    x = center_x - (tw // 2)
    canvas.paste(tmp, (x, y), tmp)


def grid_layout(n_frames: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Find (cols, rows) grid closest to a supported Gemini aspect ratio.

    Scores each layout against all supported Gemini ratios and picks the
    one with the best match. Strongly penalizes wasted cells to avoid
    Gemini filling empty cells with extra frames.
    """
    best = (n_frames, 1)
    best_score = float("inf")

    for cols in range(1, n_frames + 1):
        rows = math.ceil(n_frames / cols)
        ratio = (cols * slot_w) / (rows * slot_h)
        min_diff = min(abs(ratio - w / h) for w, h in GEMINI_RATIOS)
        wasted = cols * rows - n_frames
        score = min_diff + wasted * 0.5
        if score < best_score:
            best_score = score
            best = (cols, rows)

    return best


def snap_gemini_ratio(canvas_w: int, canvas_h: int) -> tuple[str, int, int]:
    """Find closest Gemini-supported aspect ratio and compute padded dimensions.

    Returns (ratio_str, padded_w, padded_h) where padded dims >= original
    and exactly match the chosen ratio.
    """
    ratio = canvas_w / canvas_h
    best = (1, 1)
    best_diff = float("inf")
    for pair in GEMINI_RATIOS:
        diff = abs(ratio - pair[0] / pair[1])
        if diff < best_diff:
            best_diff = diff
            best = pair

    target = best[0] / best[1]
    # Expand the smaller dimension to match the target ratio
    if canvas_w / canvas_h < target:
        new_w = math.ceil(canvas_h * target)
        new_h = canvas_h
    else:
        new_w = canvas_w
        new_h = math.ceil(canvas_w / target)

    return f"{best[0]}:{best[1]}", new_w, new_h


def pick_image_size(longest_edge: int) -> str:
    """Pick smallest Gemini output tier that covers the canvas."""
    if longest_edge <= 512:
        return "512"
    if longest_edge <= 1024:
        return "1K"
    if longest_edge <= 2048:
        return "2K"
    return "4K"


def build_canvas(
    reference_frame: Image.Image,
    total_frames: int,
    chromakey_color: str = "green",
    slot_bg: Image.Image | None = None,
    loop: bool = False,
) -> tuple[Image.Image, int, tuple[int, int], str, str]:
    """Build a sprite sheet canvas with frames arranged in a grid.

    The canvas is padded to match a Gemini-supported aspect ratio.
    Each slot is centered within its cell (evenly divided quadrant).
    Empty slots get a pixel-art frame number in the top-left corner of the cell.

    If loop=True, the reference is placed in both slot 1 and the last slot.
    If slot_bg is provided, it's placed in every slot (behind reference).

    Returns (canvas, cols, slot_size, aspect_ratio, image_size).
    """
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    slot_w, slot_h = reference_frame.size
    cols, rows = grid_layout(total_frames, slot_w, slot_h)

    # Snap to Gemini ratio for final canvas size
    raw_w, raw_h = slot_w * cols, slot_h * rows
    aspect_ratio, canvas_w, canvas_h = snap_gemini_ratio(raw_w, raw_h)
    image_size = pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    # Evenly divide canvas into cells — slots centered within each cell
    cell_w = canvas_w // cols
    cell_h = canvas_h // rows
    ox = (cell_w - slot_w) // 2  # horizontal offset to center slot
    oy = (cell_h - slot_h) // 2  # vertical offset to center slot

    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        cell_x = col * cell_w
        cell_y = row * cell_h
        x = cell_x + ox
        y = cell_y + oy

        if slot_bg is not None:
            canvas.paste(slot_bg, (x, y), slot_bg if slot_bg.mode == "RGBA" else None)

        # Frame number centered at top of cell
        draw_label(canvas, str(idx + 1), cell_x + cell_w // 2, cell_y + 4, cell_w)

    # Place reference in slot 1 (covers frame number underneath)
    canvas.paste(
        reference_frame, (ox, oy),
        reference_frame if reference_frame.mode == "RGBA" else None,
    )

    # Loop: also place reference in last slot
    if loop:
        last_idx = total_frames - 1
        lx = (last_idx % cols) * cell_w + ox
        ly = (last_idx // cols) * cell_h + oy
        canvas.paste(
            reference_frame, (lx, ly),
            reference_frame if reference_frame.mode == "RGBA" else None,
        )

    return canvas, cols, (slot_w, slot_h), aspect_ratio, image_size


def build_empty_canvas(
    total_frames: int,
    slot_w: int = 256,
    slot_h: int = 256,
    chromakey_color: str = "pink",
) -> tuple[Image.Image, int, tuple[int, int], str, str]:
    """Build a grid canvas with numbered empty slots (no reference frame).

    All slots are chromakey-filled with a frame number label.
    Used for single-pass generation where the model fills every slot.

    Returns (canvas, cols, slot_size, aspect_ratio, image_size).
    """
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (255, 0, 255))

    cols, rows = grid_layout(total_frames, slot_w, slot_h)

    raw_w, raw_h = slot_w * cols, slot_h * rows
    aspect_ratio, canvas_w, canvas_h = snap_gemini_ratio(raw_w, raw_h)
    image_size = pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        cell_x = col * cell_w
        cell_y = row * cell_h
        draw_label(canvas, str(idx + 1), cell_x + cell_w // 2, cell_y + 4, cell_w)

    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size


def extract_frames(
    sheet: Image.Image,
    total_frames: int,
    cols: int | None = None,
    slot_size: tuple[int, int] | None = None,
) -> list[Image.Image]:
    """Extract frames from a grid-layout sprite sheet.

    If slot_size is provided, extracts centered slots from evenly-divided cells.
    Otherwise falls back to dividing the sheet into equal cells.
    """
    if cols is None:
        cols = total_frames
    rows = math.ceil(total_frames / cols)
    cell_w = sheet.width // cols
    cell_h = sheet.height // rows

    if slot_size:
        sw, sh = slot_size
        ox = (cell_w - sw) // 2
        oy = (cell_h - sh) // 2
    else:
        sw, sh = cell_w, cell_h
        ox, oy = 0, 0

    frames = []
    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        x = col * cell_w + ox
        y = row * cell_h + oy
        frame = sheet.crop((x, y, x + sw, y + sh))
        frames.append(frame)
    return frames
