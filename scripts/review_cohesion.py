#!/usr/bin/env python3
"""Review cohesion across all generated game_demo assets.

Uses the LLM judge to evaluate:
1. Individual asset quality (per-category)
2. Cross-asset style coherence (combined composite)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from pixel_magic.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger("cohesion_review")

BASE = Path("output/game_demo/raw")

# Assets to review — one representative raw composite per category
REVIEW_ITEMS = {
    "knight_directions": {
        "path": BASE / "dark_knight" / "base_directions_raw.png",
        "type": "character_directions",
        "count": 2,
    },
    "knight_walk": {
        "path": BASE / "dark_knight" / "walk_south_east_raw.png",
        "type": "character_animation",
        "count": 6,
    },
    "knight_attack": {
        "path": BASE / "dark_knight" / "attack_south_east_raw.png",
        "type": "character_animation",
        "count": 5,
    },
    "golem_directions": {
        "path": BASE / "crystal_golem" / "base_directions_raw.png",
        "type": "character_directions",
        "count": 2,
    },
    "golem_walk": {
        "path": BASE / "crystal_golem" / "walk_south_east_raw.png",
        "type": "character_animation",
        "count": 4,
    },
    "items": {
        "path": BASE / "items" / "items_raw.png",
        "type": "items",
        "count": 5,
    },
    "ui": {
        "path": BASE / "ui" / "ui_raw.png",
        "type": "ui",
        "count": 4,
    },
    "effect": {
        "path": BASE / "effects" / "effect_raw.png",
        "type": "effects",
        "count": 5,
    },
}


COHESION_PROMPT = """\
You are evaluating the STYLE COHESION of a set of pixel art game assets.
All of these assets are for the same dark fantasy RPG game.
They should look like they belong together — consistent palette, pixel density,
art style, lighting direction, and overall aesthetic.

Look at this composite showing samples from each category
(knight, crystal golem, items, UI, effects).

Score each dimension from 1 (worst) to 10 (best):

1. palette_harmony — Do all assets use a compatible color palette?
   (shared dark tones, consistent accent colors)
2. pixel_density — Is the pixel resolution/density consistent across assets?
   (no mixing of 16px and 64px styles)
3. style_unity — Does the art style feel unified?
   (same era/genre feel, consistent outlines, shading approach)
4. lighting_consistency — Is the light source direction consistent?
5. game_readiness — Would these assets look cohesive in an actual game?
6. overall — Holistic cohesion score

Return ONLY valid JSON:
{"palette_harmony": N, "pixel_density": N, "style_unity": N,
 "lighting_consistency": N, "game_readiness": N, "overall": N,
 "feedback": "2-3 sentences on what works and what could be improved"}
"""


def _create_provider(settings):
    if settings.provider == "openai":
        from pixel_magic.providers.openai import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            quality=settings.openai_quality,
        )
    from pixel_magic.providers.gemini import GeminiProvider
    return GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_model,
        image_model=settings.gemini_image_model,
        fallback_image_model=settings.gemini_image_fallback_model,
        enable_fallback=settings.gemini_enable_image_fallback,
        fallback_after_seconds=settings.gemini_fallback_timeout_s,
    )


def build_cohesion_composite(items: dict) -> Image.Image:
    """Build a composite image with one sample from each category."""
    sample_paths = [
        items["knight_directions"]["path"],
        items["golem_directions"]["path"],
        items["items"]["path"],
        items["ui"]["path"],
        items["effect"]["path"],
    ]

    images = []
    for p in sample_paths:
        if p.exists():
            img = Image.open(p).convert("RGBA")
            # Scale down large images to fit in a reasonable composite
            if img.width > 512:
                ratio = 512 / img.width
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)),
                    Image.NEAREST,
                )
            images.append(img)

    if not images:
        raise RuntimeError("No images found")

    # Stack vertically with labels
    max_w = max(im.width for im in images)
    total_h = sum(im.height for im in images) + (len(images) - 1) * 8
    canvas = Image.new("RGBA", (max_w, total_h), (32, 32, 32, 255))

    y = 0
    for im in images:
        canvas.paste(im, ((max_w - im.width) // 2, y), im)
        y += im.height + 8

    return canvas


async def main() -> None:
    settings = get_settings()
    provider = _create_provider(settings)

    from pixel_magic.evaluation.judge import PixelArtJudge
    judge = PixelArtJudge(provider)

    results = {}

    # 1. Individual asset quality
    logger.info("=== Individual Asset Quality Review ===")
    for name, info in REVIEW_ITEMS.items():
        path = info["path"]
        if not path.exists():
            logger.warning("  %s: MISSING (%s)", name, path)
            continue

        img = Image.open(path).convert("RGBA")
        jr = await judge.evaluate(
            img,
            asset_type=info["type"],
            style="16-bit dark fantasy SNES RPG style",
            max_colors=16,
            expected_count=info["count"],
        )

        results[name] = {
            "scores": {k: round(v, 2) for k, v in jr.scores.items()},
            "overall": round(jr.overall, 2),
            "passed": jr.passed,
            "feedback": jr.feedback,
        }
        status = "PASS" if jr.passed else "FAIL"
        logger.info("  %s: overall=%.2f [%s] — %s", name, jr.overall, status, jr.feedback[:80])

    # 2. Cross-asset cohesion check
    logger.info("\n=== Cross-Asset Cohesion Review ===")
    composite = build_cohesion_composite(REVIEW_ITEMS)
    composite.save(BASE.parent / "cohesion_composite.png")

    raw = await provider.evaluate_image(composite, COHESION_PROMPT)
    cohesion = {}
    if isinstance(raw, dict) and "error" not in raw:
        for dim in ("palette_harmony", "pixel_density", "style_unity",
                     "lighting_consistency", "game_readiness", "overall"):
            score = raw.get(dim, 0)
            cohesion[dim] = round(float(score) / 10, 2)
        cohesion["feedback"] = raw.get("feedback", "")
    else:
        cohesion = {"error": str(raw)}

    results["_cohesion"] = cohesion
    logger.info("  Cohesion scores:")
    for k, v in cohesion.items():
        if k != "feedback":
            logger.info("    %s: %.2f", k, v)
    logger.info("  Feedback: %s", cohesion.get("feedback", "N/A"))

    # 3. Summary
    individual_scores = [r["overall"] for r in results.values()
                         if isinstance(r, dict) and "overall" in r and r != results.get("_cohesion")]
    avg = sum(individual_scores) / len(individual_scores) if individual_scores else 0
    passed = sum(1 for r in results.values()
                 if isinstance(r, dict) and r.get("passed"))
    total = sum(1 for r in results.values()
                if isinstance(r, dict) and "passed" in r)

    results["_summary"] = {
        "avg_individual_quality": round(avg, 2),
        "pass_rate": f"{passed}/{total}",
        "cohesion_overall": cohesion.get("overall", "N/A"),
    }

    report_path = BASE.parent / "cohesion_report.json"
    report_path.write_text(json.dumps(results, indent=2))
    logger.info("\n=== SUMMARY ===")
    logger.info("  Avg quality: %.2f | Pass rate: %d/%d | Cohesion: %s",
                avg, passed, total, cohesion.get("overall", "?"))
    logger.info("  Report: %s", report_path)

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
