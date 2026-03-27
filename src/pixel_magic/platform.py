"""Procedural isometric platform generation for animation frames."""

from __future__ import annotations

from PIL import Image, ImageDraw

# Stone-colored isometric tile (pixel art style)
_TOP_COLOR = (185, 190, 175, 255)
_LEFT_COLOR = (120, 125, 112, 255)
_RIGHT_COLOR = (152, 157, 143, 255)
_OUTLINE = (0, 0, 0, 255)


def create_platform(width: int, depth: int = 8) -> Image.Image:
    """Create an isometric diamond platform tile (RGBA, transparent bg)."""
    if width % 2 != 0:
        width += 1

    diamond_h = width // 2
    total_h = diamond_h + depth

    img = Image.new("RGBA", (width, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = width // 2
    cy = diamond_h // 2
    bot = diamond_h - 1

    # Face polygons
    top = [(cx, 0), (width - 1, cy), (cx, bot), (0, cy)]
    left = [(0, cy), (cx, bot), (cx, bot + depth), (0, cy + depth)]
    right = [(width - 1, cy), (cx, bot), (cx, bot + depth), (width - 1, cy + depth)]

    # Fill (sides first, then top on top)
    draw.polygon(left, fill=_LEFT_COLOR)
    draw.polygon(right, fill=_RIGHT_COLOR)
    draw.polygon(top, fill=_TOP_COLOR)

    # Outer silhouette — 1px black outline
    silhouette = [
        (cx, 0),
        (width - 1, cy),
        (width - 1, cy + depth),
        (cx, bot + depth),
        (0, cy + depth),
        (0, cy),
    ]
    for i in range(len(silhouette)):
        draw.line(
            [silhouette[i], silhouette[(i + 1) % len(silhouette)]],
            fill=_OUTLINE,
            width=1,
        )

    return img


def create_platform_grid(
    tile_width: int,
    tile_depth: int = 8,
    grid_size: int = 1,
) -> Image.Image:
    """Draw a unified isometric platform with grid lines on top.

    grid_size=1: single tile
    grid_size=2: 2x2 diamond (4 tiles)
    grid_size=3: 3x3 diamond (9 tiles)

    Draws as ONE block with tile division lines — no seams between tiles.
    Returns RGBA image with transparent background.
    """
    if grid_size == 1:
        return create_platform(tile_width, tile_depth)

    if tile_width % 2 != 0:
        tile_width += 1

    # Full grid diamond dimensions
    # Image is 1px wider/taller than grid_size*tile_width so the diamond
    # corners land at exact tile_width multiples. This makes full_w - cx == cx
    # and bot - cy == cy, so all grid divisions are exact integers (zero rounding error).
    full_w = grid_size * tile_width
    diamond_h = full_w // 2
    total_h = diamond_h + 1 + tile_depth

    img = Image.new("RGBA", (full_w + 1, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = full_w // 2
    cy = diamond_h // 2
    bot = diamond_h

    # Draw unified block (same as single tile but scaled up)
    top_face = [(cx, 0), (full_w, cy), (cx, bot), (0, cy)]
    left_face = [(0, cy), (cx, bot), (cx, bot + tile_depth), (0, cy + tile_depth)]
    right_face = [(full_w, cy), (cx, bot), (cx, bot + tile_depth), (full_w, cy + tile_depth)]

    draw.polygon(left_face, fill=_LEFT_COLOR)
    draw.polygon(right_face, fill=_RIGHT_COLOR)
    draw.polygon(top_face, fill=_TOP_COLOR)

    # Outer silhouette
    silhouette = [
        (cx, 0),
        (full_w, cy),
        (full_w, cy + tile_depth),
        (cx, bot + tile_depth),
        (0, cy + tile_depth),
        (0, cy),
    ]
    for i in range(len(silhouette)):
        draw.line(
            [silhouette[i], silhouette[(i + 1) % len(silhouette)]],
            fill=_OUTLINE,
            width=1,
        )

    # Draw tile grid lines — top face + vertical lines down the side faces
    # With the +1 image sizing, all divisions are exact: t*cx and t*cy are always integers
    for i in range(1, grid_size):
        t = i / grid_size
        # Top face: lines parallel to left→bottom edge (NE-SW)
        draw.line([
            (int(cx + t * cx), int(t * cy)),
            (int(t * cx), int(cy + t * cy)),
        ], fill=_OUTLINE, width=1)
        # Left side face: vertical line down from the left-bottom edge division
        lx = int(t * cx)
        ly = int(cy + t * cy)
        draw.line([(lx, ly), (lx, ly + tile_depth)], fill=_OUTLINE, width=1)

    for i in range(1, grid_size):
        t = i / grid_size
        # Top face: lines parallel to right→bottom edge (NW-SE)
        draw.line([
            (int(cx - t * cx), int(t * cy)),
            (int(full_w - t * cx), int(cy + t * cy)),
        ], fill=_OUTLINE, width=1)
        # Right side face: vertical line down from the right-bottom edge division
        rx = int(full_w - t * cx)
        ry = int(cy + t * cy)
        draw.line([(rx, ry), (rx, ry + tile_depth)], fill=_OUTLINE, width=1)

    return img


def composite_on_platform(
    character: Image.Image,
    char_scale: float = 0.8,
    platform_ratio: float = 1.15,
    platform_depth: int = 32,
    tiles: int = 1,
) -> tuple[Image.Image, Image.Image, int]:
    """Scale character down and place on an isometric platform.

    The character is shrunk to leave room for headroom above and
    the platform below, all within a frame sized from the original.

    Returns:
        (composite, platform_only, crop_height)
        - composite: scaled character standing on platform (RGBA)
        - platform_only: same dimensions, just the platform (for empty canvas slots)
        - crop_height: crop frames here after generation to remove the platform
    """
    char_w, char_h = character.size

    # Auto-scale character based on tile grid — larger grids → smaller character
    # so slot width stays bounded while giving more floor space
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
    _grid_scale = {1: 1.0, 2: 0.68, 3: 0.50}
    char_scale = char_scale * _grid_scale.get(grid_size, 1.0)

    # Scale character down to make room
    new_w = int(char_w * char_scale)
    new_h = int(char_h * char_scale)
    scaled = character.resize((new_w, new_h), Image.NEAREST)

    # Platform sized relative to scaled character
    plat_w = int(new_w * platform_ratio)
    platform = create_platform_grid(plat_w, platform_depth, grid_size=grid_size)
    single_diamond_h = plat_w // 2

    comp_w = max(char_w, platform.width)

    # Layout from top: [headroom] [scaled char] [platform]
    # Character feet land towards the center of the tile grid
    grid_center_offset = (grid_size - 1) * single_diamond_h // 2
    overlap = int(single_diamond_h * 0.7) + grid_center_offset
    saved_space = char_h - new_h
    headroom = saved_space // 3  # 1/3 of freed space → headroom

    char_x = (comp_w - new_w) // 2
    char_y = headroom
    platform_x = (comp_w - platform.width) // 2
    platform_y = char_y + new_h - overlap

    comp_h = platform_y + platform.height

    # Crop point: just below character's feet (removes platform)
    crop_h = char_y + new_h

    # Platform-only image (for empty canvas slots)
    platform_only = Image.new("RGBA", (comp_w, comp_h), (0, 0, 0, 0))
    platform_only.paste(platform, (platform_x, platform_y), platform)

    # Composite: platform behind, scaled character in front
    composite = Image.new("RGBA", (comp_w, comp_h), (0, 0, 0, 0))
    composite.paste(platform, (platform_x, platform_y), platform)
    composite.paste(scaled, (char_x, char_y), scaled if scaled.mode == "RGBA" else None)

    return composite, platform_only, crop_h
