"""Entry points for running sprite generation agents."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image

from agents import Runner

from pixel_magic.tracing import get_tracer

from pixel_magic.agents.character_agent import create_character_agent
from pixel_magic.agents.context import AgentContext
from pixel_magic.agents.effect_agent import create_effect_agent
from pixel_magic.agents.item_agent import create_item_agent
from pixel_magic.agents.tileset_agent import create_tileset_agent
from pixel_magic.agents.ui_agent import create_ui_agent
from pixel_magic.config import Settings
from pixel_magic.models.asset import (
    AnimationClip,
    AnimationDef,
    CharacterSpec,
    Direction,
    EffectSpec,
    ItemSpec,
    SpriteAsset,
    TilesetSpec,
    UIElementSpec,
)
from pixel_magic.providers.base import ImageProvider

logger = logging.getLogger(__name__)
_tracer = get_tracer("pixel_magic.agents.runner")


def _build_clips(
    ctx: AgentContext,
    default_duration_ms: int = 100,
) -> dict[str, list[AnimationClip]]:
    """Build AnimationClip objects from the agent's saved_clips data."""
    clips_by_anim: dict[str, list[AnimationClip]] = {}

    for clip_data in ctx.saved_clips:
        direction_str = clip_data["direction"]
        anim_name = clip_data["animation_name"]
        frame_keys = clip_data["frame_keys"]
        duration_ms = clip_data.get("duration_ms", default_duration_ms)
        is_looping = clip_data.get("is_looping", True)

        # Resolve direction enum
        direction = None
        for d in Direction:
            if d.value == direction_str:
                direction = d
                break
        if direction is None:
            direction = Direction.SE

        # Build SpriteAsset list
        frames = []
        for i, key in enumerate(frame_keys):
            image = ctx.images.get(key)
            if image is None:
                logger.warning("Frame key '%s' not found in context images", key)
                continue
            frames.append(SpriteAsset(
                image=image,
                direction=direction,
                animation_name=anim_name,
                frame_index=i,
            ))

        clip = AnimationClip(
            name=anim_name,
            direction=direction,
            frames=frames,
            duration_ms=duration_ms,
            is_looping=is_looping,
        )

        clips_by_anim.setdefault(anim_name, []).append(clip)

    return clips_by_anim


def _build_assets(ctx: AgentContext) -> list[SpriteAsset]:
    """Build SpriteAsset list from saved_clips (for non-character outputs)."""
    assets = []
    for clip_data in ctx.saved_clips:
        anim_name = clip_data["animation_name"]
        frame_keys = clip_data["frame_keys"]
        for i, key in enumerate(frame_keys):
            image = ctx.images.get(key)
            if image is None:
                continue
            assets.append(SpriteAsset(
                image=image,
                animation_name=anim_name,
                frame_index=i,
            ))
    return assets


async def run_character_generation(
    provider: ImageProvider,
    settings: Settings,
    spec: CharacterSpec,
    output_dir: Path,
) -> dict[str, list[AnimationClip]]:
    """Run the character agent to generate a complete sprite set."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = AgentContext(provider=provider, settings=settings, output_dir=output_dir)

    agent = create_character_agent(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
    )

    unique_dirs = Direction.unique_for_mode(spec.direction_mode)
    dir_names = ", ".join(d.value for d in unique_dirs)

    anims_desc = "\n".join(
        f"  - {name}: {d.frame_count} frames, {d.description}, "
        f"{'looping' if d.is_looping else 'one-shot'}, {d.duration_ms}ms/frame"
        for name, d in spec.animations.items()
    )

    dir_count = len(unique_dirs)
    anim_count = len(spec.animations)
    total_combos = dir_count * anim_count

    task = (
        f"Generate a complete character sprite set.\n\n"
        f"## Character Details\n"
        f"- Description: {spec.description}\n"
        f"- Style: {spec.style}\n"
        f"- Target resolution: {spec.resolution}\n"
        f"- Max colors: {spec.max_colors}\n"
        f"- Palette hint: {spec.palette_hint or 'none'}\n\n"
        f"## Directions to Generate\n"
        f"You MUST generate for these {dir_count} directions: {dir_names}\n"
        f"(SW, NW, W are derived by horizontal flip — do NOT generate them.)\n\n"
        f"## Animations\n{anims_desc}\n\n"
        f"## Required Workflow\n"
        f"1. Generate a SEPARATE base pose for EACH direction ({dir_count} total):\n"
        f"   For each direction: generate_image → evaluate_quality → "
        f"resize_to_target to '{spec.resolution}' → save_frames\n\n"
        f"2. Generate animations for EACH direction × EACH animation "
        f"({total_combos} total combinations):\n"
        f"   For each combo: generate_image (with base pose as reference) → "
        f"split_frames → resize_to_target to '{spec.resolution}' → save_frames\n\n"
        f"## CRITICAL REMINDERS\n"
        f"- ALWAYS call resize_to_target to '{spec.resolution}' BEFORE save_frames\n"
        f"- Do NOT skip any direction — you must cover all {dir_count} directions\n"
        f"- Do NOT skip any animation — you must cover all {anim_count} animations "
        f"for each direction\n"
        f"- When done, you should have saved {dir_count} base poses + "
        f"{total_combos} animation clips"
    )

    logger.info("Starting character agent for '%s'", spec.name)
    with _tracer.start_as_current_span("agent.character") as span:
        span.set_attribute("character.name", spec.name)
        span.set_attribute("character.directions", dir_count)
        span.set_attribute("character.animations", anim_count)
        span.set_attribute("character.resolution", spec.resolution)
        t0 = time.monotonic()

        result = await Runner.run(agent, task, context=ctx, max_turns=50)

        span.set_attribute("agent.duration_s", round(time.monotonic() - t0, 2))
        span.set_attribute("agent.clips_saved", len(ctx.saved_clips))
        span.set_attribute("agent.images_generated", len(ctx.images))

    logger.info(
        "Character agent completed. Saved %d clips, %d images in context.",
        len(ctx.saved_clips), len(ctx.images),
    )

    return _build_clips(ctx)


async def run_tileset_generation(
    provider: ImageProvider,
    settings: Settings,
    spec: TilesetSpec,
    output_dir: Path,
) -> list[SpriteAsset]:
    """Run the tileset agent to generate tiles."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = AgentContext(provider=provider, settings=settings, output_dir=output_dir)

    agent = create_tileset_agent(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
    )

    tile_types_str = ", ".join(spec.tile_types)
    tile_count = len(spec.tile_types)
    tile_size = f"{spec.tile_width}x{spec.tile_height}"
    task = (
        f"Generate a complete isometric tileset.\n\n"
        f"## Tileset Details\n"
        f"- Biome: {spec.biome}\n"
        f"- Tile types: {tile_types_str}\n"
        f"- Tile size: {tile_size}\n"
        f"- Style: {spec.style}\n"
        f"- Max colors: {spec.max_colors}\n\n"
        f"## Required Workflow\n"
        f"1. generate_image — create all {tile_count} tiles in ONE horizontal strip\n"
        f"2. split_frames — extract {tile_count} individual tiles\n"
        f"3. evaluate_quality — spot-check at least one tile\n"
        f"4. resize_to_target — resize ALL {tile_count} tiles to '{tile_size}'\n"
        f"5. save_frames — save each tile with direction=\"\" and "
        f"animation_name=tile_type_name\n\n"
        f"## CRITICAL REMINDERS\n"
        f"- ALWAYS call resize_to_target to '{tile_size}' BEFORE save_frames\n"
        f"- Do NOT skip any tile type — you must generate all {tile_count} tiles\n"
        f"- When done, you should have saved {tile_count} tiles"
    )

    logger.info("Starting tileset agent for '%s'", spec.name)
    with _tracer.start_as_current_span("agent.tileset") as span:
        span.set_attribute("tileset.name", spec.name)
        span.set_attribute("tileset.biome", spec.biome)
        span.set_attribute("tileset.tile_count", tile_count)
        t0 = time.monotonic()
        await Runner.run(agent, task, context=ctx, max_turns=50)
        span.set_attribute("agent.duration_s", round(time.monotonic() - t0, 2))
        span.set_attribute("agent.clips_saved", len(ctx.saved_clips))
    return _build_assets(ctx)


async def run_item_generation(
    provider: ImageProvider,
    settings: Settings,
    spec: ItemSpec,
    output_dir: Path,
) -> list[SpriteAsset]:
    """Run the item agent to generate item sprites."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = AgentContext(provider=provider, settings=settings, output_dir=output_dir)

    agent = create_item_agent(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
    )

    items_str = ", ".join(spec.descriptions)
    item_count = len(spec.descriptions)
    task = (
        f"Generate pixel art item sprites.\n\n"
        f"## Item Details\n"
        f"- Items: {items_str}\n"
        f"- Resolution: {spec.resolution}\n"
        f"- Style: {spec.style}\n"
        f"- Max colors: {spec.max_colors}\n"
        f"- View: {spec.view}\n\n"
        f"## Required Workflow\n"
        f"1. generate_image — create all {item_count} items in ONE horizontal strip\n"
        f"2. split_frames — extract {item_count} individual items\n"
        f"3. evaluate_quality — spot-check at least one item\n"
        f"4. resize_to_target — resize ALL {item_count} items to '{spec.resolution}'\n"
        f"5. save_frames — save each item with direction=\"\" and "
        f"animation_name=item_name\n\n"
        f"## CRITICAL REMINDERS\n"
        f"- ALWAYS call resize_to_target to '{spec.resolution}' BEFORE save_frames\n"
        f"- Do NOT skip any item — you must generate all {item_count} items\n"
        f"- When done, you should have saved {item_count} items"
    )

    logger.info("Starting item agent for %d items", len(spec.descriptions))
    with _tracer.start_as_current_span("agent.item") as span:
        span.set_attribute("item.count", item_count)
        t0 = time.monotonic()
        await Runner.run(agent, task, context=ctx, max_turns=50)
        span.set_attribute("agent.duration_s", round(time.monotonic() - t0, 2))
        span.set_attribute("agent.clips_saved", len(ctx.saved_clips))
    return _build_assets(ctx)


async def run_effect_generation(
    provider: ImageProvider,
    settings: Settings,
    spec: EffectSpec,
    output_dir: Path,
) -> AnimationClip:
    """Run the effect agent to generate an animated effect."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = AgentContext(provider=provider, settings=settings, output_dir=output_dir)

    agent = create_effect_agent(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
    )

    task = (
        f"Generate an animated pixel art effect.\n\n"
        f"## Effect Details\n"
        f"- Effect: {spec.description}\n"
        f"- Frame count: {spec.frame_count}\n"
        f"- Resolution: {spec.resolution}\n"
        f"- Style: {spec.style}\n"
        f"- Max colors: {spec.max_colors}\n"
        f"- Color emphasis: {spec.color_emphasis or 'none'}\n\n"
        f"## Required Workflow\n"
        f"1. generate_image — create all {spec.frame_count} frames in ONE "
        f"horizontal strip\n"
        f"2. split_frames — extract {spec.frame_count} individual frames\n"
        f"3. evaluate_quality — spot-check at least one frame\n"
        f"4. resize_to_target — resize ALL {spec.frame_count} frames to "
        f"'{spec.resolution}'\n"
        f"5. save_frames — save with direction=\"\" (effects are omnidirectional) "
        f"and animation_name=\"effect\"\n\n"
        f"## CRITICAL REMINDERS\n"
        f"- ALWAYS call resize_to_target to '{spec.resolution}' BEFORE save_frames\n"
        f"- Effects are direction-independent — use direction=\"\" when saving\n"
        f"- When done, you should have saved {spec.frame_count} frames"
    )

    logger.info("Starting effect agent for '%s'", spec.description[:50])
    with _tracer.start_as_current_span("agent.effect") as span:
        span.set_attribute("effect.description", spec.description[:100])
        span.set_attribute("effect.frame_count", spec.frame_count)
        t0 = time.monotonic()
        await Runner.run(agent, task, context=ctx, max_turns=50)
        span.set_attribute("agent.duration_s", round(time.monotonic() - t0, 2))
        span.set_attribute("agent.clips_saved", len(ctx.saved_clips))

    clips = _build_clips(ctx, default_duration_ms=80)
    for anim_clips in clips.values():
        if anim_clips:
            return anim_clips[0]

    return AnimationClip(
        name="effect",
        direction=Direction.S,
        frames=[],
        duration_ms=80,
        is_looping=False,
    )


async def run_ui_generation(
    provider: ImageProvider,
    settings: Settings,
    spec: UIElementSpec,
    output_dir: Path,
) -> list[SpriteAsset]:
    """Run the UI agent to generate UI elements."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = AgentContext(provider=provider, settings=settings, output_dir=output_dir)

    agent = create_ui_agent(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
    )

    elements_str = ", ".join(spec.descriptions)
    element_count = len(spec.descriptions)
    task = (
        f"Generate pixel art UI elements.\n\n"
        f"## UI Element Details\n"
        f"- Elements: {elements_str}\n"
        f"- Resolution: {spec.resolution}\n"
        f"- Style: {spec.style}\n"
        f"- Max colors: {spec.max_colors}\n\n"
        f"## Required Workflow\n"
        f"1. generate_image — create all {element_count} elements in ONE "
        f"horizontal strip\n"
        f"2. split_frames — extract {element_count} individual elements\n"
        f"3. evaluate_quality — spot-check at least one element\n"
        f"4. resize_to_target — resize ALL {element_count} elements to "
        f"'{spec.resolution}'\n"
        f"5. save_frames — save each element with direction=\"\" and "
        f"animation_name=element_name\n\n"
        f"## CRITICAL REMINDERS\n"
        f"- ALWAYS call resize_to_target to '{spec.resolution}' BEFORE save_frames\n"
        f"- Do NOT skip any element — you must generate all {element_count} elements\n"
        f"- When done, you should have saved {element_count} UI elements"
    )

    logger.info("Starting UI agent for %d elements", len(spec.descriptions))
    with _tracer.start_as_current_span("agent.ui") as span:
        span.set_attribute("ui.element_count", element_count)
        t0 = time.monotonic()
        await Runner.run(agent, task, context=ctx, max_turns=50)
        span.set_attribute("agent.duration_s", round(time.monotonic() - t0, 2))
        span.set_attribute("agent.clips_saved", len(ctx.saved_clips))
    return _build_assets(ctx)
