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
    *,
    corner: bool = False,
) -> None:
    """Draw a direction label using Pixelify Sans.

    White text with black outline for readability on chromakey background.
    Font size scales with cell width. Alpha is thresholded to avoid
    anti-aliased blending with the chromakey background.

    If corner=True, the label is positioned at the top-left corner (ignoring
    center_x) and drawn larger for better model visibility.
    """
    if corner:
        font_size = max(32, cell_w // 6)
    else:
        font_size = max(24, cell_w // 10)
    font = ImageFont.truetype(str(FONT_PATH), size=font_size)
    stroke = max(2, font_size // 10)

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

    if corner:
        x = center_x - (cell_w // 2) + 4  # left edge of cell + small margin
    else:
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
    frame_offset: int = 0,
    loop_frame: Image.Image | None = None,
) -> tuple[Image.Image, int, tuple[int, int], str, str]:
    """Build a sprite sheet canvas with frames arranged in a grid.

    Layout uses explicit margins and gaps: an outer margin around the entire
    canvas and gaps between cells. Each cell has a thick white border with
    the frame number in its top-left corner. Slots (where sprites go) are
    inset inside the borders.

    If loop=True, the reference is placed in both slot 1 and the last slot.
    If slot_bg is provided, it's placed in every slot (behind reference).

    Returns (canvas, cols, slot_size, aspect_ratio, image_size).
    """
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    slot_w, slot_h = reference_frame.size
    cols, rows = grid_layout(total_frames, slot_w, slot_h)

    # Spacing: border thickness, gap between cells, outer margin
    # Border must be very thick so Gemini clearly sees cell boundaries
    border = 5
    gap = 5
    margin = gap  # outer margin same as gap

    # Cell = border + slot + border
    cell_w = slot_w + 2 * border
    cell_h = slot_h + 2 * border

    # Total canvas before aspect-ratio snapping
    raw_w = 2 * margin + cols * cell_w + (cols - 1) * gap
    raw_h = 2 * margin + rows * cell_h + (rows - 1) * gap
    aspect_ratio, canvas_w, canvas_h = snap_gemini_ratio(raw_w, raw_h)
    image_size = pick_image_size(max(canvas_w, canvas_h))

    # Recompute margin to absorb the aspect-ratio padding evenly
    actual_margin_x = (canvas_w - cols * cell_w - (cols - 1) * gap) // 2
    actual_margin_y = (canvas_h - rows * cell_h - (rows - 1) * gap) // 2

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    # How many frames are in the last row?
    last_row_count = total_frames - (rows - 1) * cols
    last_row_offset_x = ((cols - last_row_count) * (cell_w + gap)) // 2 if last_row_count < cols else 0

    def _cell_origin(idx: int) -> tuple[int, int]:
        """Top-left corner of cell border for a given frame index."""
        col = idx % cols
        row = idx // cols
        cx = actual_margin_x + col * (cell_w + gap)
        cy = actual_margin_y + row * (cell_h + gap)
        if row == rows - 1 and last_row_offset_x:
            cx += last_row_offset_x
        return cx, cy

    def _slot_origin(idx: int) -> tuple[int, int]:
        """Top-left corner of the slot (inside border) for a given frame index."""
        cx, cy = _cell_origin(idx)
        return cx + border, cy + border

    draw = ImageDraw.Draw(canvas)
    border_color = (255, 255, 255, 255)

    for idx in range(total_frames):
        cx, cy = _cell_origin(idx)
        sx, sy = _slot_origin(idx)

        # Draw thick white border around the cell
        draw.rectangle(
            [cx, cy, cx + cell_w - 1, cy + cell_h - 1],
            outline=border_color, width=border,
        )

        if slot_bg is not None:
            canvas.paste(slot_bg, (sx, sy), slot_bg if slot_bg.mode == "RGBA" else None)

        # Frame number in the top-left corner of the cell
        draw_label(canvas, str(frame_offset + idx + 1), cx + cell_w // 2, cy + border + 2, cell_w, corner=True)

    # Place reference in slot 1 (covers frame number underneath)
    s0x, s0y = _slot_origin(0)
    canvas.paste(
        reference_frame, (s0x, s0y),
        reference_frame if reference_frame.mode == "RGBA" else None,
    )

    # Loop: place loop target (or reference) in last slot
    if loop:
        last_idx = total_frames - 1
        slx, sly = _slot_origin(last_idx)
        target = loop_frame if loop_frame is not None else reference_frame
        canvas.paste(
            target, (slx, sly),
            target if target.mode == "RGBA" else None,
        )

    return canvas, cols, (slot_w, slot_h), aspect_ratio, image_size


def build_empty_canvas(
    total_frames: int,
    slot_w: int = 256,
    slot_h: int = 256,
    chromakey_color: str = "pink",
    frame_offset: int = 0,
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

    last_row_count = total_frames - (rows - 1) * cols
    last_row_offset = (cols - last_row_count) * cell_w // 2 if last_row_count < cols else 0

    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        cell_x = col * cell_w
        cell_y = row * cell_h
        if row == rows - 1 and last_row_offset:
            cell_x += last_row_offset
        draw_label(canvas, str(frame_offset + idx + 1), cell_x + cell_w // 2, cell_y + 4, cell_w, corner=True)

    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size


def extract_frames(
    sheet: Image.Image,
    total_frames: int,
    cols: int | None = None,
    slot_size: tuple[int, int] | None = None,
) -> list[Image.Image]:
    """Extract frames from a grid-layout sprite sheet.

    Uses the same margin/gap/border layout as build_canvas to locate each
    slot precisely. If slot_size is provided, the layout includes borders
    and gaps; otherwise falls back to simple even division.
    """
    if cols is None:
        cols = total_frames
    rows = math.ceil(total_frames / cols)

    if slot_size:
        sw, sh = slot_size
        # Reconstruct the same spacing as build_canvas
        border = 5
        gap = 5
        cell_w = sw + 2 * border
        cell_h = sh + 2 * border

        # Recompute actual margins from canvas size
        actual_margin_x = (sheet.width - cols * cell_w - (cols - 1) * gap) // 2
        actual_margin_y = (sheet.height - rows * cell_h - (rows - 1) * gap) // 2

        last_row_count = total_frames - (rows - 1) * cols
        last_row_offset_x = ((cols - last_row_count) * (cell_w + gap)) // 2 if last_row_count < cols else 0

        frames = []
        for idx in range(total_frames):
            col = idx % cols
            row = idx // cols
            cx = actual_margin_x + col * (cell_w + gap)
            cy = actual_margin_y + row * (cell_h + gap)
            if row == rows - 1 and last_row_offset_x:
                cx += last_row_offset_x
            x = cx + border
            y = cy + border
            frame = sheet.crop((x, y, x + sw, y + sh))
            frames.append(frame)
        return frames
    else:
        # Simple even division fallback (for canvases without margin/gap layout)
        cell_w = sheet.width // cols
        cell_h = sheet.height // rows
        sw, sh = cell_w, cell_h

        last_row_count = total_frames - (rows - 1) * cols
        last_row_offset = (cols - last_row_count) * cell_w // 2 if last_row_count < cols else 0

        frames = []
        for idx in range(total_frames):
            col = idx % cols
            row = idx // cols
            x = col * cell_w
            y = row * cell_h
            if row == rows - 1 and last_row_offset:
                x += last_row_offset
            frame = sheet.crop((x, y, x + sw, y + sh))
            frames.append(frame)
        return frames
