"""Prompt builders for character sprite sheets and animation frames."""

from __future__ import annotations

import json
from typing import Any


_CHROMAKEY_HEX = {"green": "#00FF00", "blue": "#0000FF"}

_VIEWS_4DIR: list[dict[str, str]] = [
    {
        "position": "left",
        "facing": "front-left (3/4 view, south_east)",
        "description": "Front-facing isometric view — face and chest visible from a 3/4 top-down angle",
    },
    {
        "position": "right",
        "facing": "back-right (3/4 view, north_east)",
        "description": "Rear-facing isometric view — back and top of head visible",
    },
]

_VIEWS_8DIR: list[dict[str, str]] = [
    {
        "position": "far_left",
        "facing": "back (north)",
        "description": "Full back view from above — top of head and back visible",
    },
    {
        "position": "center_left",
        "facing": "back-right (3/4 view, north_east)",
        "description": "Rear 3/4 view — back and right shoulder visible from above",
    },
    {
        "position": "center",
        "facing": "right (east)",
        "description": "Side view from above — right profile visible",
    },
    {
        "position": "center_right",
        "facing": "front-right (3/4 view, south_east)",
        "description": "Front 3/4 view — face and chest visible from a top-down angle",
    },
    {
        "position": "far_right",
        "facing": "front (south)",
        "description": "Front view from above — face and front of body visible",
    },
]


def _background_instruction(chromakey_color: str = "green") -> str:
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return f"solid {chromakey_color} ({hex_color}) background (every non-sprite pixel must be exactly {hex_color})"


def _background_rule(chromakey_color: str = "green") -> str:
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return f"The ENTIRE image background MUST be solid {chromakey_color} ({hex_color}) — no transparency, no gradients, no shadows, just flat {chromakey_color}"


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
    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "character_sprite_reference_sheet",
        "background": {
            "type": "chromakey",
            "rule": _background_rule(chromakey_color),
            "instruction": _background_instruction(chromakey_color),
        },
        "views": views,
        "character": {
            "description": character_description,
            "pose": "standing idle",
            "consistency_rule": (
                "Every view must depict the EXACT same character — identical proportions, "
                "palette, clothing, accessories, and level of detail. Only the facing "
                "direction changes between views."
            ),
        },
        "art_details": {
            "pixel_density": "medium",
            "shading": "simple 2-3 tone stepped shading per color area",
            "outline": "Every element MUST have a 1-pixel black (#000000) outline — the character, all accessories, weapons, effects (fire, magic, particles), and every separate visual part must be fully enclosed by a black pixel border with no gaps",
            "anti_aliasing": "none — every edge is a hard pixel step",
            "perspective": "isometric 3/4 top-down (~30 degrees from above)",
            "target_resolution_per_view": resolution,
            "max_colors": max_colors,
            "style_reference": (
                "Classic SNES/Genesis pixel art: Final Fantasy Tactics, "
                "Tactics Ogre, Chrono Trigger overworld sprites"
            ),
        },
        "layout": {
            "arrangement": "horizontal row, evenly spaced, well separated",
            "spacing": "generous gap between each view so they do not overlap or touch",
            "centering": "each character view centered vertically in its area",
        },
    }

    if palette_hint:
        prompt["color_palette_hint"] = palette_hint

    return json.dumps(prompt, indent=2)


# ---------------------------------------------------------------------------
# Canvas-based sprite sheet animation prompt
# ---------------------------------------------------------------------------

_ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "walk": "a walk cycle — the character takes steps forward, legs alternating, arms swinging naturally. Each frame shows a different phase of the stride.",
    "idle": "an idle/breathing animation — very subtle motion, the character shifts weight slightly and breathes. Minimal movement.",
    "attack": "an attack animation — the character winds up, strikes with their weapon at full extension, then follows through.",
    "run": "a run cycle — similar to walk but faster, with more exaggerated leg extension and body lean.",
    "cast": "a spell casting animation — the character raises their hands, channels energy, and releases a spell.",
}


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
    """Build a prompt for canvas-based sprite sheet generation.

    The caller creates a canvas with frame 1 placed in slot 1 and
    the remaining slots filled with chromakey green. The model is
    asked to fill in the green slots with animation frames.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    anim_desc = _ANIMATION_DESCRIPTIONS.get(animation_type, f"a {animation_type} animation.")

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    character_line = ""
    if character_description:
        character_line = f"\nThe character is {character_description}."

    if loop:
        middle_count = total_frames - 2
        loop_desc = f"The FIRST and LAST slots both show the same character pose — this is a LOOPING animation. Fill in the {middle_count} middle slots (slots 2–{total_frames - 1}) with animation frames that smoothly transition from the first pose, through the full motion, and back to the same pose."
        anchor_rule = f"- Do NOT modify the first or last slot — they are identical anchor poses for the loop\n- The animation must smoothly cycle: frame {total_frames} flows back into frame 1"
    else:
        loop_desc = f"The FIRST slot contains the starting pose. Fill in the remaining {total_frames - 1} slots with animation frames."
        anchor_rule = "- Do NOT modify the first slot — it is the reference frame, leave it exactly as-is"

    if platform:
        if tiles == 1:
            floor_desc = "an isometric stone platform"
        elif tiles == 4:
            floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
        else:
            floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"

        if loop:
            slot_desc = f"The FIRST and LAST slots show a pixel art character standing on {floor_desc}. The {middle_count} middle slots each have the same floor but NO character."
        else:
            slot_desc = f"The FIRST slot shows a pixel art character standing on {floor_desc}. The remaining {total_frames - 1} slots each have the same floor but NO character."

        if tiles > 1:
            space_rule = "\n- The character has extra floor space — use it for the full range of motion (extended limbs, weapon swings, lunges)"
        else:
            space_rule = ""

        return f"""\
This image is a sprite sheet with {layout_desc}, on a {chromakey_color} ({hex_color}) background. {slot_desc}

{loop_desc} Show {anim_desc}
{character_line}

RULES:
- Draw the SAME character on each platform — identical proportions, colors, outfit, pixel art style
- Each filled slot must show a DIFFERENT pose progressing through the animation
{anchor_rule}
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
- Do NOT modify the stone platforms — draw the character standing ON TOP of them
- The character's feet must rest on the platform surface in every frame
- Maintain the isometric 3/4 top-down perspective — the platform establishes the ground plane{space_rule}
- Style: {style}
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all character elements
- Same color palette across all frames
- {chromakey_color} ({hex_color}) background must remain around the character and platform"""

    return f"""\
This image is a sprite sheet with {layout_desc}. {loop_desc}
{character_line}

Show {anim_desc}

RULES:
- Draw the SAME character in each slot — identical proportions, colors, outfit, pixel art style
- Each filled slot must show a DIFFERENT pose progressing through the animation
{anchor_rule}
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
- Only draw inside the {chromakey_color} areas
- Keep the {chromakey_color} ({hex_color}) background within each frame slot
- Style: {style}, isometric 3/4 top-down view
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all character elements
- Same color palette across all frames"""


def build_platform_removal_prompt(
    total_frames: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for a second Gemini pass that removes platforms and frame numbers."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")

    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a horizontal row"

    return f"""\
This is a pixel art sprite sheet with {total_frames} character frames {layout_desc} on stone platforms. Some frames have small white numbers in the corner.

Remove the stone platforms AND the frame numbers from EVERY frame. Replace all platform and number pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the characters EXACTLY as they are — same proportions, colors, poses, pixel art style
- Do NOT modify any character pixels — only remove the stone platforms and corner numbers
- Fill where the platforms and numbers were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} frame layout"""


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
    """Build a JSON-structured prompt for canvas-based character generation.

    The caller creates a canvas with labeled platforms in a grid.
    The model draws the same character on each platform facing the labeled direction.
    Uses the same structured JSON format as the text-only prompt for consistent
    pixel art quality.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

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

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    # Build position descriptions based on grid layout
    _POSITION_NAMES_4DIR = ["left platform", "right platform"]
    _POSITION_NAMES_8DIR = [
        "top-left platform", "top-center platform", "top-right platform",
        "bottom-left platform", "bottom-right platform",
    ]
    pos_names = _POSITION_NAMES_4DIR if direction_mode == 4 else _POSITION_NAMES_8DIR

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "character_sprite_reference_sheet",
        "reference_image": {
            "description": (
                f"The attached image shows the exact layout to follow: "
                f"{len(views)} isometric stone platforms{layout_desc} "
                f"on {chromakey_color} ({hex_color}) background"
            ),
            "usage": "Match platform positions and spacing exactly. "
                     "Draw one character per platform facing the direction "
                     "specified below for each position.",
        },
        "background": {
            "type": "chromakey",
            "rule": _background_rule(chromakey_color),
            "instruction": _background_instruction(chromakey_color),
        },
        "views": [
            {
                "platform_position": pos_names[i],
                "facing": v["facing"],
                "description": v["description"],
            }
            for i, v in enumerate(views)
        ],
        "character": {
            "description": character_description,
            "pose": "standing idle",
            "consistency_rule": (
                "Every view must depict the EXACT same character — identical "
                "proportions, palette, clothing, accessories, and level of "
                "detail. Only the facing direction changes between views."
            ),
        },
        "placement": {
            "floor": floor_desc,
            "feet": "character's feet must touch the platform surface — firmly planted, not floating",
            "centering": "character centered on each platform",
            "size": size_hint,
        },
        "art_details": {
            "pixel_density": "medium",
            "shading": "simple 2-3 tone stepped shading per color area",
            "outline": (
                "Every element MUST have a 1-pixel black (#000000) outline — "
                "the character, all accessories, weapons, effects, and every "
                "separate visual part must be fully enclosed by a black pixel "
                "border with no gaps"
            ),
            "anti_aliasing": "none — every edge is a hard pixel step",
            "perspective": "isometric 3/4 top-down (~30 degrees from above)",
            "target_resolution_per_view": resolution,
            "max_colors": max_colors,
            "style_reference": (
                "Classic SNES/Genesis pixel art: Final Fantasy Tactics, "
                "Tactics Ogre, Chrono Trigger overworld sprites"
            ),
        },
    }

    return json.dumps(prompt, indent=2)


def build_generation_cleanup_prompt(
    view_count: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing platforms and labels from generated character sheet."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"
    return f"""\
This is a pixel art character sheet with {view_count} character views {layout_desc} on stone platforms. Each platform has a direction label in the corner.

Remove the stone platforms AND the direction labels from EVERY view. Replace all platform and label pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the characters EXACTLY as they are — same proportions, colors, poses, pixel art style
- Do NOT modify any character pixels — only remove the stone platforms and corner labels
- Fill where the platforms and labels were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} layout"""


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
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    if depth > 0:
        shape_desc = "an isometric diamond with visible side faces (3D depth)"
        fill_rule = (
            "Fill the diamond top face with the terrain texture. "
            "Draw appropriate side faces below the diamond edges to give the tile depth and volume."
        )
    else:
        shape_desc = "a flat isometric diamond (top face only)"
        fill_rule = "Fill only the diamond top face with the terrain texture. No side faces."

    tiles_desc = [
        {"slot": i + 1, "label": label, "terrain": label}
        for i, label in enumerate(tile_labels)
    ]

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "terrain_tileset",
        "reference_image": {
            "description": (
                f"The attached image shows {len(tile_labels)} labeled isometric diamond outlines"
                f"{layout_desc} on {chromakey_color} ({hex_color}) background"
            ),
            "usage": (
                "Each diamond outline shows exactly where to draw the terrain tile. "
                "Fill each diamond with the terrain texture labeled above it."
            ),
        },
        "background": {
            "type": "chromakey",
            "rule": _background_rule(chromakey_color),
            "instruction": _background_instruction(chromakey_color),
        },
        "tiles": tiles_desc,
        "shape": {
            "type": shape_desc,
            "fill_rule": fill_rule,
        },
        "art_details": {
            "pixel_density": "medium",
            "shading": "simple 2-3 tone stepped shading per color area",
            "outline": "1-pixel black (#000000) outline around the entire tile perimeter",
            "anti_aliasing": "none — every edge is a hard pixel step",
            "perspective": "isometric 3/4 top-down (~30 degrees from above)",
            "max_colors": max_colors,
            "style_reference": style,
            "lighting": "consistent upper-left light source across all tiles",
        },
        "tiling_rules": {
            "seamless": "tile edges should be designed to connect smoothly when placed adjacent in an isometric grid",
            "consistency": "all tiles must share the same art style, palette warmth, and level of detail",
        },
    }

    return json.dumps(prompt, indent=2)


def build_tile_cleanup_prompt(
    tile_count: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing labels and wireframe guides from generated tiles."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"

    return f"""\
This is a pixel art tileset with {tile_count} isometric terrain tiles {layout_desc}. Each tile has a text label above it and may have thin black wireframe guide lines.

Remove the text labels AND any wireframe guide outlines from EVERY tile. Replace those pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the terrain tiles EXACTLY as they are — same textures, colors, shading, pixel art style
- Do NOT modify any terrain tile pixels — only remove the text labels and wireframe guides
- Fill where the labels and guides were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} layout"""
