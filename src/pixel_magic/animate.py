"""Canvas-based sprite sheet animation generation."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pixel_magic.prompts import build_canvas_prompt
from pixel_magic.providers.gemini import GeminiProvider

# Gemini-supported aspect ratios — landscape/square only (w, h)
# Portrait ratios excluded: animation grids read left-to-right
_GEMINI_RATIOS: list[tuple[int, int]] = [
    (1, 1), (5, 4), (4, 3), (3, 2), (16, 9),
]

_FONT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / "PixelifySans-Regular.ttf"


def _draw_label(
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
    font = ImageFont.truetype(str(_FONT_PATH), size=font_size)
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

        # Frame number centered at top of cell
        _draw_label(canvas, str(idx + 1), cell_x + cell_w // 2, cell_y + 4, cell_w)

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


def _pick_generation_config(
    n_views: int, tiles: int,
) -> tuple[str, str, int, int]:
    """Pick fixed Gemini output config based on view count and tile footprint.

    Returns (image_size, aspect_ratio, canvas_w, canvas_h).
    """
    if n_views <= 3:
        # 2-view (4-dir): 1K 4:3, except 9-tile gets 2K 16:9
        if tiles >= 9:
            return "2K", "16:9", 2048, 1152
        return "1K", "4:3", 1024, 768
    # 5-view (8-dir): 3x2 grid needs wider canvas
    return "2K", "16:9", 2048, 1152


def build_generation_canvas(
    view_labels: list[str],
    tile_depth: int = 16,
    tiles: int = 1,
    chromakey_color: str = "green",
    platform_fill: float = 0.55,
    char_ratio: float = 1.2,
    target_res: int = 64,
) -> tuple[Image.Image, int, tuple[int, int], str, str, bool]:
    """Build a canvas with labeled platforms for character generation.

    Top-down approach: start from a fixed Gemini output size, divide into
    cells, then fit platforms and character space inside each cell.

    Platforms are drawn at a small native resolution (based on target_res)
    and scaled up with NEAREST to look chunky and pixel-art-like.

    platform_fill controls how much of the cell width the platform occupies
    (0.55 = platform is 55% of cell width). char_ratio estimates the
    character's height as a multiple of the platform width — used to
    vertically center the character+platform unit in each cell so the
    character's head doesn't clip the top.

    Returns (canvas, cols, slot_size, aspect_ratio, image_size, center_bottom).
    """
    from pixel_magic.platform import create_platform_grid

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    n_views = len(view_labels)
    cols, rows, center_bottom = _generation_grid_layout(n_views)

    # Fixed canvas size from Gemini config
    image_size, aspect_ratio, canvas_w, canvas_h = _pick_generation_config(n_views, tiles)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    # Draw platform at native pixel-art resolution, then scale up with NEAREST
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
    native_tile_w = max(8, target_res * 3 // 8)
    if native_tile_w % 2 != 0:
        native_tile_w += 1
    native_depth = max(2, tile_depth * native_tile_w // 64)
    native_platform = create_platform_grid(native_tile_w, native_depth, grid_size=grid_size)

    # Scale up to fill target fraction of cell width
    target_plat_w = int(cell_w * platform_fill)
    scale = max(1, round(target_plat_w / native_platform.width))
    platform = native_platform.resize(
        (native_platform.width * scale, native_platform.height * scale),
        Image.NEAREST,
    )

    # --- Vertical placement: center character+platform unit in cell ---
    # Estimate character height from platform width
    char_height = int(platform.width * char_ratio)

    # Character feet land at center of the diamond top face
    # After scaling, diamond_h is half the platform width (isometric geometry)
    diamond_h = platform.width // 2
    feet_offset = diamond_h // 2  # y from top of platform image

    # Total composite: character body above feet + platform below feet
    platform_below_feet = platform.height - feet_offset
    composite_h = char_height + platform_below_feet

    # Clamp if composite exceeds cell (leave small margin)
    margin_min = 8
    if composite_h > cell_h - margin_min * 2:
        char_height = cell_h - platform_below_feet - margin_min * 2
        composite_h = cell_h - margin_min * 2

    # Center the composite vertically in the cell
    top_margin = (cell_h - composite_h) // 2
    plat_y_in_cell = top_margin + char_height - feet_offset

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

        # Center platform horizontally in cell
        plat_x = cell_x + (cell_w - platform.width) // 2
        plat_y = cell_y + plat_y_in_cell
        canvas.paste(platform, (plat_x, plat_y), platform)

        # # Draw direction label centered at top of cell
        # label_text = view_labels[idx].replace("_", "-")
        # label_margin = max(4, cell_h // 50)
        # _draw_label(canvas, label_text, cell_x + cell_w // 2, cell_y + label_margin, cell_w)

    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size, center_bottom


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
