"""Prompt builders for character/object sprite sheets and animation frames.

All prompts are rendered from Jinja2 JSON templates in ``templates/``.
Function signatures are backward-compatible with the old monolithic prompts.py.
"""

from __future__ import annotations

from pixel_magic.prompts._data import (
    CHROMAKEY_HEX,
    DEFAULT_EFFECT_SPATIAL_RULES,
    DEFAULT_OBJECT_SPATIAL_RULES,
    DEFAULT_SPATIAL_RULES,
    POSITION_NAMES_4DIR,
    POSITION_NAMES_8DIR,
    VIEWS_4DIR,
    VIEWS_8DIR,
    background_instruction,
    background_rule,
)
from pixel_magic.prompts._engine import render


# ---------------------------------------------------------------------------
# Single-frame animation prompt
# ---------------------------------------------------------------------------


def build_single_frame_prompt(
    pose_description: str,
    frame_number: int,
    total_frames: int,
    animation_description: str,
    character_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "green",
    subject: str = "character",
    direction: str = "",
    loop: bool = True,
    is_last: bool = False,
) -> str:
    """Build a prompt for generating a single animation frame."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")

    # Orientation description from direction
    orientation = ""
    if direction:
        facing = direction.replace("_", "-")
        orientation = f"The {subject} is facing {facing} in an isometric 3/4 top-down view."

    spatial_rules = DEFAULT_OBJECT_SPATIAL_RULES if subject == "object" else DEFAULT_SPATIAL_RULES

    return render(
        "single_frame_animation.json.j2",
        pose_description=pose_description,
        frame_number=frame_number,
        total_frames=total_frames,
        animation_description=animation_description,
        character_description=character_description,
        style=style,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        subject=subject,
        orientation=orientation,
        loop=loop,
        is_last=is_last,
        has_previous_frame=frame_number > 2,
        spatial_rules=spatial_rules,
    )


# ---------------------------------------------------------------------------
# Character sheet prompt (non-animation)
# ---------------------------------------------------------------------------


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
# Effect animation prompts (subjectless VFX)
# ---------------------------------------------------------------------------


def build_effect_animation_prompt(
    animation_description: str,
    total_frames: int,
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "pink",
    loop: bool = False,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
    frame_poses: list[str] | None = None,
) -> str:
    """Build a prompt for single-pass effect animation generation."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    # Effects have no anchor reference frame — all slots are fillable.
    # For loops, the last frame is replaced by enforce_loop_closure, so cap
    # user poses to total_frames - 1 to avoid describing a discarded frame.
    frame_poses_data = None
    if frame_poses:
        max_poses = total_frames - 1 if loop else total_frames
        capped = frame_poses[:max_poses]
        frame_poses_data = [
            {"slot": i + 1, "pose": pose}
            for i, pose in enumerate(capped)
        ]

    return render(
        "effect_animation.json.j2",
        total_frames=total_frames,
        animation_description=animation_description,
        style=style,
        chromakey_color=chromakey_color,
        hex_color=hex_color,
        loop=loop,
        layout_desc=layout_desc,
        frame_poses_data=frame_poses_data,
        spatial_rules=DEFAULT_EFFECT_SPATIAL_RULES,
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
