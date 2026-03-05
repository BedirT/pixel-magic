#!/usr/bin/env python3
"""Generate a cohesive dark-fantasy demo asset pack using the workflow executor."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Adjust path so we can import pixel_magic when run from repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pixel_magic.config import get_settings
from pixel_magic.workflow import (
    AgentRuntime,
    AssetType,
    GenerationRequest,
    ProviderAdapter,
    WorkflowExecutor,
    create_provider,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
)
logger = logging.getLogger("generate_game_demo")


GAME_STYLE = "16-bit dark fantasy SNES RPG style"
MAX_COLORS = 16


async def _run_case(
    executor: WorkflowExecutor,
    label: str,
    request: GenerationRequest,
) -> dict[str, object]:
    t0 = time.monotonic()
    result = await executor.run(request)
    dt = round(time.monotonic() - t0, 2)
    if result.status.value != "success":
        error = result.errors[0].message if result.errors else "unknown error"
        raise RuntimeError(f"{label} failed: {error}")

    frame_count = result.artifacts.total_frames if result.artifacts else 0
    output_dir = result.artifacts.output_dir if result.artifacts else ""
    logger.info("  %s done: %d frames in %.2fs", label, frame_count, dt)
    return {
        "label": label,
        "status": result.status.value,
        "frame_count": frame_count,
        "output_dir": output_dir,
        "duration_s": dt,
        "retry_count": result.metrics.retry_count if result.metrics else 0,
    }


async def main() -> None:
    settings = get_settings()
    provider = create_provider(settings)
    adapter = ProviderAdapter(provider, settings)
    agents = AgentRuntime(model=settings.agent_model, api_key=settings.openai_api_key)
    executor = WorkflowExecutor(settings=settings, provider=adapter, agents=agents)

    out_base = settings.output_dir / "game_demo"
    out_base.mkdir(parents=True, exist_ok=True)

    logger.info("=== Dark Fantasy Game Asset Generation (workflow mainline) ===")
    t_total = time.monotonic()
    results: dict[str, dict[str, object]] = {}

    try:
        logger.info("[1/5] Generating Knight character...")
        knight_request = GenerationRequest(
            asset_type=AssetType.CHARACTER,
            name="dark_knight",
            objective=(
                "A tall dark knight in ornate black plate armor, red cape, horned helm, "
                "and a massive runic greatsword."
            ),
            style=GAME_STYLE,
            resolution="64x64",
            max_colors=MAX_COLORS,
            parameters={
                "direction_mode": 4,
                "animations": {
                    "walk": {
                        "frame_count": 6,
                        "description": "heavy armored walk, cape swaying",
                    },
                    "attack": {
                        "frame_count": 5,
                        "description": "wide two-handed slash",
                    },
                    "hurt": {
                        "frame_count": 3,
                        "description": "staggering impact reaction",
                    },
                },
            },
        )
        results["dark_knight"] = await _run_case(executor, "dark_knight", knight_request)

        logger.info("[2/5] Generating Crystal Golem character...")
        golem_request = GenerationRequest(
            asset_type=AssetType.CHARACTER,
            name="crystal_golem",
            objective=(
                "A living crystal golem made of floating obsidian shards around a molten red "
                "core with magical runes."
            ),
            style=GAME_STYLE,
            resolution="64x64",
            max_colors=MAX_COLORS,
            parameters={
                "direction_mode": 4,
                "animations": {
                    "walk": {
                        "frame_count": 4,
                        "description": "hover movement with rotating shards",
                    },
                    "attack": {
                        "frame_count": 4,
                        "description": "shards explode outward then regroup",
                    },
                },
            },
        )
        results["crystal_golem"] = await _run_case(executor, "crystal_golem", golem_request)

        logger.info("[3/5] Generating items...")
        items_request = GenerationRequest(
            asset_type=AssetType.ITEMS,
            name="dark_fantasy_items",
            objective="Dark fantasy RPG item icons batch",
            style=GAME_STYLE,
            resolution="32x32",
            max_colors=MAX_COLORS,
            expected_frames=5,
            parameters={
                "descriptions": [
                    "runic greatsword",
                    "obsidian crystal shard consumable",
                    "crimson health potion",
                    "ancient gold coin with skull emblem",
                    "dark iron shield with dragon crest",
                ],
                "view": "front-facing icon",
            },
        )
        results["items"] = await _run_case(executor, "items", items_request)

        logger.info("[4/5] Generating UI...")
        ui_request = GenerationRequest(
            asset_type=AssetType.UI,
            name="dark_fantasy_ui",
            objective="Dark fantasy RPG UI element batch",
            style="16-bit dark fantasy RPG UI style",
            resolution="64x64",
            max_colors=12,
            expected_frames=4,
            parameters={
                "descriptions": [
                    "health bar frame with red fill area",
                    "mana bar frame with blue fill area",
                    "inventory slot with beveled stone border",
                    "ornate circular minimap frame",
                ]
            },
        )
        results["ui"] = await _run_case(executor, "ui", ui_request)

        logger.info("[5/5] Generating attack effect...")
        effect_request = GenerationRequest(
            asset_type=AssetType.EFFECT,
            name="dark_rune_slash",
            objective=(
                "Dark runic slash effect: a crescent arc of red energy with dark particle trails."
            ),
            style=GAME_STYLE,
            resolution="64x64",
            max_colors=10,
            expected_frames=5,
            parameters={
                "frame_count": 5,
                "color_emphasis": "deep crimson, dark red, black, faint gold rune glow",
            },
        )
        results["effect"] = await _run_case(executor, "effect", effect_request)

        total_time = round(time.monotonic() - t_total, 2)
        results["_summary"] = {
            "provider": settings.provider,
            "total_time_s": total_time,
            "output_root": str(out_base),
        }

        summary_path = out_base / "generation_summary.json"
        summary_path.write_text(json.dumps(results, indent=2))
        logger.info("=== COMPLETE in %.2fs ===", total_time)
        logger.info("Summary written to %s", summary_path)
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
