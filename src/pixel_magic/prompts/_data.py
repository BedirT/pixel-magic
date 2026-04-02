"""Shared constants and helpers for prompt templates."""

from __future__ import annotations


CHROMAKEY_HEX: dict[str, str] = {
    "green": "#00FF00",
    "blue": "#0000FF",
    "pink": "#FF00FF",
}

VIEWS_4DIR: list[dict[str, str]] = [
    {
        "position": "left",
        "facing": "south_west",
        "description": "Front 3/4 isometric view facing south-west — face and chest visible from above",
    },
    {
        "position": "right",
        "facing": "north_east",
        "description": "Rear 3/4 isometric view facing north-east — back and top of head visible",
    },
]

VIEWS_8DIR: list[dict[str, str]] = [
    {
        "position": "far_left",
        "facing": "north",
        "description": "Full rear isometric view facing north — top of head and back visible",
    },
    {
        "position": "center_left",
        "facing": "north_east",
        "description": "Rear 3/4 isometric view facing north-east — back and right shoulder visible from above",
    },
    {
        "position": "center",
        "facing": "east",
        "description": "Side isometric view facing east — right profile visible",
    },
    {
        "position": "center_right",
        "facing": "south_east",
        "description": "Front 3/4 isometric view facing south-east — face and chest visible from above",
    },
    {
        "position": "far_right",
        "facing": "south",
        "description": "Front isometric view facing south — face and front of body visible",
    },
]

POSITION_NAMES_4DIR: list[str] = ["left platform", "right platform"]
POSITION_NAMES_8DIR: list[str] = [
    "top-left platform", "top-center platform", "top-right platform",
    "bottom-left platform", "bottom-right platform",
]

DEFAULT_SPATIAL_RULES: list[str] = [
    "Keep the character's feet/base touching the same ground line in every frame",
    "Keep the character's center of mass in the same horizontal position — no sliding",
    "Keep the character the same size in every frame — no growing or shrinking",
]

DEFAULT_OBJECT_SPATIAL_RULES: list[str] = [
    "Keep the object's base touching the same ground line in every frame",
    "Keep the object centered in the same horizontal position — no sliding",
    "Keep the object the same size in every frame",
]

DEFAULT_EFFECT_SPATIAL_RULES: list[str] = [
    "Keep the effect centered in the same position in every frame",
    "Keep the overall effect size consistent between frames",
]


def background_instruction(chromakey_color: str = "green") -> str:
    """One-line background instruction for prompts."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return f"solid {chromakey_color} ({hex_color}) background (every non-sprite pixel must be exactly {hex_color})"


def background_rule(chromakey_color: str = "green") -> str:
    """Full background rule for prompts."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return (
        f"The ENTIRE image background MUST be solid {chromakey_color} ({hex_color}) "
        f"— no transparency, no gradients, no shadows, just flat {chromakey_color}"
    )
