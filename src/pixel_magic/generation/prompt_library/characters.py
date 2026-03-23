"""Character sprite prompt templates."""

from __future__ import annotations

import json
from typing import Any

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate


# ── JSON-structured multi-view prompt builder ─────────────────────────


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

def build_character_sheet_prompt(
    character_description: str,
    direction_mode: int = 4,
    style: str = "16-bit SNES RPG style",
    resolution: str = "64x64",
    max_colors: int = 16,
    palette_hint: str = "",
    provider: str = "openai",
    chromakey_color: str = "green",
) -> str:
    """Build a JSON-structured prompt for multi-view character reference sheet.

    Returns the prompt as a JSON string. Both GPT Image and Gemini respond
    well to this structured format for producing consistent multi-view sheets.
    """
    from pixel_magic.generation.prompt_library._shared import (
        background_instruction as _bg_instruction,
        background_rule as _bg_rule,
    )

    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "character_sprite_reference_sheet",
        "background": {
            "type": "transparent",
            "rule": _bg_rule(provider, chromakey_color),
            "instruction": _bg_instruction(provider, chromakey_color),
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
            "outline": "integrated (no separate outline color, edges defined by color contrast)",
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


# ── Shared constants ──────────────────────────────────────────────────

_PIXEL_ART_SYSTEM = (
    "You are a professional pixel art sprite artist specializing in ISOMETRIC "
    "retro 16-bit game assets (SNES/Genesis era, like Final Fantasy Tactics, "
    "Tactics Ogre, or Chrono Trigger overworld). "
    "ALL sprites MUST be drawn in isometric 3/4 top-down perspective — the "
    "camera looks down at roughly 30° from above, so the viewer sees the top "
    "of the character's head/shoulders and the ground plane forms a diamond grid "
    "(2:1 width-to-height ratio). "
    "Generate pixel-perfect sprites on a ${background_instruction} with hard "
    "pixel edges and stepped shading. "
    "Each sprite must be clearly separated. Every pixel must be a single flat "
    "color — use a unified, carefully chosen palette throughout."
)

_ANIMATION_SYSTEM = (
    "You are a professional pixel art animation specialist for ISOMETRIC retro "
    "16-bit video games (like Final Fantasy Tactics, Tactics Ogre). "
    "ALL sprites MUST be drawn in isometric 3/4 top-down perspective — the "
    "camera looks down at roughly 30° from above. "
    "Generate pixel-perfect animation frames on a ${background_instruction} "
    "with hard pixel edges and stepped shading. All frames must depict the exact "
    "same character with identical proportions, palette, and design."
)

_REFERENCE_SYSTEM = (
    "You are a professional pixel art animation specialist. You will receive a "
    "reference image of a character drawn in ISOMETRIC 3/4 top-down perspective. "
    "Generate new animation frames that match the reference character exactly — "
    "same palette, proportions, isometric perspective, and pixel-perfect style "
    "with hard edges and stepped shading."
)

_ISOMETRIC_RULES = (
    "PERSPECTIVE — MANDATORY (isometric 3/4 top-down view):\n"
    "- The camera is positioned ABOVE and in front of the character, looking "
    "down at ~30°. The viewer can see the TOP of the character's head and shoulders.\n"
    "- Characters appear slightly foreshortened vertically — they are NOT "
    "drawn as flat front-facing portraits. Imagine the character standing on a "
    "diamond-shaped floor tile.\n"
    "- The ground plane is an isometric diamond grid (2:1 width-to-height ratio). "
    "Each character's feet touch this imaginary diamond tile.\n"
    "- Think of classic SNES RPG sprites: Final Fantasy VI, Chrono Trigger "
    "overworld, Tactics Ogre — that exact camera angle.\n\n"
    "DIRECTIONS (all in isometric perspective, camera looking down):\n"
    "- SE (south_east) = character's body angled toward the BOTTOM-RIGHT of "
    "the screen. This is the classic 'front-facing' isometric view — you see "
    "the character's face and chest from a 3/4 top-down angle.\n"
    "- NE (north_east) = character's body angled toward the TOP-RIGHT of the "
    "screen. This is the 'back' view — you see the character's back and the "
    "top of their head.\n"
    "- S (south) = character angled toward the BOTTOM of the screen (front "
    "view, centered).\n"
    "- E (east) = character angled toward the RIGHT of the screen (side view "
    "from above).\n"
    "- N (north) = character angled toward the TOP of the screen (full back "
    "view from above).\n\n"
    "STYLE RULES:\n"
    "- ${background_rule} (no floor, no shadow, no background elements)\n"
    "- Pixel-perfect rendering: every edge is a hard pixel step with stepped shading, "
    "no anti-aliasing, no gradients, no blur\n"
    "- Unified palette of exactly ${max_colors} or fewer distinct colors across ALL sprites "
    "\u2014 choose colors deliberately and reuse them for cohesion\n"
    "- Every pixel must be one solid flat color"
)

# ── Single-direction character (one sprite per image) ─────────────────

register(PromptTemplate(
    name="character_single_direction",
    description="Generate one character sprite in one isometric direction",
    system_context=_PIXEL_ART_SYSTEM,
    template=(
        "Create a single ISOMETRIC pixel art character sprite (3/4 top-down camera "
        "angle, like Final Fantasy Tactics or Chrono Trigger) on a ${background_instruction}.\n\n"
        "Character: ${character_description}\n"
        "Direction: The character is facing ${direction} (${direction_description})\n"
        "Style: ${style}\n"
        "Target resolution: ${resolution}\n"
        "Maximum colors: ${max_colors}\n"
        "${palette_hint}\n\n"
        "RULES:\n"
        "- Draw exactly ONE character sprite, centered in the image\n"
        "- The character is in a standing idle pose facing the ${direction} direction\n"
        "- If a reference image is provided, match the character's appearance EXACTLY "
        "(same proportions, palette, design) \u2014 only change the facing direction\n"
        "- Do NOT draw multiple sprites, frames, strips, dividers, or decorations\n"
        + _ISOMETRIC_RULES
    ),
    defaults={
        "direction": "south_east",
        "direction_description": "body angled toward bottom-right of screen, classic front-facing isometric view",
        "style": "16-bit SNES RPG style",
        "resolution": "64x64",
        "max_colors": "16",
        "palette_hint": "",
        "background_instruction": "fully transparent background",
        "background_rule": "The ENTIRE image background MUST be fully transparent (alpha=0)",
    },
    reference_strategy="none",
))

# ── 4-Direction base ──────────────────────────────────────────────────

register(PromptTemplate(
    name="character_directions_4dir",
    description="Generate 2 unique directions (SE, NE) of a character in one composite image",
    system_context=_PIXEL_ART_SYSTEM,
    template=(
        "Create a horizontal strip of ${direction_count} ISOMETRIC pixel art character "
        "sprites (3/4 top-down camera angle, like Final Fantasy Tactics or Chrono Trigger) "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n"
        "Each sprite is the SAME character facing a different direction: ${direction_names}.\n\n"
        "Character: ${character_description}\n"
        "Style: ${style}\n"
        "Target resolution per sprite: ${resolution}\n"
        "Maximum colors: ${max_colors}\n"
        "${palette_hint}\n\n"
        "CRITICAL RULES:\n"
        "- Arrange sprites in a single horizontal row, evenly spaced, left to right "
        "in this order: ${direction_names}\n"
        "- Every sprite must be the exact same character with the same proportions, colors, and design\n"
        "- Each sprite should be a standing idle pose facing the specified direction\n"
        + _ISOMETRIC_RULES
        + FRAMING_RULES
    ),
    defaults={
        "direction_count": "2",
        "direction_names": "south_east, north_east",
        "style": "16-bit SNES RPG style",
        "resolution": "64x64",
        "max_colors": "16",
        "palette_hint": "",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))

# ── 8-Direction base ──────────────────────────────────────────────────

register(PromptTemplate(
    name="character_directions_8dir",
    description="Generate 5 unique directions (S, SE, E, NE, N) of a character in one composite image",
    system_context=_PIXEL_ART_SYSTEM,
    template=(
        "Create a horizontal strip of ${direction_count} ISOMETRIC pixel art character "
        "sprites (3/4 top-down camera angle, like Final Fantasy Tactics or Chrono Trigger) "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n"
        "Each sprite is the SAME character facing a different direction: ${direction_names}.\n\n"
        "Character: ${character_description}\n"
        "Style: ${style}\n"
        "Target resolution per sprite: ${resolution}\n"
        "Maximum colors: ${max_colors}\n"
        "${palette_hint}\n\n"
        "CRITICAL RULES:\n"
        "- Arrange sprites in a single horizontal row, evenly spaced, left to right "
        "in this order: ${direction_names}\n"
        "- Every sprite must be the exact same character with the same proportions, colors, and design\n"
        "- Each sprite should be a standing idle pose facing the specified direction\n"
        + _ISOMETRIC_RULES
        + FRAMING_RULES
    ),
    defaults={
        "direction_count": "5",
        "direction_names": "south, south_east, east, north_east, north",
        "style": "16-bit SNES RPG style",
        "resolution": "64x64",
        "max_colors": "16",
        "palette_hint": "",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))

# ── Animation strip (with reference) ─────────────────────────────────

register(PromptTemplate(
    name="character_animation",
    description="Generate all frames of one animation in one direction as a horizontal strip",
    system_context=_ANIMATION_SYSTEM,
    template=(
        "Create a horizontal strip of exactly ${frame_count} ISOMETRIC animation frames "
        "(3/4 top-down camera angle) separated by 1px magenta (#FF00FF) vertical divider "
        "lines, showing a pixel art character performing: ${animation_name}.\n\n"
        "Character: ${character_description}\n"
        "Direction: The character is facing ${direction} (in isometric 3/4 top-down view)\n"
        "Animation: ${animation_description}\n"
        "Frame count: exactly ${frame_count} frames\n"
        "Style: ${style}\n"
        "Target resolution per frame: ${resolution}\n"
        "Maximum colors: ${max_colors}\n"
        "${palette_hint}\n\n"
        "CRITICAL RULES:\n"
        "- Produce exactly ${frame_count} distinct frames, each showing a different "
        "phase of the animation\n"
        "- Arrange ALL ${frame_count} frames in a single horizontal row, left to right, "
        "in animation order\n"
        "- The character must look IDENTICAL across all frames (same proportions, same colors, same face)\n"
        "- Only the animated parts should change between frames (limbs, effects)\n"
        "- Use isometric 3/4 top-down perspective matching the ${direction} direction — "
        "camera looks down from above at ~30°, you can see the top of the character's head\n"
        "- ${background_rule} (no floor, no shadow)\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of ${max_colors} or fewer colors\n"
        "- Show smooth progression of the ${animation_name} motion from start to end\n"
        "- Frame 1 and frame ${frame_count} should transition smoothly if this is a looping animation"
        + FRAMING_RULES
    ),
    defaults={
        "animation_name": "idle",
        "animation_description": "breathing idle stance",
        "frame_count": "4",
        "direction": "south",
        "style": "16-bit SNES RPG style",
        "resolution": "64x64",
        "max_colors": "16",
        "palette_hint": "",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="character_reference",
))

# ── Custom animation (from reference image) ──────────────────────────

register(PromptTemplate(
    name="character_custom_animation",
    description="Add a custom animation to an existing character using a reference image",
    system_context=_REFERENCE_SYSTEM,
    template=(
        "Using the provided reference image of the character, create a horizontal strip "
        "of ${frame_count} animation frames separated by 1px magenta (#FF00FF) vertical divider lines, "
        "showing: ${animation_name} — ${animation_description}.\n\n"
        "The character faces ${direction}.\n"
        "Frame count: ${frame_count} frames total\n"
        "Style: ${style}\n"
        "Target resolution per frame: ${resolution}\n"
        "Maximum colors: ${max_colors}\n\n"
        "CRITICAL RULES:\n"
        "- The character in the animation MUST match the reference image exactly "
        "(same proportions, colors, features)\n"
        "- Arrange frames in a single horizontal row, left to right, in animation order\n"
        "- Only the animated body parts should change between frames\n"
        "- ${background_rule}\n"
        "- Clean pixel art: no anti-aliasing, crisp pixel edges\n"
        "- Show smooth motion progression for the ${animation_name} action"
        + FRAMING_RULES
    ),
    defaults={
        "animation_name": "custom",
        "animation_description": "custom animation",
        "frame_count": "4",
        "direction": "south",
        "style": "16-bit SNES RPG style",
        "resolution": "64x64",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="character_reference",
))
