"""Canvas-based sprite sheet animation generation."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from pixel_magic.canvas import (
    FONT_PATH as _FONT_PATH,
    GEMINI_RATIOS as _GEMINI_RATIOS,
    build_canvas,
    build_empty_canvas,
    draw_label as _draw_label,
    extract_frames,
    grid_layout as _grid_layout,
    pick_image_size as _pick_image_size,
    snap_gemini_ratio as _snap_gemini_ratio,
)
from pixel_magic.prompts import build_canvas_prompt
from pixel_magic.providers.gemini import GeminiProvider


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

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255), "pink": (255, 0, 255)}
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
    subject: str = "character",
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
    if subject == "object":
        from pixel_magic.prompts import build_object_animation_prompt

        prompt = build_object_animation_prompt(
            animation_type=animation_type,
            total_frames=total_frames,
            object_description=character_description,
            style=style,
            chromakey_color=chromakey_color,
            platform=platform,
            loop=loop,
            tiles=tiles,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
        )
    else:
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
