"""Sprite generation orchestrator — delegates to multi-agent system."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from pixel_magic.agents.runner import (
    run_character_generation,
    run_effect_generation,
    run_item_generation,
    run_tileset_generation,
    run_ui_generation,
)
from pixel_magic.config import Settings
from pixel_magic.generation.extractor import (
    CompositeLayout,
    extract_frames,
    normalize_frame_sizes,
)
from pixel_magic.models.asset import (
    AnimationClip,
    AnimationDef,
    CharacterSpec,
    Direction,
    DirectionMode,
    EffectSpec,
    ItemSpec,
    SpriteAsset,
    TilesetSpec,
    UIElementSpec,
)
from pixel_magic.providers.base import GenerationConfig, ImageProvider

logger = logging.getLogger(__name__)


class SpriteGenerator:
    """Orchestrates sprite generation via multi-agent system."""

    def __init__(self, provider: ImageProvider, prompts, settings: Settings):
        self._provider = provider
        self._prompts = prompts  # kept for backward compat, unused by agents
        self._settings = settings

    async def generate_character(
        self,
        spec: CharacterSpec,
        output_dir: Path | None = None,
        **kwargs,
    ) -> dict[str, list[AnimationClip]]:
        """Generate a complete character sprite set with all directions and animations."""
        out = output_dir or self._settings.output_dir / "raw" / spec.name
        return await run_character_generation(
            self._provider, self._settings, spec, out
        )

    async def generate_tileset(
        self,
        spec: TilesetSpec,
        output_dir: Path | None = None,
        **kwargs,
    ) -> list[SpriteAsset]:
        """Generate an isometric tileset."""
        out = output_dir or self._settings.output_dir / "raw" / spec.name
        return await run_tileset_generation(
            self._provider, self._settings, spec, out
        )

    async def generate_items(
        self,
        spec: ItemSpec,
        output_dir: Path | None = None,
        **kwargs,
    ) -> list[SpriteAsset]:
        """Generate item icons."""
        out = output_dir or self._settings.output_dir / "raw" / "items"
        return await run_item_generation(
            self._provider, self._settings, spec, out
        )

    async def generate_effect(
        self,
        spec: EffectSpec,
        output_dir: Path | None = None,
        **kwargs,
    ) -> AnimationClip:
        """Generate an animated visual effect."""
        out = output_dir or self._settings.output_dir / "raw" / "effects"
        return await run_effect_generation(
            self._provider, self._settings, spec, out
        )

    async def generate_ui_elements(
        self,
        spec: UIElementSpec,
        output_dir: Path | None = None,
        **kwargs,
    ) -> list[SpriteAsset]:
        """Generate UI elements."""
        out = output_dir or self._settings.output_dir / "raw" / "ui"
        return await run_ui_generation(
            self._provider, self._settings, spec, out
        )

    async def generate_custom(
        self,
        prompt: str,
        frame_count: int = 1,
        layout: CompositeLayout = CompositeLayout.HORIZONTAL_STRIP,
        output_dir: Path | None = None,
    ) -> list[SpriteAsset]:
        """Freeform generation from a custom prompt (direct, no agent)."""
        out = output_dir or self._settings.output_dir / "raw" / "custom"
        out.mkdir(parents=True, exist_ok=True)

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._provider.generate(prompt, config)
        result.image.save(out / "custom_raw.png")

        if frame_count <= 1:
            asset = SpriteAsset(image=result.image, frame_index=0)
            return [asset]

        frames = extract_frames(result.image, layout, frame_count)
        frames = normalize_frame_sizes(frames)

        assets = []
        for i, img in enumerate(frames):
            asset = SpriteAsset(image=img, frame_index=i)
            img.save(out / f"custom_{i:03d}.png")
            assets.append(asset)

        return assets

    async def add_character_animation(
        self,
        character_name: str,
        reference_image_path: Path,
        anim_def: AnimationDef,
        direction_mode: DirectionMode = DirectionMode.FOUR,
        style: str = "16-bit SNES RPG style",
        resolution: str = "64x64",
        max_colors: int = 16,
        output_dir: Path | None = None,
    ) -> list[AnimationClip]:
        """Add a custom animation to an existing character using a reference image."""
        out = output_dir or self._settings.output_dir / "raw" / character_name
        out.mkdir(parents=True, exist_ok=True)

        ref_image = Image.open(reference_image_path).convert("RGBA")
        unique_dirs = Direction.unique_for_mode(direction_mode)

        config = GenerationConfig(image_size=self._settings.image_size)
        clips = []

        for direction in unique_dirs:
            prompt = (
                f"Create a horizontal strip of exactly {anim_def.frame_count} "
                f"animation frames showing a pixel art character performing: "
                f"{anim_def.name} ({anim_def.description}). "
                f"Character faces {direction.value}. Same character as reference. "
                f"Style: {style}. Resolution: {resolution}. "
                f"Max {max_colors} colors. Transparent background. "
                f"Isometric perspective. Hard pixel edges, no anti-aliasing."
            )

            result = await self._provider.generate_with_references(
                prompt, [ref_image], config
            )

            frames_imgs = extract_frames(
                result.image, CompositeLayout.HORIZONTAL_STRIP, anim_def.frame_count
            )
            frames_imgs = normalize_frame_sizes(frames_imgs)

            result.image.save(out / f"{anim_def.name}_{direction.value}_raw.png")

            sprite_frames = []
            for i, img in enumerate(frames_imgs):
                asset = SpriteAsset(
                    image=img,
                    direction=direction,
                    animation_name=anim_def.name,
                    frame_index=i,
                )
                img.save(out / f"{anim_def.name}_{direction.value}_{i:03d}.png")
                sprite_frames.append(asset)

            clips.append(AnimationClip(
                name=anim_def.name,
                direction=direction,
                frames=sprite_frames,
                duration_ms=anim_def.duration_ms,
                is_looping=anim_def.is_looping,
            ))

        return clips
