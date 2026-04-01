"""Canvas-based sprite sheet animation generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
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


BATCH_SIZE = 6
OVERLAP = 1


@dataclass(frozen=True)
class BatchInfo:
    """Describes one batch in a multi-batch animation generation."""

    batch_index: int
    total_batches: int
    frame_start: int       # global frame number (1-indexed)
    frame_end: int         # global frame number (inclusive)
    batch_frames: int      # number of slots in this batch's canvas
    is_first: bool
    is_last: bool


def _compute_batches(
    total_frames: int,
    batch_size: int = BATCH_SIZE,
    loop: bool = False,
) -> list[BatchInfo]:
    """Compute batch descriptors for multi-batch animation.

    Batch 0 produces batch_size frames. Each subsequent batch overlaps by 1
    frame (the last frame of the previous batch becomes the first/reference
    frame of the next).

    When loop=True, ensures the last batch has at least 3 frames so there is
    always at least one fillable slot for Gemini to generate the loop-closure
    transition (overlap + fill + loop anchor).
    """
    if total_frames <= batch_size:
        return [BatchInfo(
            batch_index=0, total_batches=1,
            frame_start=1, frame_end=total_frames,
            batch_frames=total_frames,
            is_first=True, is_last=True,
        )]

    batches: list[BatchInfo] = []
    new_per_batch = batch_size - OVERLAP
    n_batches = 1 + math.ceil((total_frames - batch_size) / new_per_batch)

    for i in range(n_batches):
        if i == 0:
            start = 1
            end = batch_size
        else:
            start = batch_size + (i - 1) * new_per_batch
            end = min(start + new_per_batch, total_frames)

        batch_frames = end - start + 1
        batches.append(BatchInfo(
            batch_index=i,
            total_batches=n_batches,
            frame_start=start,
            frame_end=end,
            batch_frames=batch_frames,
            is_first=(i == 0),
            is_last=(i == n_batches - 1),
        ))

    # For looping animations, ensure the last batch has at least 3 frames
    # (1 overlap + 1+ fillable + 1 loop anchor). If it has ≤2, shrink the
    # penultimate batch by 1 to give the last batch room.
    if loop and len(batches) > 1 and batches[-1].batch_frames <= 2:
        prev = batches[-2]
        last = batches[-1]
        new_split = prev.frame_end - 1  # penultimate ends 1 frame earlier
        batches[-2] = BatchInfo(
            batch_index=prev.batch_index,
            total_batches=prev.total_batches,
            frame_start=prev.frame_start,
            frame_end=new_split,
            batch_frames=new_split - prev.frame_start + 1,
            is_first=prev.is_first,
            is_last=False,
        )
        batches[-1] = BatchInfo(
            batch_index=last.batch_index,
            total_batches=last.total_batches,
            frame_start=new_split,
            frame_end=last.frame_end,
            batch_frames=last.frame_end - new_split + 1,
            is_first=False,
            is_last=True,
        )

    return batches


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

    # TODO: add a small compass template in the canvas corner so generated
    # views can communicate orientation without relying on text labels.
    return canvas, cols, (cell_w, cell_h), aspect_ratio, image_size, center_bottom


async def _generate_single_batch(
    provider: GeminiProvider,
    reference_frame: Image.Image,
    animation_type: str,
    batch_frames: int,
    loop: bool,
    character_description: str,
    style: str,
    chromakey_color: str,
    platform: bool,
    tiles: int,
    subject: str,
    slot_bg: Image.Image | None,
    frame_offset: int = 0,
    batch_index: int = 0,
    total_batches: int = 1,
    global_total_frames: int | None = None,
    is_final_batch: bool = False,
    prev_sheet: Image.Image | None = None,
    loop_target: Image.Image | None = None,
    save_dir: Path | None = None,
    batch_label: str = "",
) -> tuple[list[Image.Image], Image.Image]:
    """Generate a single batch of animation frames.

    Returns (extracted_frames, raw_sheet) where raw_sheet is the completed
    sprite sheet image for this batch (used as context for the next batch).
    """
    # Determine whether this batch's canvas should have a loop anchor in the last slot.
    # - Single-batch (first + last): use reference_frame in last slot (original behavior)
    # - Multi-batch final: use loop_target (original frame 1) in last slot
    # - All other batches: no loop anchor
    is_first = batch_index == 0
    if is_final_batch and loop and is_first:
        # Single-batch loop: reference_frame goes in both first and last slot
        batch_loop = True
    elif is_final_batch and loop and loop_target is not None:
        # Multi-batch final: loop_target (original pose) goes in last slot
        batch_loop = True
    else:
        batch_loop = False

    canvas, grid_cols, slot_size, aspect_ratio, image_size = build_canvas(
        reference_frame, batch_frames, chromakey_color,
        slot_bg=slot_bg, loop=batch_loop, frame_offset=frame_offset,
        loop_frame=loop_target,
    )
    grid_rows = math.ceil(batch_frames / grid_cols)

    # Use backward-compatible names for single-batch generation
    if save_dir:
        if total_batches == 1:
            canvas.save(save_dir / "canvas_input.png")
        else:
            canvas.save(save_dir / f"batch_{batch_index}_canvas.png")

    print(f"  {batch_label}Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid, {batch_frames} frames)")
    print(f"  {batch_label}Gemini: {aspect_ratio} ratio, {image_size} output, slot={slot_size[0]}x{slot_size[1]}")

    # Build prompt with batch context
    if subject == "object":
        from pixel_magic.prompts import build_object_animation_prompt

        prompt = build_object_animation_prompt(
            animation_type=animation_type,
            total_frames=batch_frames,
            object_description=character_description,
            style=style,
            chromakey_color=chromakey_color,
            platform=platform,
            loop=batch_loop,
            tiles=tiles,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            batch_index=batch_index,
            total_batches=total_batches,
            global_total_frames=global_total_frames,
            is_final_batch=is_final_batch,
        )
    else:
        prompt = build_canvas_prompt(
            animation_type=animation_type,
            total_frames=batch_frames,
            character_description=character_description,
            style=style,
            chromakey_color=chromakey_color,
            platform=platform,
            loop=batch_loop,
            tiles=tiles,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            batch_index=batch_index,
            total_batches=total_batches,
            global_total_frames=global_total_frames,
            is_final_batch=is_final_batch,
        )

    # Batch 0: single image. Batch 1+: [prev_sheet, canvas]
    images: list[Image.Image] = []
    if prev_sheet is not None:
        images.append(prev_sheet)
    images.append(canvas)

    print(f"  {batch_label}Generating sprite sheet ({len(images)} image(s))...")
    result = await provider.generate_with_images(
        prompt=prompt,
        images=images,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )

    if save_dir:
        suffix = "sheet_raw.png" if total_batches == 1 else f"batch_{batch_index}_sheet_raw.png"
        result.image.save(save_dir / suffix)

    # Platform removal pass
    if platform:
        from pixel_magic.prompts import build_platform_removal_prompt

        removal_prompt = build_platform_removal_prompt(
            batch_frames, chromakey_color,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
        )
        print(f"  {batch_label}Removing platforms (2nd pass)...")
        cleaned = await provider.generate_with_images(
            prompt=removal_prompt,
            images=[result.image],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        if save_dir:
            suffix = "sheet_cleaned.png" if total_batches == 1 else f"batch_{batch_index}_sheet_cleaned.png"
            cleaned.image.save(save_dir / suffix)
        result = cleaned

    sheet = result.image
    if sheet.size != canvas.size:
        sheet = sheet.resize(canvas.size, Image.NEAREST)

    frames = extract_frames(sheet, batch_frames, cols=grid_cols, slot_size=slot_size)
    return frames, sheet


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

    For <= 6 frames, generates in a single batch (unchanged behavior).
    For > 6 frames, splits into multiple 6-frame batches chained by
    overlapping the last frame of each batch as the reference for the next.

    Returns an ordered list of total_frames PIL Images.
    """
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    # Platform mode: composite character onto platform tile
    slot_bg = None
    if platform:
        from pixel_magic.platform import composite_on_platform

        ref_composite, slot_bg, _crop_h = composite_on_platform(reference_frame, tiles=tiles)
    else:
        ref_composite = reference_frame

    batches = _compute_batches(total_frames, loop=loop)

    if len(batches) > 1:
        print(f"  Multi-batch: {len(batches)} batches for {total_frames} frames")

    all_frames: list[Image.Image] = []
    prev_sheet: Image.Image | None = None

    for batch in batches:
        batch_label = f"[Batch {batch.batch_index + 1}/{batch.total_batches}] " if batch.total_batches > 1 else ""

        # Reference frame for this batch's canvas slot 1.
        # All batches must use the same slot dimensions as batch 0 so that
        # slot_bg, loop_target, and grid layout stay consistent.
        if batch.is_first:
            batch_ref = ref_composite
        else:
            # The extracted overlap frame has the correct slot dimensions but
            # a baked-in chromakey background. Strip it to transparent so it
            # composites cleanly over slot_bg (platform) in build_canvas.
            # Do NOT crop or re-composite — that would change the slot size.
            from pixel_magic.background import remove_background

            batch_ref = remove_background(all_frames[-1], chromakey_color=chromakey_color)

        # For loop closure: provide original frame 1 to last batch
        loop_target = None
        if batch.is_last and loop and not batch.is_first:
            loop_target = ref_composite

        batch_frames, batch_sheet = await _generate_single_batch(
            provider=provider,
            reference_frame=batch_ref,
            animation_type=animation_type,
            batch_frames=batch.batch_frames,
            loop=loop,
            character_description=character_description,
            style=style,
            chromakey_color=chromakey_color,
            platform=platform,
            tiles=tiles,
            subject=subject,
            slot_bg=slot_bg,
            frame_offset=batch.frame_start - 1,
            batch_index=batch.batch_index,
            total_batches=batch.total_batches,
            global_total_frames=total_frames,
            is_final_batch=batch.is_last,
            prev_sheet=prev_sheet,
            loop_target=loop_target,
            save_dir=save_dir,
            batch_label=batch_label,
        )

        # Collect frames: skip overlap frame for batch 1+ (it's a duplicate)
        if batch.is_first:
            all_frames.extend(batch_frames)
        else:
            all_frames.extend(batch_frames[1:])

        prev_sheet = batch_sheet

    return all_frames


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
