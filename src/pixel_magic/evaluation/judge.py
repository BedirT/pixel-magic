"""LLM-as-judge — structured rubric evaluation for generated pixel art."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from PIL import Image

from pixel_magic.providers.base import ImageProvider

logger = logging.getLogger(__name__)


# ── Rubric dimensions ─────────────────────────────────────────────────

DIMENSIONS = [
    "instruction_following",
    "pixel_art_quality",
    "style_adherence",
    "composition_layout",
    "silhouette_readability",
    "palette_discipline",
    "consistency",
    "overall",
]

# ── Judge prompts per asset type ──────────────────────────────────────

_BASE_RUBRIC = """\
You are an expert pixel art judge evaluating AI-generated sprite images.
Score each dimension from 1 (worst) to 10 (best). Be strict and precise.

**Dimensions:**
1. instruction_following — Did the output match ALL explicit instructions?
   (correct number of sprites, correct layout, correct subject matter)
2. pixel_art_quality — Clean pixel grid, no anti-aliasing/blur/gradients,
   no subpixel artifacts, crisp single-pixel edges
3. style_adherence — Authentic {style} pixel art style, appropriate color ramps,
   intentional shading, period-accurate aesthetic
4. composition_layout — Sprites arranged correctly in the requested layout
   (horizontal strip, evenly spaced, consistent sizing).
   Look for magenta (#FF00FF) separator lines between sprites — these are
   intentional framing guides. Presence of clear separators is a positive signal.
5. silhouette_readability — Clear, recognizable silhouette at target size,
   good contrast against transparent background
6. palette_discipline — Limited, intentional palette (max {max_colors} colors),
   no color noise, consistent use across sprites
7. consistency — All sprites look like they belong together (same character/set),
   matching proportions, colors, and style
8. overall — Holistic quality considering all dimensions above

{type_specific_rubric}

Return ONLY valid JSON:
{{"instruction_following": N, "pixel_art_quality": N, "style_adherence": N,
  "composition_layout": N, "silhouette_readability": N, "palette_discipline": N,
  "consistency": N, "overall": N, "feedback": "2-3 sentences of specific feedback"}}"""


_CHARACTER_DIRECTIONS_RUBRIC = """\
**Type-specific: Character Directions**
- Expected: {count} sprites in a horizontal row, same character facing different directions
- Each sprite should be a standing idle pose
- Isometric perspective (2:1 ratio, ~30° viewing angle):
  For 2-sprite sets: south-east (front-right) and north-east (back-right) facing
  For 5-sprite sets: S, SE, E, NE, N (front to back sweep)
- Look for magenta (#FF00FF) vertical divider lines between sprites (good framing)
- Extra attention to: identical character design across all directions, correct facing angles"""

_ANIMATION_RUBRIC = """\
**Type-specific: Animation Strip**
- Expected: {count} frames in a horizontal row showing smooth animation progression
- Same character in every frame (identical proportions, colors, face)
- Only animated parts should change between frames
- First and last frames should loop cleanly if applicable
- Look for magenta (#FF00FF) vertical divider lines between frames (good framing)
- Extra attention to: motion quality and character identity preservation"""

_TILESET_RUBRIC = """\
**Type-specific: Tileset**
- Expected: {count} tiles in a horizontal row
- Isometric diamond tiles with seamless edges
- Consistent lighting (top-left light source)
- Tiles should have natural texture variation
- Look for magenta (#FF00FF) vertical divider lines between tiles (good framing)
- Extra attention to: seamless tiling capability and consistent lighting"""

_ITEMS_RUBRIC = """\
**Type-specific: Item Icons**
- Expected: {count} distinct item icons in a horizontal row
- Each should be instantly recognizable at target size
- Bold outlines for readability
- Items should look like game inventory icons
- Look for magenta (#FF00FF) vertical divider lines between icons (good framing)
- Extra attention to: icon readability and design distinctiveness"""

_EFFECTS_RUBRIC = """\
**Type-specific: Effect Animation**
- Expected: {count} frames showing effect lifecycle (appear → peak → dissipate)
- Vibrant, dynamic look with particle/energy details
- Clean transparency — effect floats in space
- Look for magenta (#FF00FF) vertical divider lines between frames (good framing)
- Extra attention to: dynamic quality and lifecycle progression"""

_UI_RUBRIC = """\
**Type-specific: UI Elements**
- Expected: {count} UI elements in a horizontal row
- Functional-looking game UI (borders, frames, slots)
- Consistent frame/border style
- Look for magenta (#FF00FF) vertical divider lines between elements (good framing)
- Extra attention to: functional clarity and visual unity"""

TYPE_RUBRICS = {
    "character_directions": _CHARACTER_DIRECTIONS_RUBRIC,
    "character_animation": _ANIMATION_RUBRIC,
    "tileset": _TILESET_RUBRIC,
    "items": _ITEMS_RUBRIC,
    "effects": _EFFECTS_RUBRIC,
    "ui": _UI_RUBRIC,
}


@dataclass
class JudgeResult:
    """Structured output from the LLM judge."""

    scores: dict[str, float] = field(default_factory=dict)
    feedback: str = ""
    raw_response: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def overall(self) -> float:
        return self.scores.get("overall", 0.0)

    @property
    def passed(self) -> bool:
        return self.overall >= 0.7

    def to_dict(self) -> dict:
        return {
            "scores": self.scores,
            "feedback": self.feedback,
            "overall": self.overall,
            "passed": self.passed,
            "error": self.error,
        }


class PixelArtJudge:
    """LLM-as-judge for scoring generated pixel art on structured rubrics."""

    def __init__(self, provider: ImageProvider):
        self._provider = provider

    async def evaluate(
        self,
        image: Image.Image,
        asset_type: str,
        style: str = "16-bit SNES RPG style",
        max_colors: int = 16,
        expected_count: int = 1,
    ) -> JudgeResult:
        """Score a generated image against the rubric for the given asset type.

        Args:
            image: The generated composite image to evaluate.
            asset_type: One of: character_directions, character_animation,
                        tileset, items, effects, ui.
            style: The requested pixel art style.
            max_colors: Expected max palette colors.
            expected_count: Expected number of sprites/frames in the image.

        Returns:
            JudgeResult with normalized scores (0-1 scale).
        """
        type_rubric = TYPE_RUBRICS.get(asset_type, "")
        if type_rubric:
            type_rubric = type_rubric.format(count=expected_count)

        prompt = _BASE_RUBRIC.format(
            style=style,
            max_colors=max_colors,
            type_specific_rubric=type_rubric,
        )

        try:
            raw = await self._provider.evaluate_image(image, prompt)
        except Exception as e:
            logger.error("Judge evaluation failed: %s", e)
            return JudgeResult(error=str(e))

        return self._parse_response(raw)

    async def evaluate_comparison(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
        asset_type: str,
        style: str = "16-bit SNES RPG style",
        max_colors: int = 16,
        expected_count: int = 1,
    ) -> tuple[JudgeResult, JudgeResult]:
        """Evaluate two images independently for A/B comparison.

        Returns results for (image_a, image_b).
        """
        result_a = await self.evaluate(
            image_a, asset_type, style, max_colors, expected_count
        )
        result_b = await self.evaluate(
            image_b, asset_type, style, max_colors, expected_count
        )
        return result_a, result_b

    @staticmethod
    def _parse_response(raw: dict) -> JudgeResult:
        """Parse provider response into normalized JudgeResult."""
        if "error" in raw:
            return JudgeResult(
                raw_response=raw,
                error=raw.get("error", "Unknown error"),
            )

        scores = {}
        for dim in DIMENSIONS:
            val = raw.get(dim, 0)
            try:
                scores[dim] = float(val) / 10.0  # Normalize 1-10 → 0-1
            except (TypeError, ValueError):
                scores[dim] = 0.0

        return JudgeResult(
            scores=scores,
            feedback=str(raw.get("feedback", "")),
            raw_response=raw,
        )
