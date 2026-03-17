"""Custom freeform generation prompt template."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

register(PromptTemplate(
    name="custom_generation",
    description="Generate pixel art from a freeform custom prompt",
    system_context=(
        "You are a professional pixel art sprite artist for retro-style video games "
        "(SNES/Genesis era). Generate pixel-perfect sprites on a "
        "${background_instruction} with hard pixel edges and stepped shading. "
        "Every pixel must be a single flat color — use a unified, carefully "
        "chosen palette throughout."
    ),
    template=(
        "${description}\n\n"
        "Resolution: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors}\n\n"
        "${perspective_rules}"
        "CRITICAL RULES:\n"
        "- ${background_rule} (no floor, no shadow, no background elements)\n"
        "- Pixel-perfect rendering: every edge is a hard pixel step with stepped "
        "shading, no anti-aliasing, no gradients, no blur\n"
        "- Unified palette of exactly ${max_colors} or fewer distinct colors\n"
        "- Every pixel must be one solid flat color"
        + FRAMING_RULES
    ),
    defaults={
        "description": "A pixel art sprite",
        "resolution": "64x64",
        "style": "16-bit pixel art",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
        "perspective_rules": "",
    },
    reference_strategy="none",
))
