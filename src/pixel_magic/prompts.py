"""Prompt builders for character/object sprite sheets and animation frames."""

from __future__ import annotations

import json
from typing import Any


_CHROMAKEY_HEX = {"green": "#00FF00", "blue": "#0000FF", "pink": "#FF00FF"}

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


# ---------------------------------------------------------------------------
# Canvas-based object animation prompt
# ---------------------------------------------------------------------------

_OBJECT_ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "sway": "a gentle swaying animation — the object rocks side to side as if blown by wind. Subtle, rhythmic motion. The base stays planted.",
    "flicker": "a flickering animation — the flame or light source pulses and shifts shape between frames. Organic, jittery movement.",
    "burn": "a burning animation — flames dance and smoke wisps rise. The fire shape changes each frame while the base stays grounded.",
    "pulse": "a pulsing/glowing animation — the object brightens and dims rhythmically. Subtle scale or luminosity shifts.",
    "open": "an opening animation — the object's lid, door, or cover swings open revealing the interior.",
    "bob": "a bobbing animation — the object gently floats up and down in place. Smooth, continuous vertical motion.",
    "spin": "a rotating animation — the object turns in place, showing different facets each frame.",
}


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
    """Build a prompt for object animation sprite sheet generation.

    Same canvas approach as character animation: slot 1 has the reference,
    remaining slots filled with chromakey for Gemini to complete.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    anim_desc = _OBJECT_ANIMATION_DESCRIPTIONS.get(
        animation_type,
        _ANIMATION_DESCRIPTIONS.get(animation_type, f"a {animation_type} animation."),
    )

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    object_line = ""
    if object_description:
        object_line = f"\nThe object is {object_description}."

    if loop:
        middle_count = total_frames - 2
        loop_desc = f"The FIRST and LAST slots both show the same object — this is a LOOPING animation. Fill in the {middle_count} middle slots (slots 2–{total_frames - 1}) with animation frames that smoothly transition from the first pose, through the full motion, and back to the same pose."
        anchor_rule = f"- Do NOT modify the first or last slot — they are identical anchor frames for the loop\n- The animation must smoothly cycle: frame {total_frames} flows back into frame 1"
    else:
        loop_desc = f"The FIRST slot contains the starting state. Fill in the remaining {total_frames - 1} slots with animation frames."
        anchor_rule = "- Do NOT modify the first slot — it is the reference frame, leave it exactly as-is"

    if platform:
        if tiles == 1:
            floor_desc = "an isometric stone platform"
        elif tiles == 4:
            floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
        else:
            floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"

        if loop:
            slot_desc = f"The FIRST and LAST slots show a pixel art object sitting on {floor_desc}. The {middle_count} middle slots each have the same floor but NO object."
        else:
            slot_desc = f"The FIRST slot shows a pixel art object sitting on {floor_desc}. The remaining {total_frames - 1} slots each have the same floor but NO object."

        return f"""\
This image is a sprite sheet with {layout_desc}, on a {chromakey_color} ({hex_color}) background. {slot_desc}

{loop_desc} Show {anim_desc}
{object_line}

RULES:
- Draw the SAME object on each platform — identical base shape, colors, proportions, pixel art style
- Each filled slot must show a DIFFERENT state progressing through the animation
{anchor_rule}
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
- Do NOT modify the stone platforms — draw the object sitting ON TOP of them
- The object's base must rest on the platform surface in every frame
- Maintain the isometric 3/4 top-down perspective — the platform establishes the ground plane
- Style: {style}
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all object elements
- Same color palette across all frames
- {chromakey_color} ({hex_color}) background must remain around the object and platform"""

    return f"""\
This image is a sprite sheet with {layout_desc}. {loop_desc}
{object_line}

Show {anim_desc}

RULES:
- Draw the SAME object in each slot — identical base shape, colors, proportions, pixel art style
- Each filled slot must show a DIFFERENT state progressing through the animation
{anchor_rule}
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
- Only draw inside the {chromakey_color} areas
- Keep the {chromakey_color} ({hex_color}) background within each frame slot
- Style: {style}, isometric 3/4 top-down view
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all object elements
- Same color palette across all frames"""


# ---------------------------------------------------------------------------
# Effect animation prompts (subjectless VFX)
# ---------------------------------------------------------------------------

_EFFECT_ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "explosion": "an explosion — starts as a bright flash, expands outward with fire and debris, then dissipates into smoke and embers.",
    "slash": "a slash effect — a sharp arc of energy sweeps across the frame, trailing light, then fades away.",
    "shield_hit": "a shield impact — concentric rings of energy pulse outward from a central hit point, then fade.",
    "magic_circle": "a rotating magic circle — glowing runes and geometric patterns spin and pulse with arcane energy.",
    "healing_aura": "a healing aura — gentle green/white particles rise upward, glowing warmly, in a cyclical pattern.",
    "energy_ball": "an energy ball — a sphere of crackling energy pulses, sparks, and shifts shape between frames.",
    "smoke": "a smoke puff — a cloud billows outward from the center, expanding and thinning as it dissipates.",
    "fire": "a fire animation — flames dance and flicker, changing shape organically each frame while maintaining the same base position.",
    "water_splash": "a water splash — droplets erupt upward and arc outward in all directions, then settle.",
    "poison_cloud": "a poison cloud — sickly green gas swirls and undulates in place with subtle drifting particles.",
    "stun_stars": "stun stars — small stars orbit in a circle above, twinkling and spinning rhythmically.",
    "buff_glow": "a buff glow — a radiant aura pulses outward rhythmically, with rising energy particles.",
}


def build_effect_reference_prompt(
    effect_name: str,
    description: str = "",
    style: str = "16-bit SNES RPG style",
    max_colors: int = 16,
    chromakey_color: str = "pink",
) -> str:
    """Build a text-to-image prompt for generating a single effect reference frame."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")

    # Use the animation description to infer the "peak moment"
    anim_desc = _EFFECT_ANIMATION_DESCRIPTIONS.get(effect_name, "")
    effect_desc = description or effect_name.replace("_", " ")

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "front-facing 2D",
        "purpose": "vfx_effect_reference_frame",
        "background": {
            "type": "chromakey",
            "rule": _background_rule(chromakey_color),
            "instruction": _background_instruction(chromakey_color),
        },
        "effect": {
            "name": effect_name,
            "description": f"A pixel art {effect_desc} effect",
            "moment": f"Show the effect at its peak/most recognizable state — the single most iconic frame of {effect_desc}",
        },
        "art_details": {
            "pixel_density": "medium",
            "shading": "simple 2-3 tone stepped shading per color area",
            "outline": (
                "Every element MUST have a 1-pixel black (#000000) outline — "
                "all particles, energy shapes, and distinct visual parts must be "
                "enclosed by a black pixel border with no gaps"
            ),
            "anti_aliasing": "none — every edge is a hard pixel step",
            "max_colors": max_colors,
            "style_reference": style,
        },
        "layout": {
            "arrangement": f"single centered sprite on solid {chromakey_color} ({hex_color}) background",
            "no_grid": "do NOT draw a grid, platform, or multiple sprites — just one centered effect",
        },
    }

    return json.dumps(prompt, indent=2)


def build_effect_animation_prompt(
    animation_type: str,
    total_frames: int,
    effect_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "pink",
    loop: bool = True,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for effect animation sprite sheet generation.

    Same canvas approach as character/object animation: slot 1 has the reference,
    remaining slots filled with chromakey for Gemini to complete.
    No platforms — effects are floating VFX overlays.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    anim_desc = _EFFECT_ANIMATION_DESCRIPTIONS.get(
        animation_type, f"a {animation_type} animation.",
    )

    if grid_cols and grid_rows:
        layout_desc = f"{total_frames} numbered frame slots arranged in a {grid_cols}x{grid_rows} grid (read left-to-right, top-to-bottom)"
    else:
        layout_desc = f"{total_frames} frame slots in a horizontal row"

    effect_line = ""
    if effect_description:
        effect_line = f"\nThe effect is {effect_description}."

    if loop:
        middle_count = total_frames - 2
        loop_desc = f"The FIRST and LAST slots both show the same effect state — this is a LOOPING animation. Fill in the {middle_count} middle slots (slots 2–{total_frames - 1}) with animation frames that smoothly transition from the first state, through the full motion, and back to the same state."
        anchor_rule = f"- Do NOT modify the first or last slot — they are identical anchor frames for the loop\n- The animation must smoothly cycle: frame {total_frames} flows back into frame 1"
    else:
        loop_desc = f"The FIRST slot contains the starting state. Fill in the remaining {total_frames - 1} slots with animation frames that progress the effect to completion."
        anchor_rule = "- Do NOT modify the first slot — it is the reference frame, leave it exactly as-is"

    return f"""\
This image is a sprite sheet with {layout_desc}. {loop_desc}
{effect_line}

Show {anim_desc}

RULES:
- Maintain consistent color palette and art style across all frames
- Each filled slot must show a DIFFERENT state progressing through the animation
{anchor_rule}
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
- Only draw inside the {chromakey_color} areas
- Keep the {chromakey_color} ({hex_color}) background within each frame slot
- The effect should be centered in each frame
- Style: {style}, front-facing 2D view (not isometric — this is a VFX overlay)
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all effect elements (particles, energy shapes, flames, etc.)
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
                f"The attached image shows exactly {len(tile_labels)} labeled isometric diamond outlines"
                f"{layout_desc} on {chromakey_color} ({hex_color}) background"
            ),
            "usage": (
                "Each diamond outline shows exactly where to draw the terrain tile. "
                "Fill each diamond with the terrain texture labeled above it. "
                "Do not invent extra tiles. Any unlabeled or outline-free area must remain solid "
                f"{chromakey_color} ({hex_color}) background."
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
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" in a {grid_cols}x{grid_rows} grid"

    objects_desc = [
        {"slot": i + 1, "label": label}
        for i, label in enumerate(object_labels)
    ]

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "world_object_props",
        "reference_image": {
            "description": (
                f"The attached image shows exactly {len(object_labels)} labeled "
                f"isometric stone platforms{layout_desc} "
                f"on {chromakey_color} ({hex_color}) background"
            ),
            "usage": (
                "Each platform shows where to draw the labeled object. "
                "Draw one object per platform, standing or sitting on the platform surface. "
                "Do not invent extra objects. Any unlabeled area must remain solid "
                f"{chromakey_color} ({hex_color}) background."
            ),
        },
        "background": {
            "type": "chromakey",
            "rule": _background_rule(chromakey_color),
            "instruction": _background_instruction(chromakey_color),
        },
        "objects": objects_desc,
        "variant_rule": (
            "Each object must be visually DISTINCT — different shapes, silhouettes, "
            "proportions, and surface details. Do NOT draw the same object twice with "
            "minor color changes. Make each one immediately distinguishable at a glance."
        ),
        "placement": {
            "grounding": (
                "Each object MUST stand or sit directly ON the platform surface — "
                "firmly touching, not floating above"
            ),
            "centering": "Center each object horizontally on its platform",
            "size": (
                "Objects should be proportional to the platform — tall objects "
                "(trees) can extend well above, short objects (rocks, chests) stay compact"
            ),
        },
        "art_details": {
            "pixel_density": "medium",
            "shading": "simple 2-3 tone stepped shading per color area",
            "outline": (
                "Every element MUST have a 1-pixel black (#000000) outline — "
                "the object and all distinct parts must be fully enclosed by "
                "a black pixel border with no gaps"
            ),
            "anti_aliasing": "none — every edge is a hard pixel step",
            "perspective": "isometric 3/4 top-down (~30 degrees from above)",
            "max_colors": max_colors,
            "style_reference": style,
            "lighting": "consistent upper-left light source across all objects",
        },
    }

    if description:
        prompt["theme"] = description

    return json.dumps(prompt, indent=2)


def build_object_cleanup_prompt(
    object_count: int,
    chromakey_color: str = "pink",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing platforms and labels from generated objects."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#FF00FF")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"

    return f"""\
This is a pixel art sheet with {object_count} isometric world objects {layout_desc} on stone platforms. Each platform has a text label above it.

Remove the stone platforms AND the text labels from EVERY object. Replace all platform and label pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the objects EXACTLY as they are — same shapes, colors, shading, pixel art style
- Do NOT modify any object pixels — only remove the stone platforms and text labels
- Fill where the platforms and labels were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} layout"""
