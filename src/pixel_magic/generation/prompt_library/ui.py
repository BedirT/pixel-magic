"""UI element prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

register(PromptTemplate(
    name="ui_elements_batch",
    description="Generate multiple UI elements in a single composite image",
    system_context=(
        "You are a professional pixel art UI designer for retro RPG games "
        "(SNES/Genesis era). Generate pixel-perfect, functional UI elements on a "
        "${background_instruction} with hard pixel edges and stepped shading. "
        "UI must be readable and match an authentic 16-bit pixel art aesthetic."
    ),
    template=(
        "Create a horizontal row of ${count} pixel art UI elements "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n\n"
        "Elements (left to right): ${element_descriptions}\n"
        "Resolution per element: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors} total\n\n"
        "CRITICAL RULES:\n"
        "- Arrange all elements in a single horizontal row, evenly spaced\n"
        "- Each element should be clearly distinct and functional-looking\n"
        "- Use consistent border/frame style across all elements\n"
        "- Rounded or beveled edges in pixel art style (1-2px borders)\n"
        "- ${background_rule}\n"
        "- Pixel-perfect rendering: every edge is a hard pixel step with stepped shading, "
        "no anti-aliasing, no gradients, no blur\n"
        "- Unified palette of exactly ${max_colors} or fewer colors — share the same "
        "palette across all elements for visual cohesion\n"
        "- Text areas should be clearly defined (but don't render actual text)\n"
        "- Elements should look like they belong in the same game UI"
        + FRAMING_RULES
    ),
    defaults={
        "element_descriptions": "health bar frame, mana bar frame, inventory slot",
        "count": "3",
        "resolution": "64x64",
        "style": "16-bit RPG UI style",
        "max_colors": "8",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))
