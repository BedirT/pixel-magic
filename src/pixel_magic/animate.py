"""Canvas-based sprite sheet animation generation."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from pixel_magic.prompts import build_canvas_prompt
from pixel_magic.providers.gemini import GeminiProvider

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


def _draw_frame_number(
    canvas: Image.Image,
    number: int,
    slot_x: int,
    slot_y: int,
    slot_width: int,
) -> None:
    """Draw a pixel-art frame number in the top-left corner of a slot."""
    scale = max(2, slot_width // 60)
    margin = scale * 2
    gap = scale  # gap between multi-digit numbers

    digits = [int(d) for d in str(number)]

    x0 = slot_x + margin
    y0 = slot_y + margin

    for digit in digits:
        bitmap = _DIGIT_BITMAPS[digit]
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


def _grid_layout(n_frames: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Find (cols, rows) grid closest to 16:9 aspect ratio."""
    target = 16 / 9
    best = (n_frames, 1)
    best_diff = float("inf")

    for cols in range(1, n_frames + 1):
        rows = math.ceil(n_frames / cols)
        ratio = (cols * slot_w) / (rows * slot_h)
        diff = abs(ratio - target)
        if diff < best_diff:
            best_diff = diff
            best = (cols, rows)

    return best


def build_canvas(
    reference_frame: Image.Image,
    total_frames: int,
    chromakey_color: str = "green",
    slot_bg: Image.Image | None = None,
    loop: bool = False,
) -> tuple[Image.Image, int]:
    """Build a sprite sheet canvas with frames arranged in a grid.

    Frames are laid out in a cols x rows grid approximating 16:9 aspect ratio.
    Empty slots get a pixel-art frame number in the top-left corner.

    If loop=True, the reference is placed in both slot 1 and the last slot.
    If slot_bg is provided, it's placed in every slot (behind reference).

    Returns (canvas, cols) — cols needed by extract_frames().
    """
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    w, h = reference_frame.size
    cols, rows = _grid_layout(total_frames, w, h)

    canvas = Image.new("RGBA", (w * cols, h * rows), (*fill, 255))

    # Place slot backgrounds and frame numbers on all slots
    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        x, y = col * w, row * h

        if slot_bg is not None:
            canvas.paste(slot_bg, (x, y), slot_bg if slot_bg.mode == "RGBA" else None)

        _draw_frame_number(canvas, idx + 1, x, y, w)

    # Place reference in slot 1 (covers frame number underneath)
    canvas.paste(
        reference_frame, (0, 0),
        reference_frame if reference_frame.mode == "RGBA" else None,
    )

    # Loop: also place reference in last slot
    if loop:
        last_idx = total_frames - 1
        lx = (last_idx % cols) * w
        ly = (last_idx // cols) * h
        canvas.paste(
            reference_frame, (lx, ly),
            reference_frame if reference_frame.mode == "RGBA" else None,
        )

    return canvas, cols


def extract_frames(
    sheet: Image.Image,
    total_frames: int,
    cols: int | None = None,
) -> list[Image.Image]:
    """Extract frames from a grid-layout sprite sheet.

    If cols is None, falls back to horizontal strip (legacy).
    """
    if cols is None:
        cols = total_frames
    rows = math.ceil(total_frames / cols)
    slot_w = sheet.width // cols
    slot_h = sheet.height // rows

    frames = []
    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        frame = sheet.crop((col * slot_w, row * slot_h, (col + 1) * slot_w, (row + 1) * slot_h))
        frames.append(frame)
    return frames


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

    # Build canvas
    canvas, grid_cols = build_canvas(ref_composite, total_frames, chromakey_color, slot_bg=slot_bg, loop=loop)
    grid_rows = math.ceil(total_frames / grid_cols)
    if save_dir:
        canvas.save(save_dir / "canvas_input.png")

    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid, {total_frames} frames)")

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
        )
        if save_dir:
            cleaned.image.save(save_dir / "sheet_cleaned.png")
        result = cleaned

    # Extract frames
    frames = extract_frames(result.image, total_frames, cols=grid_cols)

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
