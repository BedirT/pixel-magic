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
            "type": "transparent",
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
    max_colors: int = 16,
    chromakey_color: str = "green",
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for canvas-based character generation.

    The caller creates a canvas with labeled platforms in a grid.
    The model draws the same character on each platform facing the labeled direction.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

    if tiles == 1:
        floor_desc = "an isometric stone platform"
    elif tiles == 4:
        floor_desc = "a 2x2 isometric stone tile floor"
    else:
        floor_desc = "a 3x3 isometric stone tile floor"

    view_list = "\n".join(
        f"  - Platform labeled \"{v['facing'].split('(')[0].strip()}\": "
        f"draw the character {v['description'].lower()}"
        for v in views
    )

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" arranged in a {grid_cols}x{grid_rows} grid"

    return f"""\
This image shows {len(views)} labeled {floor_desc}s{layout_desc} on a {chromakey_color} ({hex_color}) background. Each platform has a direction label in the corner.

Draw the SAME pixel art character on every platform, facing the labeled direction:
{view_list}

The character is: {character_description}

RULES:
- The character must be IDENTICAL across all platforms — same proportions, colors, outfit, pixel art style
- Only the facing direction changes between platforms
- The character's feet must rest on the platform surface
- Maintain the isometric 3/4 top-down perspective — the platform establishes the ground plane
- Style: {style}
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all character elements
- Maximum {max_colors} colors in the character palette
- Simple 2-3 tone stepped shading per color area
- {chromakey_color} ({hex_color}) background must remain around the character and platform
- Do NOT modify the platforms or labels — draw the character standing ON TOP of them"""


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
