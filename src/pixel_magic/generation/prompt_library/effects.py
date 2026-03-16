"""Effect animation prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

register(PromptTemplate(
    name="effect_animation",
    description="Generate all frames of an animated visual effect in a horizontal strip",
    system_context=(
        "You are a professional pixel art VFX artist for retro-style video games "
        "(SNES/Genesis era). Generate crisp, vibrant effect animations on a "
        "${background_instruction} with hard pixel edges and stepped shading. Effects should read well "
        "at small sizes and feel dynamic."
    ),
    template=(
        "Create a horizontal strip of exactly ${frame_count} animation frames "
        "separated by 1px magenta (#FF00FF) vertical divider lines, "
        "for a pixel art visual effect: ${effect_description}\n\n"
        "Frame count: exactly ${frame_count} frames\n"
        "Resolution per frame: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors}\n"
        "Color emphasis: ${color_emphasis}\n\n"
        "CRITICAL RULES:\n"
        "- Produce exactly ${frame_count} distinct frames, each showing a "
        "different phase of the effect lifecycle\n"
        "- Arrange ALL ${frame_count} frames in a single horizontal row, left to right, in animation order\n"
        "- Frame 1: effect begins / appears\n"
        "- Middle frames: effect at full intensity\n"
        "- Final frame (frame ${frame_count}): effect dissipating / fading\n"
        "- ${background_rule} (the effect floats in space)\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of exactly ${max_colors} or fewer colors\n"
        "- Each frame should be the same size\n"
        "- Use the emphasized colors prominently: ${color_emphasis}\n"
        "- Add subtle pixel particles or energy wisps for dynamism"
        + FRAMING_RULES
    ),
    defaults={
        "effect_description": "magical spell explosion",
        "frame_count": "6",
        "resolution": "64x64",
        "style": "16-bit pixel art",
        "max_colors": "12",
        "color_emphasis": "",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))
