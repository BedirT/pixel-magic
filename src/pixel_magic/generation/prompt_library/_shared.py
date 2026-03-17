"""Shared prompt constants used by all template modules."""

from __future__ import annotations

_CHROMAKEY_HEX = {"green": "#00FF00", "blue": "#0000FF"}

_FRAMING_BASE = (
    "\nFRAMING — CRITICAL:\n"
    "- Place a 1-pixel-wide MAGENTA (#FF00FF) vertical line between each sprite/frame "
    "as a separator\n"
    "- Each sprite occupies an equal-width cell in the horizontal row\n"
    "- The magenta separator must span the FULL height of the image\n"
    "- Do NOT place magenta lines at the left or right edges — only BETWEEN sprites\n"
    "- Do NOT use magenta (#FF00FF) anywhere else in the artwork\n"
    "- ${background_rule}\n"
)


def framing_rules(provider: str = "openai", chromakey_color: str = "green") -> str:
    """Return framing rules with provider-appropriate background instruction."""
    if provider == "gemini":
        hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
        bg_line = f"- The ENTIRE image background must be filled with solid {chromakey_color} ({hex_color}) — every pixel not part of a sprite must be exactly this color"
    else:
        bg_line = "- The ENTIRE image background must be fully transparent — every pixel not part of a sprite must have alpha=0"
    return _FRAMING_BASE + bg_line


def background_instruction(provider: str = "openai", chromakey_color: str = "green") -> str:
    """Return the background instruction text for prompt templates."""
    if provider == "gemini":
        hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
        return f"solid {chromakey_color} ({hex_color}) background (every non-sprite pixel must be exactly {hex_color})"
    return "fully transparent background (every non-sprite pixel must be alpha=0)"


def background_rule(provider: str = "openai", chromakey_color: str = "green") -> str:
    """Return the background rule text for prompt templates."""
    if provider == "gemini":
        hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
        return f"The ENTIRE image background MUST be solid {chromakey_color} ({hex_color}) — no transparency, no gradients, no shadows, just flat {chromakey_color}"
    return "The ENTIRE image background MUST be fully transparent (alpha=0) — no solid fill, no shadows, no floor"


# Template-variable version: uses ${background_rule} so it adapts per-provider at render time
FRAMING_RULES = _FRAMING_BASE

# Generic isometric perspective rules (no character-specific directions).
# Used by effects, custom, and any asset type that wants isometric perspective.
ISOMETRIC_PERSPECTIVE = (
    "\nPERSPECTIVE — MANDATORY (isometric 3/4 top-down view):\n"
    "- The camera is positioned ABOVE and in front of the subject, looking "
    "down at ~30°. The viewer can see the TOP of the subject.\n"
    "- Subjects appear slightly foreshortened vertically — they are NOT "
    "drawn as flat front-facing images. Imagine the subject sitting on a "
    "diamond-shaped floor tile.\n"
    "- The ground plane is an isometric diamond grid (2:1 width-to-height ratio).\n"
    "- Think of classic SNES RPG sprites: Final Fantasy VI, Chrono Trigger "
    "overworld, Final Fantasy Tactics — that exact camera angle.\n"
)


def perspective_rules(perspective: str = "isometric") -> str:
    """Return perspective rules string based on the requested perspective."""
    if perspective.lower() == "isometric":
        return ISOMETRIC_PERSPECTIVE
    return ""
