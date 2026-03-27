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
    """Arrange tiles in an isometric diamond grid.

    grid_size=1: single tile
    grid_size=2: 2x2 diamond (4 tiles)
    grid_size=3: 3x3 diamond (9 tiles)

    Returns RGBA image with transparent background.
    """
    if grid_size == 1:
        return create_platform(tile_width, tile_depth)

    tile = create_platform(tile_width, tile_depth)
    tw, th = tile.size
    diamond_h = tile_width // 2

    # Isometric grid dimensions
    grid_w = grid_size * tw
    grid_h = grid_size * diamond_h + tile_depth

    grid_img = Image.new("RGBA", (grid_w, grid_h), (0, 0, 0, 0))

    # Place tiles back-to-front for correct overlap
    for row in range(grid_size):
        for col in range(grid_size):
            x = (col - row) * (tw // 2) + (grid_size - 1) * (tw // 2)
            y = (col + row) * (diamond_h // 2)
            grid_img.paste(tile, (x, y), tile)

    return grid_img


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
