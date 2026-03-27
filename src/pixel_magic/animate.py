"""Canvas-based sprite sheet animation generation."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from pixel_magic.prompts import build_canvas_prompt
from pixel_magic.providers.gemini import GeminiProvider

# Gemini-supported aspect ratios — landscape/square only (w, h)
# Portrait ratios excluded: animation grids read left-to-right
_GEMINI_RATIOS: list[tuple[int, int]] = [
    (1, 1), (5, 4), (4, 3), (3, 2), (16, 9),
]

# 3x5 pixel bitmaps for digits 0-9 (each row is a 3-bit mask, MSB = left)
_DIGIT_BITMAPS: dict[int, list[int]] = {
    0: [0b111, 0b101, 0b101, 0b101, 0b111],
    1: [0b010, 0b110, 0b010, 0b010, 0b111],
    2: [0b111, 0b001, 0b111, 0b100, 0b111],
    3: [0b111, 0b001, 0b111, 0b001, 0b111],
    4: [0b101, 0b101, 0b111, 0b001, 0b001],
    5: [0b111, 0b100, 0b111, 0b001, 0b111],
    6: [0b111, 0b100, 0b111, 0b101, 0b111],
    7: [0b111, 0b001, 0b001, 0b010, 0b010],
    8: [0b111, 0b101, 0b111, 0b101, 0b111],
    9: [0b111, 0b101, 0b111, 0b001, 0b111],
}

# 3x5 pixel bitmaps for uppercase letters (same format as digits)
_LETTER_BITMAPS: dict[str, list[int]] = {
    "A": [0b010, 0b101, 0b111, 0b101, 0b101],
    "B": [0b110, 0b101, 0b110, 0b101, 0b110],
    "C": [0b011, 0b100, 0b100, 0b100, 0b011],
    "E": [0b111, 0b100, 0b110, 0b100, 0b111],
    "F": [0b111, 0b100, 0b110, 0b100, 0b100],
    "G": [0b011, 0b100, 0b101, 0b101, 0b011],
    "H": [0b101, 0b101, 0b111, 0b101, 0b101],
    "I": [0b111, 0b010, 0b010, 0b010, 0b111],
    "K": [0b101, 0b110, 0b100, 0b110, 0b101],
    "L": [0b100, 0b100, 0b100, 0b100, 0b111],
    "N": [0b101, 0b111, 0b111, 0b101, 0b101],
    "O": [0b010, 0b101, 0b101, 0b101, 0b010],
    "R": [0b110, 0b101, 0b110, 0b101, 0b101],
    "S": [0b011, 0b100, 0b010, 0b001, 0b110],
    "T": [0b111, 0b010, 0b010, 0b010, 0b010],
    "W": [0b101, 0b101, 0b101, 0b111, 0b101],
    " ": [0b000, 0b000, 0b000, 0b000, 0b000],
    "-": [0b000, 0b000, 0b111, 0b000, 0b000],
}


def _draw_pixel_text(
    canvas: Image.Image,
    text: str,
    slot_x: int,
    slot_y: int,
    slot_width: int,
) -> None:
    """Draw pixel-art text in the top-left corner of a slot."""
    scale = max(2, slot_width // 60)
    margin = scale * 2
    gap = scale  # gap between characters

    x0 = slot_x + margin
    y0 = slot_y + margin

    for char in text.upper():
        if char.isdigit():
            bitmap = _DIGIT_BITMAPS.get(int(char))
        else:
            bitmap = _LETTER_BITMAPS.get(char)
        if bitmap is None:
            x0 += 2 * scale  # skip unknown chars
            continue

        for row_idx, row_bits in enumerate(bitmap):
            for col_idx in range(3):
                if row_bits & (1 << (2 - col_idx)):
                    px = x0 + col_idx * scale
                    py = y0 + row_idx * scale
                    # Black outline (1px border around each block)
                    for dx in range(-1, scale + 1):
                        for dy in range(-1, scale + 1):
                            cx, cy = px + dx, py + dy
                            if 0 <= cx < canvas.width and 0 <= cy < canvas.height:
                                canvas.putpixel((cx, cy), (0, 0, 0, 255))
                    # White fill
                    for dx in range(scale):
                        for dy in range(scale):
                            canvas.putpixel((px + dx, py + dy), (255, 255, 255, 255))
        x0 += 3 * scale + gap


def _draw_frame_number(
    canvas: Image.Image,
    number: int,
    slot_x: int,
    slot_y: int,
    slot_width: int,
) -> None:
    """Draw a pixel-art frame number in the top-left corner of a slot."""
    _draw_pixel_text(canvas, str(number), slot_x, slot_y, slot_width)


def _grid_layout(n_frames: int, slot_w: int, slot_h: int) -> tuple[int, int]:
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
        min_diff = min(abs(ratio - w / h) for w, h in _GEMINI_RATIOS)
        wasted = cols * rows - n_frames
        score = min_diff + wasted * 0.5
        if score < best_score:
            best_score = score
            best = (cols, rows)

    return best


def _snap_gemini_ratio(canvas_w: int, canvas_h: int) -> tuple[str, int, int]:
    """Find closest Gemini-supported aspect ratio and compute padded dimensions.

    Returns (ratio_str, padded_w, padded_h) where padded dims >= original
    and exactly match the chosen ratio.
    """
    ratio = canvas_w / canvas_h
    best = (1, 1)
    best_diff = float("inf")
    for pair in _GEMINI_RATIOS:
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


def _pick_image_size(longest_edge: int) -> str:
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
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    slot_w, slot_h = reference_frame.size
    cols, rows = _grid_layout(total_frames, slot_w, slot_h)

    # Snap to Gemini ratio for final canvas size
    raw_w, raw_h = slot_w * cols, slot_h * rows
    aspect_ratio, canvas_w, canvas_h = _snap_gemini_ratio(raw_w, raw_h)
    image_size = _pick_image_size(max(canvas_w, canvas_h))

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

        # Number at top-left of cell (not slot)
        _draw_frame_number(canvas, idx + 1, cell_x, cell_y, cell_w)

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


def _generation_grid_layout(n_views: int) -> tuple[int, int, bool]:
    """Grid layout for character generation views.

    Returns (cols, rows, center_bottom).
    center_bottom=True means the last row has fewer items and should be centered.
    """
    if n_views <= 3:
        return n_views, 1, False
    if n_views == 4:
        return 2, 2, False
    if n_views == 5:
        return 3, 2, True
    # 6+
    cols = 3
    rows = math.ceil(n_views / cols)
    return cols, rows, n_views % cols != 0


def build_generation_canvas(
    view_labels: list[str],
    tile_width: int = 256,
    tile_depth: int = 16,
    tiles: int = 1,
    chromakey_color: str = "green",
    char_ratio: float = 1.7,
) -> tuple[Image.Image, int, tuple[int, int], str, str, bool]:
    """Build a canvas with labeled platforms for character generation.

    Each platform gets a direction label in the top-left corner.
    For 5 views, the bottom row of 2 is centered.

    char_ratio controls platform placement — the space above the platform
    is sized for a character of height tile_width * char_ratio. This
    positions the platform where a character's feet would be, but the
    model may generate characters of different sizes. Default 1.7 is
    mid-range for isometric RPG sprites (1.5 chibi, 2.0 tactical).

    Returns (canvas, cols, slot_size, aspect_ratio, image_size, center_bottom).
    """
    from pixel_magic.platform import create_platform_grid

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    n_views = len(view_labels)
    cols, rows, center_bottom = _generation_grid_layout(n_views)

    # Scale individual tile size down for larger grids so platforms don't dominate
    # Slot size stays based on base tile_width — only the tiles inside shrink
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
    _tile_scale = {1: 1.0, 2: 0.7, 3: 0.45}
    scaled_tile = int(tile_width * _tile_scale.get(grid_size, 1.0))
    platform = create_platform_grid(scaled_tile, tile_depth, grid_size=grid_size)

    # Slot dimensions based on BASE tile_width (consistent canvas size)
    char_height = int(tile_width * char_ratio)
    slot_w = max(tile_width * 2, platform.width + 20)
    slot_h_base = char_height

    # Character feet land at the CENTER of the platform's diamond top face.
    single_diamond_h = scaled_tile // 2
    feet_offset = grid_size * single_diamond_h // 2

    # Platform placed so feet_offset into it aligns with bottom of char_height
    plat_x = (slot_w - platform.width) // 2
    plat_y = char_height - feet_offset
    slot_h = plat_y + platform.height

    # Snap to Gemini ratio
    raw_w = cols * slot_w
    raw_h = rows * slot_h
    aspect_ratio, canvas_w, canvas_h = _snap_gemini_ratio(raw_w, raw_h)
    image_size = _pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    for idx in range(n_views):
        if not center_bottom or idx < cols:
            row = idx // cols
            col = idx % cols
            cell_x = col * cell_w
            cell_y = row * cell_h
        else:
            # Bottom row — centered
            row = 1
            bottom_idx = idx - cols
            bottom_count = n_views - cols
            total_bottom_w = bottom_count * cell_w
            offset = (canvas_w - total_bottom_w) // 2
            cell_x = offset + bottom_idx * cell_w
            cell_y = row * cell_h

        # Center slot within cell
        ox = cell_x + (cell_w - slot_w) // 2
        oy = cell_y + (cell_h - slot_h) // 2

        # Paste platform
        canvas.paste(platform, (ox + plat_x, oy + plat_y), platform)

        # Draw direction label
        label_text = view_labels[idx].upper().replace("_", " ")
        _draw_pixel_text(canvas, label_text, cell_x, cell_y, cell_w)

    return canvas, cols, (slot_w, slot_h), aspect_ratio, image_size, center_bottom


async def generate_animation(
    provider: GeminiProvider,
    reference_frame: Image.Image,
    animation_type: str = "walk",
    total_frames: int = 6,
    loop: bool = True,
    character_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "green",
    save_dir: Path | None = None,
    platform: bool = False,
    tiles: int = 1,
) -> list[Image.Image]:
    """Generate animation by filling a pre-built sprite sheet canvas.

    1. Build a canvas: frame 1 in slot 1, green fill in remaining slots
    2. Send canvas + prompt to Gemini asking it to fill in the green slots
    3. Extract individual frames from the result

    If platform=True, each slot gets an isometric platform tile to establish
    the ground plane and perspective. Platforms are cropped off after generation.

    Returns an ordered list of total_frames PIL Images.
    """
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    # Platform mode: composite character onto platform tile
    crop_h = None
    slot_bg = None
    if platform:
        from pixel_magic.platform import composite_on_platform

        ref_composite, slot_bg, crop_h = composite_on_platform(reference_frame, tiles=tiles)
    else:
        ref_composite = reference_frame

    # Build canvas (handles grid layout, padding, centering)
    canvas, grid_cols, slot_size, aspect_ratio, image_size = build_canvas(
        ref_composite, total_frames, chromakey_color, slot_bg=slot_bg, loop=loop,
    )
    grid_rows = math.ceil(total_frames / grid_cols)

    if save_dir:
        canvas.save(save_dir / "canvas_input.png")

    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid, {total_frames} frames)")
    print(f"  Gemini: {aspect_ratio} ratio, {image_size} output, slot={slot_size[0]}x{slot_size[1]}")

    # Generate
    prompt = build_canvas_prompt(
        animation_type=animation_type,
        total_frames=total_frames,
        character_description=character_description,
        style=style,
        chromakey_color=chromakey_color,
        platform=platform,
        loop=loop,
        tiles=tiles,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )

    print("  Generating sprite sheet...")
    result = await provider.generate_with_images(
        prompt=prompt,
        images=[canvas],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )

    # Save raw result
    if save_dir:
        result.image.save(save_dir / "sheet_raw.png")

    # Second pass: ask Gemini to remove platforms
    if platform:
        from pixel_magic.prompts import build_platform_removal_prompt

        removal_prompt = build_platform_removal_prompt(
            total_frames, chromakey_color,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
        )
        print("  Removing platforms (2nd pass)...")
        cleaned = await provider.generate_with_images(
            prompt=removal_prompt,
            images=[result.image],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        if save_dir:
            cleaned.image.save(save_dir / "sheet_cleaned.png")
        result = cleaned

    # Resize output to match our canvas dims if Gemini changed them
    sheet = result.image
    if sheet.size != canvas.size:
        sheet = sheet.resize(canvas.size, Image.NEAREST)

    # Extract frames (centered within cells)
    frames = extract_frames(sheet, total_frames, cols=grid_cols, slot_size=slot_size)

    if save_dir:
        for i, frame in enumerate(frames, 1):
            frame.save(save_dir / f"frame_{i:02d}.png")

    return frames


def assemble_sprite_sheet(frames: list[Image.Image]) -> Image.Image:
    """Assemble frames into a horizontal sprite sheet."""
    max_h = max(f.height for f in frames)
    total_w = sum(f.width for f in frames)
    sheet = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        sheet.paste(frame, (x, 0), frame if frame.mode == "RGBA" else None)
        x += frame.width
    return sheet
