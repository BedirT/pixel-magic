"""Item sprite prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompts import PromptTemplate

# ── Inventory icons ───────────────────────────────────────────────────────

register(PromptTemplate(
    name="item_icons_batch",
    description="Generate a batch of item icons in a single composite image",
    system_context=(
        "You are a professional pixel art item designer for retro RPG games "
        "(SNES/Genesis era). Generate pixel-perfect item icons on transparent "
        "background with hard pixel edges and stepped shading. Every icon must "
        "be instantly recognizable at small sizes."
    ),
    template=(
        "Create a horizontal row of ${count} pixel art item icons on a transparent background.\n\n"
        "Items (left to right): ${item_descriptions}\n"
        "Resolution per icon: ${resolution}\n"
        "View: ${view}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors} total across all items\n\n"
        "CRITICAL RULES:\n"
        "- Arrange items in a single horizontal row, evenly spaced, in the listed order\n"
        "- Each icon should fill most of its frame (minimal padding)\n"
        "- Items must be clearly distinct and recognizable at ${resolution}\n"
        "- Consistent style, scale, and lighting across all icons\n"
        "- Background MUST be fully transparent\n"
        "- Pixel-perfect rendering: every edge is a hard pixel step with stepped shading, "
        "no anti-aliasing, no gradients, no blur\n"
        "- Bold outlines (1-2px dark border) for readability at small sizes\n"
        "- Unified palette of exactly ${max_colors} or fewer colors — reuse colors "
        "across all items for visual cohesion"
    ),
    defaults={
        "item_descriptions": "iron sword, health potion, wooden shield",
        "count": "3",
        "resolution": "32x32",
        "view": "front-facing icon",
        "style": "16-bit SNES RPG style",
        "max_colors": "16",
    },
    reference_strategy="none",
))

# ── World-drop sprites ────────────────────────────────────────────────────

register(PromptTemplate(
    name="item_world_sprites",
    description="Generate item sprites as they appear dropped in the game world",
    system_context=(
        "You are a professional pixel art item designer for retro isometric RPG games "
        "(SNES/Genesis era). Generate pixel-perfect world-drop sprites on transparent "
        "background with hard pixel edges."
    ),
    template=(
        "Create a horizontal row of ${count} pixel art world-drop item sprites "
        "on a transparent background.\n"
        "These are how items look when lying on the ground in an isometric game world.\n\n"
        "Items (left to right): ${item_descriptions}\n"
        "Resolution per sprite: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors} total\n\n"
        "CRITICAL RULES:\n"
        "- Arrange in a single horizontal row\n"
        "- Isometric perspective (items lying on the ground, viewed from above at ~30°)\n"
        "- Smaller and less detailed than inventory icons — focus on silhouette readability\n"
        "- Add a subtle drop shadow or glow to help visibility on varied ground tiles\n"
        "- Background MUST be fully transparent\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of ${max_colors} or fewer colors"
    ),
    defaults={
        "item_descriptions": "iron sword, health potion, gold coin",
        "count": "3",
        "resolution": "24x24",
        "style": "16-bit isometric RPG style",
        "max_colors": "12",
    },
    reference_strategy="none",
))
