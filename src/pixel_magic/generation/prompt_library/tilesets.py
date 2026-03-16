"""Tileset prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

# ── Ground tiles ──────────────────────────────────────────────────────

register(PromptTemplate(
    name="tileset_ground",
    description="Generate a set of isometric ground tiles in one composite image",
    system_context=(
        "You are a professional pixel art environment artist for retro isometric RPG games. "
        "Generate crisp, grid-aligned isometric tiles on a ${background_instruction}. "
        "NEVER use anti-aliasing, blur, or soft edges. All tiles must share a "
        "strictly limited, consistent color palette."
    ),
    template=(
        "Create a horizontal row of ${count} isometric ground tiles "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n"
        "Each tile is a diamond shape (isometric view, 2:1 width-to-height ratio).\n\n"
        "Biome: ${biome}\n"
        "Tile variants: ${tile_types}\n"
        "Tile size: ${tile_width}x${tile_height} pixels per tile\n"
        "Style: ${style}\n"
        "Maximum colors: STRICTLY ${max_colors} or fewer colors total\n\n"
        "CRITICAL RULES:\n"
        "- Arrange tiles in a single horizontal row, evenly spaced, in this order: ${tile_types}\n"
        "- Each tile is a flat isometric diamond shape (no 3D objects on top)\n"
        "- All tiles must tile seamlessly with each other at their edges\n"
        "- Consistent lighting direction (top-left light source)\n"
        "- ${background_rule} outside the diamond shapes\n"
        "- ZERO anti-aliasing: every pixel edge must be a hard step, no gradients, "
        "no blur, no soft blending between colors\n"
        "- STRICT palette: use EXACTLY ${max_colors} or fewer distinct colors across ALL tiles "
        "\u2014 count your colors carefully\n"
        "- Authentic retro 16-bit rendering: flat-shaded pixel surfaces, 1-pixel outlines\n"
        "- Tiles should have subtle texture variation using pixel-level detail (tiny dots, "
        "single-pixel highlights) to avoid looking flat"
        + FRAMING_RULES
    ),
    defaults={
        "biome": "temperate forest",
        "tile_types": "grass, dirt, stone",
        "tile_width": "64",
        "tile_height": "32",
        "count": "3",
        "style": "16-bit isometric RPG style",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))

# ── Object props ──────────────────────────────────────────────────────

register(PromptTemplate(
    name="tileset_objects",
    description="Generate isometric objects/props for a tileset",
    system_context=(
        "You are a professional pixel art environment artist for retro isometric games "
        "(SNES/Genesis era). Generate pixel-perfect isometric objects on a "
        "${background_instruction} with hard pixel edges and stepped shading."
    ),
    template=(
        "Create a horizontal row of ${count} isometric objects/props "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n\n"
        "Objects: ${tile_types}\n"
        "Biome context: ${biome}\n"
        "Base tile size: ${tile_width}x${tile_height} pixels\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors} total\n\n"
        "CRITICAL RULES:\n"
        "- Arrange objects in a single horizontal row, evenly spaced\n"
        "- Objects should sit naturally on an isometric ground plane\n"
        "- Consistent scale relative to the base tile size\n"
        "- ${background_rule}\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of ${max_colors} or fewer colors\n"
        "- Consistent lighting (top-left)"
        + FRAMING_RULES
    ),
    defaults={
        "biome": "temperate forest",
        "tile_types": "tree, bush, rock",
        "tile_width": "64",
        "tile_height": "32",
        "count": "3",
        "style": "16-bit isometric RPG style",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))

# ── Wall segments ─────────────────────────────────────────────────────

register(PromptTemplate(
    name="tileset_walls",
    description="Generate isometric wall/elevation tile variants",
    system_context=(
        "You are a professional pixel art environment artist for retro isometric games "
        "(SNES/Genesis era). Generate pixel-perfect isometric wall segments on a "
        "${background_instruction} with hard pixel edges and stepped shading."
    ),
    template=(
        "Create a horizontal row of ${count} isometric wall/elevation variants "
        "separated by 1px magenta (#FF00FF) vertical divider lines "
        "on a ${background_instruction}.\n\n"
        "Wall types: ${tile_types}\n"
        "Biome context: ${biome}\n"
        "Base tile size: ${tile_width}x${tile_height} pixels\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors} total\n\n"
        "CRITICAL RULES:\n"
        "- Arrange wall segments in a single horizontal row\n"
        "- Walls must connect seamlessly when placed adjacent in an isometric grid\n"
        "- Show the front face and top of the wall in isometric view\n"
        "- Consistent material, lighting (top-left), and scale\n"
        "- ${background_rule}\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of ${max_colors} or fewer colors"
        + FRAMING_RULES
    ),
    defaults={
        "biome": "stone castle",
        "tile_types": "wall_front, wall_corner, wall_end",
        "tile_width": "64",
        "tile_height": "32",
        "count": "3",
        "style": "16-bit isometric RPG style",
        "max_colors": "16",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
    },
    reference_strategy="none",
))
