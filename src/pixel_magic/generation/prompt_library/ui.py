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
        "- A reference image is attached showing the exact grid layout with magenta dividers. "
        "Match this layout precisely — place each element within the cells shown.\n"
        "- Each element must be a COMPLETE standalone component centered in its cell — never crop or clip it against any cell edge.\n"
        "- The main functional shape should occupy roughly 70-85% of the cell, with only a small transparent margin around it.\n"
        "- Arrange all elements in a single horizontal row, evenly spaced\n"
        "- Each element should be clearly distinct and functional-looking\n"
        "- Use consistent border/frame style across all elements\n"
        "- Rounded or beveled edges in pixel art style (1-2px borders)\n"
        "- Match each description literally: bars need a large visible fill channel, orb frames need a large centered orb/socket, and slots need a large recessed cavity.\n"
        "- Use bold enough borders, highlights, and interior details that the UI still reads after nearest-neighbor scaling.\n"
        "- Fill empty space with intentional panel detail (inner bevels, corner caps, bolts, glyphs) instead of leaving large blank areas.\n"
        "- Any divider or guide marks visible in the reference image are layout guides only and must NOT appear in the final UI.\n"
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
        "resolution": "160x128",
        "style": "16-bit RPG UI style",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))

register(PromptTemplate(
    name="ui_single",
    description="Generate one standalone pixel art UI element",
    system_context=(
        "You are a professional pixel art UI designer for retro RPG games "
        "(SNES/Genesis era). Generate one pixel-perfect, functional UI element on a "
        "${background_instruction} with hard pixel edges and stepped shading."
    ),
    template=(
        "Create ONE standalone pixel art UI element.\n\n"
        "Element description: ${element_description}\n"
        "Resolution: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors}\n\n"
        "CRITICAL RULES:\n"
        "- Draw exactly ONE complete UI element centered in the canvas — no strips, no divider lines, no extra panels\n"
        "- Match the description literally: bars need a large visible fill channel, orb frames need a large centered orb/socket, and slots need a large recessed cavity\n"
        "- If the description is a bar, give it substantial endcaps, housing, or a label plate so the overall widget uses the canvas instead of collapsing into a thin strip\n"
        "- The main functional shape should occupy roughly 70-85% of the canvas, with a small transparent margin around it\n"
        "- Use bold readable borders, highlights, and interior details that still read after nearest-neighbor scaling\n"
        "- Fill empty space with intentional panel detail (inner bevels, corner caps, bolts, glyphs) instead of leaving large blank areas\n"
        "- ${background_rule}\n"
        "- Pixel-perfect rendering: every edge is a hard pixel step with stepped shading, no anti-aliasing, no gradients, no blur\n"
        "- Unified palette of exactly ${max_colors} or fewer colors\n"
        "- The element must look immediately usable and readable in a game HUD"
    ),
    defaults={
        "element_description": "health bar frame",
        "resolution": "160x128",
        "style": "16-bit RPG UI style",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))
