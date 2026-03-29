"""Prompt builders for character/object sprite sheets and animation frames.

All prompts are rendered from Jinja2 JSON templates in ``templates/``.
Function signatures are backward-compatible with the old monolithic prompts.py.
"""

from __future__ import annotations

import json

from pixel_magic.prompts._data import (
    ANIMATION_DESCRIPTIONS,
    CHROMAKEY_HEX,
    EFFECT_ANIMATION_DESCRIPTIONS,
    OBJECT_ANIMATION_DESCRIPTIONS,
    POSITION_NAMES_4DIR,
    POSITION_NAMES_8DIR,
    VIEWS_4DIR,
    VIEWS_8DIR,
    background_instruction,
    background_rule,
)
from pixel_magic.prompts._engine import render


def build_character_sheet_prompt(
    character_description: str,
    direction_mode: int = 4,
    style: str = "16-bit SNES RPG style",
    resolution: str = "64x64",
    max_colors: int = 16,
    palette_hint: str = "",
    chromakey_color: str = "green",
) -> str:
    """Build a JSON-structured prompt for multi-view character reference sheet."""
    views = VIEWS_4DIR if direction_mode == 4 else VIEWS_8DIR
    return render(
        "character_sheet.json.j2",
        character_description=character_description,
        views=views,
        resolution=resolution,
        max_colors=max_colors,
        palette_hint=palette_hint,
        background_rule=background_rule(chromakey_color),
        background_instruction=background_instruction(chromakey_color),
    )


# ---------------------------------------------------------------------------
# Canvas-based sprite sheet animation prompt
# ---------------------------------------------------------------------------


def build_canvas_prompt(
    animation_type: str,
    total_frames: int,
    character_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "green",
    platform: bool = False,
    loop: bool = False,
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for canvas-based sprite sheet generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    anim_desc = ANIMATION_DESCRIPTIONS.get(animation_type, f"a {animation_type} animation.")

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    middle_count = total_frames - 2 if loop else 0

    # Platform floor description
    if tiles == 1:
        floor_desc = "an isometric stone platform"
    elif tiles == 4:
        floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
    else:
        floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"

    return render(
        "canvas_animation.json.j2",
        animation_type=animation_type,
        total_frames=total_frames,
        character_description=character_description,
        style=style,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        platform=platform,
        loop=loop,
        tiles=tiles,
        layout_desc=layout_desc,
        anim_desc=anim_desc,
        middle_count=middle_count,
        floor_desc=floor_desc,
    )


# ---------------------------------------------------------------------------
# Canvas-based object animation prompt
# ---------------------------------------------------------------------------


def build_object_animation_prompt(
    animation_type: str,
    total_frames: int,
    object_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "pink",
    platform: bool = False,
    loop: bool = True,
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for object animation sprite sheet generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    anim_desc = OBJECT_ANIMATION_DESCRIPTIONS.get(
        animation_type,
        ANIMATION_DESCRIPTIONS.get(animation_type, f"a {animation_type} animation."),
    )

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    middle_count = total_frames - 2 if loop else 0

    if tiles == 1:
        floor_desc = "an isometric stone platform"
    elif tiles == 4:
        floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
    else:
        floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"

    return render(
        "object_animation.json.j2",
        animation_type=animation_type,
        total_frames=total_frames,
        object_description=object_description,
        style=style,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        platform=platform,
        loop=loop,
        tiles=tiles,
        layout_desc=layout_desc,
        anim_desc=anim_desc,
        middle_count=middle_count,
        floor_desc=floor_desc,
    )


# ---------------------------------------------------------------------------
# Effect animation prompts (subjectless VFX)
# ---------------------------------------------------------------------------


def build_effect_animation_prompt(
    effect_name: str,
    total_frames: int,
    effect_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "pink",
    loop: bool = False,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for single-pass effect animation generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    anim_desc = EFFECT_ANIMATION_DESCRIPTIONS.get(
        effect_name, f"a {effect_name.replace('_', ' ')} animation.",
    )

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    return render(
        "effect_animation.json.j2",
        effect_name=effect_name,
        total_frames=total_frames,
        effect_description=effect_description,
        style=style,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        loop=loop,
        layout_desc=layout_desc,
        anim_desc=anim_desc,
    )


def build_effect_cleanup_prompt(
    total_frames: int,
    chromakey_color: str = "pink",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing frame guide numbers from effect sprite sheets."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")

    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a horizontal row"

    return render(
        "effect_cleanup.json.j2",
        total_frames=total_frames,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
    )


def build_platform_removal_prompt(
    total_frames: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for a second Gemini pass that removes platforms and frame numbers."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")

    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a horizontal row"

    return render(
        "platform_removal.json.j2",
        total_frames=total_frames,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
    )


# ---------------------------------------------------------------------------
# Canvas-based character generation prompts (platform-based)
# ---------------------------------------------------------------------------


def build_generation_canvas_prompt(
    character_description: str,
    direction_mode: int = 4,
    style: str = "16-bit SNES RPG style",
    resolution: str = "64x64",
    max_colors: int = 16,
    chromakey_color: str = "green",
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a JSON-structured prompt for canvas-based character generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    views_data = VIEWS_4DIR if direction_mode == 4 else VIEWS_8DIR
    pos_names = POSITION_NAMES_4DIR if direction_mode == 4 else POSITION_NAMES_8DIR

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    if tiles == 1:
        floor_desc = "a single isometric stone platform tile"
    elif tiles == 4:
        floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
    else:
        floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"

    if tiles > 1:
        size_hint = "large enough to fill most of the platform"
    else:
        size_hint = "tall — about 2-3x the height of the platform"

    # Build views with platform positions
    views = [
        {
            "platform_position": pos_names[i],
            "facing": v["facing"],
            "description": v["description"],
        }
        for i, v in enumerate(views_data)
    ]

    return render(
        "generation_canvas.json.j2",
        character_description=character_description,
        n_views=len(views_data),
        views=views,
        resolution=resolution,
        max_colors=max_colors,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
        floor_desc=floor_desc,
        size_hint=size_hint,
        background_rule=background_rule(chromakey_color),
        background_instruction=background_instruction(chromakey_color),
    )


def build_generation_cleanup_prompt(
    view_count: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing platforms and labels from generated character sheet."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"

    return render(
        "generation_cleanup.json.j2",
        view_count=view_count,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
    )


# ---------------------------------------------------------------------------
# Tile generation prompts
# ---------------------------------------------------------------------------


def build_tile_canvas_prompt(
    tile_labels: list[str],
    style: str = "16-bit SNES RPG style",
    max_colors: int = 16,
    chromakey_color: str = "green",
    depth: int = 4,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a JSON-structured prompt for canvas-based tile generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    tiles = [
        {"slot": i + 1, "label": label, "terrain": label}
        for i, label in enumerate(tile_labels)
    ]

    return render(
        "tile_canvas.json.j2",
        tile_count=len(tile_labels),
        tiles=tiles,
        style=style,
        max_colors=max_colors,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        depth=depth,
        layout_desc=layout_desc,
        background_rule=background_rule(chromakey_color),
        background_instruction=background_instruction(chromakey_color),
    )


def build_tile_cleanup_prompt(
    tile_count: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing labels and wireframe guides from generated tiles."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"

    return render(
        "tile_cleanup.json.j2",
        tile_count=tile_count,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
    )


# ---------------------------------------------------------------------------
# Object generation prompts
# ---------------------------------------------------------------------------


def build_object_canvas_prompt(
    object_labels: list[str],
    description: str = "",
    style: str = "16-bit SNES RPG style",
    max_colors: int = 16,
    chromakey_color: str = "pink",
    depth: int = 8,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a JSON-structured prompt for canvas-based object generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    objects = [
        {"slot": i + 1, "label": label}
        for i, label in enumerate(object_labels)
    ]

    return render(
        "object_canvas.json.j2",
        object_count=len(object_labels),
        objects=objects,
        description=description,
        style=style,
        max_colors=max_colors,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
        background_rule=background_rule(chromakey_color),
        background_instruction=background_instruction(chromakey_color),
    )


def build_object_cleanup_prompt(
    object_count: int,
    chromakey_color: str = "pink",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing platforms and labels from generated objects."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"

    return render(
        "object_cleanup.json.j2",
        object_count=object_count,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        layout_desc=layout_desc,
    )
