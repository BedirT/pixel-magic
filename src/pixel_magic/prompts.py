"""JSON-structured prompt builder for character sprite sheets."""

from __future__ import annotations

import json
from typing import Any


_CHROMAKEY_HEX = {"green": "#00FF00", "blue": "#0000FF"}

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


def _background_instruction(provider: str, chromakey_color: str = "green") -> str:
    if provider == "gemini":
        hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
        return f"solid {chromakey_color} ({hex_color}) background (every non-sprite pixel must be exactly {hex_color})"
    return "fully transparent background (every non-sprite pixel must be alpha=0)"


def _background_rule(provider: str, chromakey_color: str = "green") -> str:
    if provider == "gemini":
        hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
        return f"The ENTIRE image background MUST be solid {chromakey_color} ({hex_color}) — no transparency, no gradients, no shadows, just flat {chromakey_color}"
    return "The ENTIRE image background MUST be fully transparent (alpha=0) — no solid fill, no shadows, no floor"


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
    """Build a JSON-structured prompt for multi-view character reference sheet."""
    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

    prompt: dict[str, Any] = {
        "image_type": "pixel_art",
        "style": "isometric",
        "purpose": "character_sprite_reference_sheet",
        "background": {
            "type": "transparent",
            "rule": _background_rule(provider, chromakey_color),
            "instruction": _background_instruction(provider, chromakey_color),
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
