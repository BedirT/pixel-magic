"""Sprite generation orchestrator — coordinates multi-step generation workflows."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.generation.extractor import (
    CompositeLayout,
    extract_frames,
    normalize_frame_sizes,
)
from pixel_magic.generation.prompts import PromptBuilder
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
from pixel_magic.generation.validation import (
    ValidationResult,
    build_retry_hint,
    validate_generation,
)
from pixel_magic.providers.base import GenerationConfig, GenerationResult, ImageProvider

logger = logging.getLogger(__name__)


class SpriteGenerator:
    """Orchestrates multi-step sprite generation using an AI image provider."""

    def __init__(self, provider: ImageProvider, prompts: PromptBuilder, settings: Settings):
        self._provider = provider
        self._prompts = prompts
        self._settings = settings

    # ── Validated generation helper ───────────────────────────────────

    async def _generate_validated(
        self,
        prompt: str,
        config: GenerationConfig,
        *,
        reference_images: list[Image.Image] | None = None,
        validate: bool = False,
        max_retries: int = 2,
        expected_count: int = 1,
        instructions_summary: str = "",
    ) -> GenerationResult:
        """Generate an image, optionally validating with an LLM check.

        When *validate* is True the result is checked by a lightweight LLM
        judge.  If the check fails the image is regenerated (up to
        *max_retries* additional attempts) with corrective hints appended
        to the prompt.
        """
        if reference_images:
            result = await self._provider.generate_with_references(prompt, reference_images, config)
        else:
            result = await self._provider.generate(prompt, config)

        if not validate:
            return result

        for attempt in range(1, max_retries + 1):
            vr = await validate_generation(
                self._provider,
                result.image,
                instructions_summary or prompt[:400],
                expected_count,
            )
            if vr.passed:
                logger.info("Validation passed on attempt %d", attempt)
                result.metadata["validation"] = vr.to_dict()
                return result

            logger.warning(
                "Validation failed (attempt %d/%d): %s",
                attempt, max_retries, vr.feedback,
            )
            retry_hint = build_retry_hint(vr)
            retry_prompt = f"{prompt}\n\n--- CORRECTION ---\n{retry_hint}"

            if reference_images:
                result = await self._provider.generate_with_references(
                    retry_prompt, reference_images, config
                )
            else:
                result = await self._provider.generate(retry_prompt, config)

        # Final attempt — no more retries, return whatever we got
        result.metadata["validation"] = {"passed": False, "exhausted_retries": True}
        return result

    # ── Character generation ──────────────────────────────────────────

    async def generate_character(
        self,
        spec: CharacterSpec,
        output_dir: Path | None = None,
        *,
        validate: bool = False,
        max_retries: int = 2,
    ) -> dict[str, list[AnimationClip]]:
        """Generate a complete character sprite set with all directions and animations.

        Returns a dict mapping animation_name → list of AnimationClip (one per direction).
        """
        out = output_dir or self._settings.output_dir / "raw" / spec.name
        out.mkdir(parents=True, exist_ok=True)

        # Step 1: Generate base directions (idle pose) — all directions in one composite
        unique_dirs = Direction.unique_for_mode(spec.direction_mode)
        logger.info(
            "Generating base directions for '%s' (%d unique directions)",
            spec.name, len(unique_dirs),
        )

        dir_template = (
            "character_directions_4dir"
            if spec.direction_mode == DirectionMode.FOUR
            else "character_directions_8dir"
        )

        dir_names_str = ", ".join(d.value for d in unique_dirs)
        prompt = self._prompts.render(
            dir_template,
            character_description=spec.description,
            style=spec.style,
            resolution=spec.resolution,
            max_colors=str(spec.max_colors),
            palette_hint=spec.palette_hint,
            direction_count=str(len(unique_dirs)),
            direction_names=dir_names_str,
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            validate=validate,
            max_retries=max_retries,
            expected_count=len(unique_dirs),
            instructions_summary=(
                f"{len(unique_dirs)} idle-pose direction sprites for: {spec.description}"
            ),
        )

        # Extract individual direction frames
        dir_frames = extract_frames(
            result.image, CompositeLayout.HORIZONTAL_STRIP, len(unique_dirs)
        )
        dir_frames = normalize_frame_sizes(dir_frames)

        # Save raw composite for debug
        result.image.save(out / "base_directions_raw.png")

        # Map directions to their idle frames (used as references later)
        direction_refs: dict[Direction, Image.Image] = {}
        for i, direction in enumerate(unique_dirs):
            direction_refs[direction] = dir_frames[i]
            dir_frames[i].save(out / f"idle_{direction.value}.png")

        # Step 2: Generate each animation for each unique direction
        all_clips: dict[str, list[AnimationClip]] = {}

        for anim_name, anim_def in spec.animations.items():
            logger.info("Generating animation '%s' (%d frames)", anim_name, anim_def.frame_count)
            clips_for_anim = []

            for direction in unique_dirs:
                clip = await self._generate_animation_clip(
                    spec=spec,
                    anim_def=anim_def,
                    direction=direction,
                    reference_image=direction_refs[direction],
                    output_dir=out,
                    validate=validate,
                    max_retries=max_retries,
                )
                clips_for_anim.append(clip)

            all_clips[anim_name] = clips_for_anim

        # Step 3: Create idle clips from the direction images
        idle_clips = []
        for direction in unique_dirs:
            idle_asset = SpriteAsset(
                image=direction_refs[direction],
                direction=direction,
                animation_name="idle",
                frame_index=0,
            )
            clip = AnimationClip(
                name="idle",
                direction=direction,
                frames=[idle_asset],
                duration_ms=spec.animations.get("idle", AnimationDef("idle", 1, "", 150)).duration_ms,
                is_looping=True,
            )
            idle_clips.append(clip)

        # If "idle" was also specified as multi-frame animation, it was already generated above
        if "idle" not in all_clips:
            all_clips["idle"] = idle_clips

        return all_clips

    async def _generate_animation_clip(
        self,
        spec: CharacterSpec,
        anim_def: AnimationDef,
        direction: Direction,
        reference_image: Image.Image,
        output_dir: Path,
        validate: bool = False,
        max_retries: int = 2,
    ) -> AnimationClip:
        """Generate all frames for one animation in one direction as a composite."""
        prompt = self._prompts.render(
            "character_animation",
            character_description=spec.description,
            style=spec.style,
            resolution=spec.resolution,
            max_colors=str(spec.max_colors),
            palette_hint=spec.palette_hint,
            animation_name=anim_def.name,
            animation_description=anim_def.description,
            frame_count=str(anim_def.frame_count),
            direction=direction.value,
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            reference_images=[reference_image],
            validate=validate,
            max_retries=max_retries,
            expected_count=anim_def.frame_count,
            instructions_summary=(
                f"{anim_def.frame_count}-frame '{anim_def.name}' animation "
                f"facing {direction.value} for: {spec.description}"
            ),
        )

        # Extract frames from composite strip
        frames_imgs = extract_frames(
            result.image, CompositeLayout.HORIZONTAL_STRIP, anim_def.frame_count
        )
        frames_imgs = normalize_frame_sizes(frames_imgs)

        # Save raw composite
        result.image.save(
            output_dir / f"{anim_def.name}_{direction.value}_raw.png"
        )

        # Build SpriteAsset list
        sprite_frames = []
        for i, img in enumerate(frames_imgs):
            asset = SpriteAsset(
                image=img,
                direction=direction,
                animation_name=anim_def.name,
                frame_index=i,
            )
            img.save(output_dir / f"{anim_def.name}_{direction.value}_{i:03d}.png")
            sprite_frames.append(asset)

        return AnimationClip(
            name=anim_def.name,
            direction=direction,
            frames=sprite_frames,
            duration_ms=anim_def.duration_ms,
            is_looping=anim_def.is_looping,
        )

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

        clips = []
        for direction in unique_dirs:
            prompt = self._prompts.render(
                "character_custom_animation",
                animation_name=anim_def.name,
                animation_description=anim_def.description,
                frame_count=str(anim_def.frame_count),
                direction=direction.value,
                style=style,
                resolution=resolution,
                max_colors=str(max_colors),
            )

            config = GenerationConfig(image_size=self._settings.image_size)
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

    # ── Tileset generation ────────────────────────────────────────────

    async def generate_tileset(
        self, spec: TilesetSpec, output_dir: Path | None = None,
        *, validate: bool = False, max_retries: int = 2,
    ) -> list[SpriteAsset]:
        """Generate an isometric tileset — all tiles in one composite."""
        out = output_dir or self._settings.output_dir / "raw" / spec.name
        out.mkdir(parents=True, exist_ok=True)

        tile_types_str = ", ".join(spec.tile_types)
        prompt = self._prompts.render(
            "tileset_ground",
            biome=spec.biome,
            tile_types=tile_types_str,
            tile_width=str(spec.tile_width),
            tile_height=str(spec.tile_height),
            count=str(len(spec.tile_types)),
            style=spec.style,
            max_colors=str(spec.max_colors),
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            validate=validate,
            max_retries=max_retries,
            expected_count=len(spec.tile_types),
            instructions_summary=(
                f"{len(spec.tile_types)} tileset tiles ({tile_types_str}) for {spec.biome}"
            ),
        )
        result.image.save(out / "tileset_raw.png")

        frames = extract_frames(
            result.image, CompositeLayout.AUTO_DETECT, len(spec.tile_types)
        )
        frames = normalize_frame_sizes(frames)

        assets = []
        for i, (img, tile_type) in enumerate(zip(frames, spec.tile_types)):
            asset = SpriteAsset(image=img, animation_name=tile_type, frame_index=i)
            img.save(out / f"tile_{tile_type}_{i:03d}.png")
            assets.append(asset)

        return assets

    # ── Item generation ───────────────────────────────────────────────

    async def generate_items(
        self, spec: ItemSpec, output_dir: Path | None = None,
        *, validate: bool = False, max_retries: int = 2,
    ) -> list[SpriteAsset]:
        """Generate item icons in a single composite image."""
        out = output_dir or self._settings.output_dir / "raw" / "items"
        out.mkdir(parents=True, exist_ok=True)

        items_str = ", ".join(spec.descriptions)
        prompt = self._prompts.render(
            "item_icons_batch",
            item_descriptions=items_str,
            count=str(len(spec.descriptions)),
            resolution=spec.resolution,
            style=spec.style,
            max_colors=str(spec.max_colors),
            view=spec.view,
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            validate=validate,
            max_retries=max_retries,
            expected_count=len(spec.descriptions),
            instructions_summary=(
                f"{len(spec.descriptions)} item icons: {items_str}"
            ),
        )
        result.image.save(out / "items_raw.png")

        frames = extract_frames(
            result.image, CompositeLayout.AUTO_DETECT, len(spec.descriptions)
        )
        frames = normalize_frame_sizes(frames)

        assets = []
        for i, (img, desc) in enumerate(zip(frames, spec.descriptions)):
            name = desc.lower().replace(" ", "_")[:30]
            asset = SpriteAsset(image=img, animation_name=name, frame_index=i)
            img.save(out / f"item_{name}_{i:03d}.png")
            assets.append(asset)

        return assets

    # ── Effect generation ─────────────────────────────────────────────

    async def generate_effect(
        self, spec: EffectSpec, output_dir: Path | None = None,
        *, validate: bool = False, max_retries: int = 2,
    ) -> AnimationClip:
        """Generate an animated effect — all frames in a horizontal strip."""
        out = output_dir or self._settings.output_dir / "raw" / "effects"
        out.mkdir(parents=True, exist_ok=True)

        prompt = self._prompts.render(
            "effect_animation",
            effect_description=spec.description,
            frame_count=str(spec.frame_count),
            resolution=spec.resolution,
            style=spec.style,
            max_colors=str(spec.max_colors),
            color_emphasis=spec.color_emphasis,
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            validate=validate,
            max_retries=max_retries,
            expected_count=spec.frame_count,
            instructions_summary=(
                f"{spec.frame_count}-frame effect: {spec.description}"
            ),
        )
        result.image.save(out / "effect_raw.png")

        frames = extract_frames(
            result.image, CompositeLayout.HORIZONTAL_STRIP, spec.frame_count
        )
        frames = normalize_frame_sizes(frames)

        sprite_frames = []
        for i, img in enumerate(frames):
            asset = SpriteAsset(image=img, animation_name="effect", frame_index=i)
            img.save(out / f"effect_{i:03d}.png")
            sprite_frames.append(asset)

        return AnimationClip(
            name="effect",
            direction=Direction.S,
            frames=sprite_frames,
            duration_ms=80,
            is_looping=False,
        )

    # ── UI generation ─────────────────────────────────────────────────

    async def generate_ui_elements(
        self, spec: UIElementSpec, output_dir: Path | None = None,
        *, validate: bool = False, max_retries: int = 2,
    ) -> list[SpriteAsset]:
        """Generate UI elements in a single composite."""
        out = output_dir or self._settings.output_dir / "raw" / "ui"
        out.mkdir(parents=True, exist_ok=True)

        elements_str = ", ".join(spec.descriptions)
        prompt = self._prompts.render(
            "ui_elements_batch",
            element_descriptions=elements_str,
            count=str(len(spec.descriptions)),
            resolution=spec.resolution,
            style=spec.style,
            max_colors=str(spec.max_colors),
        )

        config = GenerationConfig(image_size=self._settings.image_size)
        result = await self._generate_validated(
            prompt, config,
            validate=validate,
            max_retries=max_retries,
            expected_count=len(spec.descriptions),
            instructions_summary=(
                f"{len(spec.descriptions)} UI elements: {elements_str}"
            ),
        )
        result.image.save(out / "ui_raw.png")

        frames = extract_frames(
            result.image, CompositeLayout.AUTO_DETECT, len(spec.descriptions)
        )
        frames = normalize_frame_sizes(frames)

        assets = []
        for i, (img, desc) in enumerate(zip(frames, spec.descriptions)):
            name = desc.lower().replace(" ", "_")[:30]
            asset = SpriteAsset(image=img, animation_name=name, frame_index=i)
            img.save(out / f"ui_{name}_{i:03d}.png")
            assets.append(asset)

        return assets

    # ── Custom/freeform generation ────────────────────────────────────

    async def generate_custom(
        self,
        prompt: str,
        frame_count: int = 1,
        layout: CompositeLayout = CompositeLayout.HORIZONTAL_STRIP,
        output_dir: Path | None = None,
    ) -> list[SpriteAsset]:
        """Freeform generation from a custom prompt."""
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
