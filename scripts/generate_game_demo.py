#!/usr/bin/env python3
"""Generate a cohesive set of dark fantasy game assets with LLM validation.

Generates:
  1. Knight character (4-dir) + walk, attack, hurt animations
  2. Weird character — living crystal golem (4-dir) + idle, walk animations
  3. Game items batch
  4. UI elements batch
  5. Attack effect animation

All assets share a consistent dark-fantasy style and palette hint.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Adjust path so we can import pixel_magic
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pixel_magic.config import get_settings
from pixel_magic.generation.orchestrator import SpriteGenerator
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.models.asset import (
    AnimationDef,
    CharacterSpec,
    DirectionMode,
    EffectSpec,
    ItemSpec,
    UIElementSpec,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
)
logger = logging.getLogger("generate_game")

# ── Shared style constants ────────────────────────────────────────────

GAME_STYLE = "16-bit dark fantasy SNES RPG style"
PALETTE_HINT = "muted steel grays, deep crimson, dark gold accents, midnight blue shadows"
MAX_COLORS = 16

# Whether to enable the new LLM validation (set via CLI flag)
VALIDATE = "--validate" in sys.argv
MAX_RETRIES = 2


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


async def main() -> None:
    settings = get_settings()
    provider = _create_provider(settings)
    prompts = PromptBuilder(settings.prompts_dir)
    gen = SpriteGenerator(provider, prompts, settings)

    out_base = settings.output_dir / "game_demo"
    out_base.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    logger.info("=== Dark Fantasy Game Asset Generation ===")
    logger.info("Validation: %s  |  Max retries: %d", VALIDATE, MAX_RETRIES)

    t_total = time.monotonic()

    # ── 1. Knight character ───────────────────────────────────────────
    logger.info("\n[1/5] Generating Knight character...")
    knight_spec = CharacterSpec(
        name="dark_knight",
        description=(
            "a tall dark knight in ornate black plate armor with a red cape, "
            "horned helm with glowing red eye slits, wielding a massive "
            "two-handed greatsword with runes etched along the blade"
        ),
        style=GAME_STYLE,
        direction_mode=DirectionMode.FOUR,
        resolution="64x64",
        max_colors=MAX_COLORS,
        palette_hint=PALETTE_HINT,
        animations={
            "walk": AnimationDef(
                "walk", 6,
                "heavy armored walking cycle with cape swaying, "
                "greatsword resting on shoulder",
                100, True,
            ),
            "attack": AnimationDef(
                "attack", 5,
                "wide horizontal greatsword slash from right to left, "
                "cape flaring dramatically",
                80, False,
            ),
            "hurt": AnimationDef(
                "hurt", 3,
                "staggering backward from impact, shield arm up, "
                "sparks flying off armor",
                120, False,
            ),
        },
    )

    t0 = time.monotonic()
    knight_clips = await gen.generate_character(
        knight_spec,
        output_dir=out_base / "raw" / "dark_knight",
        validate=VALIDATE,
        max_retries=MAX_RETRIES,
    )
    dt = time.monotonic() - t0

    total_frames = sum(
        len(clip.frames)
        for clips in knight_clips.values()
        for clip in clips
    )
    results["dark_knight"] = {
        "animations": list(knight_clips.keys()),
        "total_frames": total_frames,
        "time_s": round(dt, 1),
    }
    logger.info("  Knight done: %d animations, %d frames in %.1fs",
                len(knight_clips), total_frames, dt)

    # ── 2. Weird character — Living Crystal Golem ─────────────────────
    logger.info("\n[2/5] Generating Crystal Golem (weird character)...")
    golem_spec = CharacterSpec(
        name="crystal_golem",
        description=(
            "a bizarre living crystal golem made of jagged floating obsidian "
            "shards orbiting a pulsing core of molten red energy, no head "
            "or limbs in the traditional sense — just a chaotic cluster of "
            "dark crystalline fragments held together by magic tendrils, "
            "with tiny glowing runes on each shard"
        ),
        style=GAME_STYLE,
        direction_mode=DirectionMode.FOUR,
        resolution="64x64",
        max_colors=MAX_COLORS,
        palette_hint=PALETTE_HINT,
        animations={
            "walk": AnimationDef(
                "walk", 4,
                "floating/hovering movement with shards rotating and "
                "energy core pulsing, leaving a faint trail",
                120, True,
            ),
            "attack": AnimationDef(
                "attack", 4,
                "shards explode outward in a ring then snap back, "
                "energy core flares bright red",
                80, False,
            ),
        },
    )

    t0 = time.monotonic()
    golem_clips = await gen.generate_character(
        golem_spec,
        output_dir=out_base / "raw" / "crystal_golem",
        validate=VALIDATE,
        max_retries=MAX_RETRIES,
    )
    dt = time.monotonic() - t0

    total_frames = sum(
        len(clip.frames)
        for clips in golem_clips.values()
        for clip in clips
    )
    results["crystal_golem"] = {
        "animations": list(golem_clips.keys()),
        "total_frames": total_frames,
        "time_s": round(dt, 1),
    }
    logger.info("  Golem done: %d animations, %d frames in %.1fs",
                len(golem_clips), total_frames, dt)

    # ── 3. Game items ─────────────────────────────────────────────────
    logger.info("\n[3/5] Generating game items...")
    item_spec = ItemSpec(
        descriptions=[
            "runic greatsword with glowing red runes",
            "obsidian crystal shard (consumable)",
            "crimson health potion in a dark glass vial",
            "ancient gold coin with skull emblem",
            "dark iron shield with dragon crest",
        ],
        resolution="32x32",
        style=GAME_STYLE,
        max_colors=MAX_COLORS,
        view="front-facing icon",
    )

    t0 = time.monotonic()
    items = await gen.generate_items(
        item_spec,
        output_dir=out_base / "raw" / "items",
        validate=VALIDATE,
        max_retries=MAX_RETRIES,
    )
    dt = time.monotonic() - t0

    results["items"] = {
        "count": len(items),
        "time_s": round(dt, 1),
    }
    logger.info("  Items done: %d icons in %.1fs", len(items), dt)

    # ── 4. UI elements ────────────────────────────────────────────────
    logger.info("\n[4/5] Generating UI elements...")
    ui_spec = UIElementSpec(
        descriptions=[
            "health bar frame (dark iron with red fill area)",
            "mana bar frame (dark iron with blue fill area)",
            "inventory slot (stone texture with beveled border)",
            "minimap frame (ornate dark gold circular border)",
        ],
        resolution="64x64",
        style="16-bit dark fantasy RPG UI style",
        max_colors=12,
    )

    t0 = time.monotonic()
    ui_elements = await gen.generate_ui_elements(
        ui_spec,
        output_dir=out_base / "raw" / "ui",
        validate=VALIDATE,
        max_retries=MAX_RETRIES,
    )
    dt = time.monotonic() - t0

    results["ui"] = {
        "count": len(ui_elements),
        "time_s": round(dt, 1),
    }
    logger.info("  UI done: %d elements in %.1fs", len(ui_elements), dt)

    # ── 5. Attack effect ──────────────────────────────────────────────
    logger.info("\n[5/5] Generating attack effect...")
    effect_spec = EffectSpec(
        description=(
            "dark runic slash effect — a crescent arc of red energy with "
            "dark particle trails, rune symbols briefly visible in the arc"
        ),
        frame_count=5,
        resolution="64x64",
        style=GAME_STYLE,
        max_colors=10,
        color_emphasis="deep crimson, dark red, black, faint gold rune glow",
    )

    t0 = time.monotonic()
    effect = await gen.generate_effect(
        effect_spec,
        output_dir=out_base / "raw" / "effects",
        validate=VALIDATE,
        max_retries=MAX_RETRIES,
    )
    dt = time.monotonic() - t0

    results["effect"] = {
        "frame_count": effect.frame_count,
        "time_s": round(dt, 1),
    }
    logger.info("  Effect done: %d frames in %.1fs", effect.frame_count, dt)

    # ── Summary ───────────────────────────────────────────────────────
    total_time = time.monotonic() - t_total

    results["_summary"] = {
        "total_time_s": round(total_time, 1),
        "validate": VALIDATE,
        "provider": settings.provider,
    }

    summary_path = out_base / "generation_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))

    logger.info("\n=== COMPLETE in %.1fs ===", total_time)
    logger.info("Results saved to %s", summary_path)
    logger.info("Output directory: %s", out_base)
    for name, info in results.items():
        if name.startswith("_"):
            continue
        logger.info("  %s: %s", name, json.dumps(info))

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
