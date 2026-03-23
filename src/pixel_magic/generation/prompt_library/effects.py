"""Effect animation prompt templates."""

from pixel_magic.generation.prompt_library import register
from pixel_magic.generation.prompt_library._shared import FRAMING_RULES
from pixel_magic.generation.prompts import PromptTemplate

register(PromptTemplate(
    name="effect_animation",
    description="Generate all frames of an animated visual effect in a horizontal strip",
    system_context=(
        "You are a professional pixel art VFX artist for isometric retro tactics games "
        "(SNES/Genesis era). Generate crisp, vibrant effect animations on a "
        "${background_instruction} with hard pixel edges and stepped shading. Effects should read well "
        "at small sizes, feel dynamic, and clearly read from an isometric top-down camera."
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
        "${perspective_rules}"
        "CRITICAL RULES:\n"
        "- A reference image is attached showing the exact grid layout with magenta dividers. "
        "Match this layout precisely — place each frame within the cells shown.\n"
        "- Produce exactly ${frame_count} distinct frames, each showing a "
        "different phase of the effect lifecycle\n"
        "- Arrange ALL ${frame_count} frames in a single horizontal row, left to right, in animation order\n"
        "- Frame 1: the effect begins as a compact orb, spark cluster, or rune burst occupying roughly 20-35% of the cell — never as a 1-2px line\n"
        "- Middle frames: the effect expands to 45-80% of the cell with a clear focal silhouette\n"
        "- Final frame (frame ${frame_count}): the effect dissipates but still remains readable, around 30-60% of the cell\n"
        "- Show the effect from ABOVE on an isometric battlefield footprint: depict top faces, foreshortened volume, and angled planes — NOT a flat side-view beam or vertical column\n"
        "- Always show the area-of-effect footprint from above rather than a projectile profile from the side\n"
        "- Keep the effect centered in each cell and bias the silhouette diagonally/asymmetrically to imply motion and depth\n"
        "- Add a small dark contact shadow, scorch mark, or grounded footprint under the effect so the top-down placement is unmistakable\n"
        "- Any divider or guide marks visible in the reference image are layout guides only and must NOT appear in the final effect\n"
        "- ${background_rule} except for a tiny dark contact shadow or scorch footprint directly under the effect\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Unified palette of exactly ${max_colors} or fewer colors\n"
        "- Each frame should be the same size\n"
        "- Use the emphasized colors prominently: ${color_emphasis}\n"
        "- Use a bright core, darker rim, and crisp particles/streaks to create depth and motion\n"
        "- No soft glow clouds or blurred halos — any glow must be described with stepped pixel clusters"
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
        "perspective_rules": "",
    },
    reference_strategy="none",
))

register(PromptTemplate(
    name="effect_single_frame",
    description="Generate one frame of an isometric visual effect",
    system_context=(
        "You are a professional pixel art VFX artist for isometric retro tactics games "
        "(SNES/Genesis era). Generate one crisp, vibrant effect frame on a "
        "${background_instruction} with hard pixel edges and stepped shading. The frame must clearly read "
        "from an isometric top-down camera."
    ),
    template=(
        "Create ONE pixel art visual effect frame for: ${effect_description}\n\n"
        "Frame ${frame_index} of ${frame_count}\n"
        "This frame should depict: ${phase_description}\n"
        "Target silhouette coverage: ${occupancy_hint} of the canvas\n"
        "Resolution: ${resolution}\n"
        "Style: ${style}\n"
        "Maximum colors: ${max_colors}\n"
        "Color emphasis: ${color_emphasis}\n\n"
        "${perspective_rules}"
        "CRITICAL RULES:\n"
        "- Draw exactly ONE centered effect frame — no strips, no dividers, no extra panels\n"
        "- If a reference frame is provided, keep the same palette, energy shape language, and top-down orientation while advancing the motion\n"
        "- Show the area-of-effect footprint from above rather than a projectile profile from the side\n"
        "- Depict top faces, foreshortened volume, and angled planes — NOT a flat side-view beam or vertical column\n"
        "- Bias the silhouette diagonally/asymmetrically to imply motion and depth\n"
        "- Add a small dark contact shadow, scorch mark, or grounded footprint under the effect so the top-down placement is unmistakable\n"
        "- ${background_rule} except for a tiny dark contact shadow or scorch footprint directly under the effect\n"
        "- Pixel-perfect rendering: hard pixel edges, stepped shading, no anti-aliasing\n"
        "- Use a bright core, darker rim, and crisp particles/streaks to create depth and motion\n"
        "- No soft glow clouds or blurred halos — any glow must be described with stepped pixel clusters"
    ),
    defaults={
        "effect_description": "magical spell explosion",
        "frame_index": "1",
        "frame_count": "6",
        "phase_description": "compact ember burst beginning to ignite",
        "occupancy_hint": "20-35%",
        "resolution": "64x64",
        "style": "16-bit pixel art",
        "max_colors": "12",
        "color_emphasis": "",
        "background_instruction": "fully transparent background",
        "background_rule": "Background MUST be fully transparent",
        "perspective_rules": "",
    },
    reference_strategy="none",
))
