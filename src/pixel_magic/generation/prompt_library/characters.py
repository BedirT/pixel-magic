"""Character sprite prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

# ── Shared constants ──────────────────────────────────────────────────

_PIXEL_ART_SYSTEM = (
    "You are a professional pixel art sprite artist specializing in retro 16-bit "
    "game assets (SNES/Genesis era). Generate pixel-perfect sprites on a "
    "${background_instruction} with hard pixel edges and stepped shading. "
    "Each sprite must be clearly separated. Every pixel must be a single flat "
    "color — use a unified, carefully chosen palette throughout."
)

_ANIMATION_SYSTEM = (
    "You are a professional pixel art animation specialist for retro 16-bit "
    "video games. Generate pixel-perfect animation frames on a "
    "${background_instruction} with hard pixel edges and stepped shading. All frames must "
    "depict the exact same character with identical proportions, palette, and design."
)

_REFERENCE_SYSTEM = (
    "You are a professional pixel art animation specialist. You will receive a "
    "reference image of a character. Generate new animation frames that match the "
    "reference character exactly — same palette, proportions, and pixel-perfect style "
    "with hard edges and stepped shading."
)

_ISOMETRIC_RULES = (
    "- Use isometric perspective (2:1 ratio diamond grid, ~30° viewing angle from above)\n"
    "- SE (south_east) = character facing front-right toward the camera "
    "(classic isometric front view)\n"
    "- NE (north_east) = character facing back-right away from camera (back view)\n"
    "- S (south) = character facing directly toward the camera\n"
    "- E (east) = character facing right (side view)\n"
    "- N (north) = character facing directly away from camera\n"
    "- ${background_rule} (no floor, no shadow, no background elements)\n"
    "- Pixel-perfect rendering: every edge is a hard pixel step with stepped shading, "
    "no anti-aliasing, no gradients, no blur\n"
    "- Unified palette of exactly ${max_colors} or fewer distinct colors across ALL sprites "
    "\u2014 choose colors deliberately and reuse them for cohesion\n"
    "- Every pixel must be one solid flat color"
)

# ── 4-Direction base ──────────────────────────────────────────────────

register(PromptTemplate(
    name="character_directions_4dir",
    description="Generate 2 unique directions (SE, NE) of a character in one composite image",
    system_context=_PIXEL_ART_SYSTEM,
    template=(
        "Create a horizontal strip of ${direction_count} pixel art character sprites "
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
        "Create a horizontal strip of ${direction_count} pixel art character sprites "
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
        "Create a horizontal strip of exactly ${frame_count} animation frames "
        "separated by 1px magenta (#FF00FF) vertical divider lines, "
        "showing a pixel art character performing: ${animation_name}.\n\n"
        "Character: ${character_description}\n"
        "Direction: The character is facing ${direction}\n"
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
        "- Use isometric perspective matching the ${direction} direction\n"
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
