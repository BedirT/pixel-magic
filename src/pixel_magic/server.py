"""FastMCP server — all tool definitions for the Pixel Magic pipeline."""

from __future__ import annotations

import base64
import io
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image

from pixel_magic.config import Settings, get_settings, reset_settings
from pixel_magic.generation.orchestrator import SpriteGenerator
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.models.asset import (
    AnimationDef,
    CharacterSpec,
    DEFAULT_ANIMATIONS,
    DirectionMode,
    EffectSpec,
    ItemSpec,
    TilesetSpec,
    UIElementSpec,
)
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.export import export_all
from pixel_magic.pipeline.ingest import normalize_sprite
from pixel_magic.pipeline.palette import extract_adaptive_palette, quantize_image
from pixel_magic.pipeline.cleanup import cleanup_sprite
from pixel_magic.pipeline.consistency import lock_palette_across_clips
from pixel_magic.pipeline.grid import infer_grid
from pixel_magic.pipeline.projection import project_to_grid
from pixel_magic.qa.deterministic import run_deterministic_qa
from pixel_magic.qa.vision import run_vision_qa, build_correction_prompt

logger = logging.getLogger(__name__)


# ── Provider factory ──────────────────────────────────────────────────

def _create_provider(settings: Settings):
    """Create the image provider based on settings."""
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


# ── App state ─────────────────────────────────────────────────────────

class AppState:
    """Shared application state across MCP tools."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = _create_provider(settings)
        self.prompts = PromptBuilder(settings.prompts_dir)
        self.generator = SpriteGenerator(self.provider, self.prompts, settings)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize provider and shared state on startup."""
    settings = get_settings()
    state = AppState(settings)
    try:
        yield state
    finally:
        await state.provider.close()


mcp = FastMCP(
    "Pixel Magic",
    description="AI-powered pixel art sprite generation and conversion pipeline",
    lifespan=lifespan,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _get_state(ctx) -> AppState:
    """Extract AppState from MCP context."""
    return ctx.request_context.lifespan_context


def _image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 PNG string."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _load_palette(settings: Settings, palette_name: str | None = None) -> Palette | None:
    """Load a palette by name from the palettes directory."""
    if not palette_name:
        return None
    path = settings.palettes_dir / f"{palette_name}.hex"
    if path.exists():
        return Palette.from_hex_file(path)
    return None


def _parse_animations(animations_input: dict[str, Any] | None) -> dict[str, AnimationDef]:
    """Parse animation definitions from MCP tool input."""
    if not animations_input:
        return {
            "idle": DEFAULT_ANIMATIONS["idle"],
            "walk": DEFAULT_ANIMATIONS["walk"],
        }

    result = {}
    for name, config in animations_input.items():
        if isinstance(config, str):
            # Reference a default animation by name
            if config in DEFAULT_ANIMATIONS:
                result[name] = DEFAULT_ANIMATIONS[config]
            continue

        if isinstance(config, dict):
            result[name] = AnimationDef(
                name=name,
                frame_count=config.get("frame_count", 4),
                description=config.get("description", name),
                duration_ms=config.get("duration_ms", 100),
                is_looping=config.get("is_looping", True),
            )

    return result or {"idle": DEFAULT_ANIMATIONS["idle"], "walk": DEFAULT_ANIMATIONS["walk"]}


async def _run_pipeline_on_clips(
    clips: dict[str, list],
    settings: Settings,
    palette: Palette | None,
    name: str,
    direction_mode: DirectionMode,
) -> dict[str, str]:
    """Run post-processing pipeline on generated clips and export."""
    # Extract adaptive palette if none provided
    all_frames = []
    for anim_clips in clips.values():
        for clip in anim_clips:
            for frame in clip.frames:
                all_frames.append(frame.image)

    if palette is None and all_frames:
        palette = extract_adaptive_palette(all_frames, settings.palette_size)

    # Quantize if palette available
    if palette:
        for anim_clips in clips.values():
            for clip in anim_clips:
                for i, frame in enumerate(clip.frames):
                    quantized = quantize_image(frame.image, palette)
                    cleaned = cleanup_sprite(
                        quantized,
                        palette.colors,
                        settings.min_island_size,
                        settings.max_hole_size,
                        settings.enforce_outline,
                    )
                    frame.image = cleaned

        # Lock palette
        for anim_clips in clips.values():
            lock_palette_across_clips(anim_clips, palette)

    # Export
    output_dir = settings.output_dir / name
    outputs = export_all(
        clips,
        output_dir,
        name=name,
        direction_mode=direction_mode,
        palette=palette,
        padding=settings.atlas_padding,
        export_pngs=settings.export_individual_pngs,
        export_godot=settings.export_godot_tres,
    )

    return {k: str(v) for k, v in outputs.items()}


# ══════════════════════════════════════════════════════════════════════
#  HIGH-LEVEL GENERATION TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def generate_character(
    ctx,
    character_description: str,
    name: str = "character",
    style: str = "16-bit SNES RPG style",
    direction_mode: int = 4,
    animations: dict | None = None,
    resolution: str = "64x64",
    max_colors: int = 16,
    palette_name: str | None = None,
    palette_hint: str = "",
) -> str:
    """Generate a complete pixel art character sprite set with all directions and animations.

    Args:
        character_description: Detailed description of the character's appearance.
        name: Character name (used for file naming).
        style: Pixel art style description (e.g., "16-bit SNES RPG style").
        direction_mode: 4 (S,E + flips) or 8 (S,SE,E,NE,N + flips) directions.
        animations: Dict of animation definitions. Keys are animation names, values are
            either a preset name string (e.g., "idle", "walk", "attack") or a dict with
            keys: frame_count, description, duration_ms, is_looping.
            Defaults to idle + walk if not specified.
        resolution: Target sprite resolution (e.g., "64x64", "32x32").
        max_colors: Maximum palette colors.
        palette_name: Name of a .hex palette file to use (e.g., "default_16").
        palette_hint: Text hint for color palette (e.g., "warm earth tones").

    Returns:
        JSON string with generation results and output file paths.
    """
    state = _get_state(ctx)

    dir_mode = DirectionMode.FOUR if direction_mode == 4 else DirectionMode.EIGHT
    anim_defs = _parse_animations(animations)

    spec = CharacterSpec(
        name=name,
        description=character_description,
        style=style,
        direction_mode=dir_mode,
        resolution=resolution,
        max_colors=max_colors,
        palette_hint=palette_hint,
        animations=anim_defs,
    )

    palette = _load_palette(state.settings, palette_name)

    # Generate
    clips = await state.generator.generate_character(spec)

    # Pipeline + export
    outputs = await _run_pipeline_on_clips(clips, state.settings, palette, name, dir_mode)

    # QA
    all_frames = []
    for anim_clips in clips.values():
        for clip in anim_clips:
            all_frames.extend([f.image for f in clip.frames])

    qa = run_deterministic_qa(all_frames, palette, state.settings.alpha_policy)

    return json.dumps({
        "status": "success",
        "name": name,
        "directions": direction_mode,
        "animations": list(anim_defs.keys()),
        "total_frames": len(all_frames),
        "outputs": outputs,
        "qa": qa.to_dict(),
    }, indent=2)


@mcp.tool()
async def add_character_animation(
    ctx,
    character_name: str,
    animation_name: str,
    reference_image_path: str,
    frame_count: int = 4,
    description: str = "",
    duration_ms: int = 100,
    is_looping: bool = True,
    direction_mode: int = 4,
    style: str = "16-bit SNES RPG style",
    resolution: str = "64x64",
    max_colors: int = 16,
) -> str:
    """Add a custom animation to an existing character using a reference image.

    Args:
        character_name: Name of the existing character.
        animation_name: Name for the new animation (e.g., "jump", "fishing").
        reference_image_path: Path to a reference image of the character.
        frame_count: Number of animation frames.
        description: Description of the animation motion.
        duration_ms: Duration per frame in milliseconds.
        is_looping: Whether the animation loops.
        direction_mode: 4 or 8 directions.
        style: Pixel art style.
        resolution: Target resolution.
        max_colors: Max palette colors.

    Returns:
        JSON with output paths and QA results.
    """
    state = _get_state(ctx)

    anim_def = AnimationDef(
        name=animation_name,
        frame_count=frame_count,
        description=description or animation_name,
        duration_ms=duration_ms,
        is_looping=is_looping,
    )

    dir_mode = DirectionMode.FOUR if direction_mode == 4 else DirectionMode.EIGHT

    clips = await state.generator.add_character_animation(
        character_name=character_name,
        reference_image_path=Path(reference_image_path),
        anim_def=anim_def,
        direction_mode=dir_mode,
        style=style,
        resolution=resolution,
        max_colors=max_colors,
    )

    # Export individual PNGs
    output_dir = state.settings.output_dir / character_name / animation_name
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for clip in clips:
        for frame in clip.frames:
            dir_name = clip.direction.value if clip.direction else "none"
            fname = f"{animation_name}_{dir_name}_{frame.frame_index:03d}.png"
            p = output_dir / fname
            frame.image.save(p)
            paths.append(str(p))

    return json.dumps({
        "status": "success",
        "character": character_name,
        "animation": animation_name,
        "frames_per_direction": frame_count,
        "directions": direction_mode,
        "output_paths": paths,
    }, indent=2)


@mcp.tool()
async def generate_tileset(
    ctx,
    biome: str,
    tile_types: list[str],
    name: str = "tileset",
    tile_width: int = 64,
    tile_height: int = 32,
    style: str = "16-bit isometric RPG style",
    max_colors: int = 16,
    palette_name: str | None = None,
) -> str:
    """Generate an isometric tileset for a biome.

    Args:
        biome: Biome/environment type (e.g., "forest", "desert", "snow").
        tile_types: List of tile variants to generate (e.g., ["grass", "dirt", "water"]).
        name: Tileset name for file naming.
        tile_width: Tile width in pixels.
        tile_height: Tile height in pixels.
        style: Pixel art style.
        max_colors: Max palette colors.
        palette_name: Optional palette file name.

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)

    spec = TilesetSpec(
        name=name,
        biome=biome,
        tile_types=tile_types,
        tile_width=tile_width,
        tile_height=tile_height,
        style=style,
        max_colors=max_colors,
    )

    palette = _load_palette(state.settings, palette_name)
    assets = await state.generator.generate_tileset(spec)

    output_dir = state.settings.output_dir / name
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    frames = []
    for asset in assets:
        frames.append(asset.image)
        fname = f"{name}_{asset.animation_name}_{asset.frame_index:03d}.png"
        p = output_dir / fname
        asset.image.save(p)
        paths.append(str(p))

    if palette is None and frames:
        palette = extract_adaptive_palette(frames, max_colors)

    return json.dumps({
        "status": "success",
        "name": name,
        "biome": biome,
        "tile_count": len(assets),
        "output_paths": paths,
    }, indent=2)


@mcp.tool()
async def generate_items(
    ctx,
    item_descriptions: list[str],
    resolution: str = "32x32",
    style: str = "16-bit SNES RPG style",
    max_colors: int = 16,
    view: str = "front-facing icon",
    palette_name: str | None = None,
) -> str:
    """Generate pixel art item/pickup sprites in batch.

    Args:
        item_descriptions: List of item descriptions (e.g., ["rusty iron sword", "health potion"]).
        resolution: Icon resolution.
        style: Pixel art style.
        max_colors: Max palette colors.
        view: Viewing angle/perspective.
        palette_name: Optional palette file name.

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)

    spec = ItemSpec(
        descriptions=item_descriptions,
        resolution=resolution,
        style=style,
        max_colors=max_colors,
        view=view,
    )

    assets = await state.generator.generate_items(spec)

    output_dir = state.settings.output_dir / "items"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for asset in assets:
        name_slug = (asset.animation_name or f"item_{asset.frame_index}").replace(" ", "_")
        p = output_dir / f"{name_slug}.png"
        asset.image.save(p)
        paths.append(str(p))

    return json.dumps({
        "status": "success",
        "item_count": len(assets),
        "output_paths": paths,
    }, indent=2)


@mcp.tool()
async def generate_effect(
    ctx,
    effect_description: str,
    frame_count: int = 6,
    resolution: str = "64x64",
    style: str = "16-bit pixel art",
    max_colors: int = 12,
    color_emphasis: str = "",
) -> str:
    """Generate an animated pixel art visual effect (explosion, magic, etc.).

    Args:
        effect_description: Description of the effect.
        frame_count: Number of animation frames.
        resolution: Frame resolution.
        style: Pixel art style.
        max_colors: Max palette colors.
        color_emphasis: Dominant colors (e.g., "fire: orange, red, yellow").

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)

    spec = EffectSpec(
        description=effect_description,
        frame_count=frame_count,
        resolution=resolution,
        style=style,
        max_colors=max_colors,
        color_emphasis=color_emphasis,
    )

    clip = await state.generator.generate_effect(spec)

    output_dir = state.settings.output_dir / "effects"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for frame in clip.frames:
        p = output_dir / f"effect_{frame.frame_index:03d}.png"
        frame.image.save(p)
        paths.append(str(p))

    return json.dumps({
        "status": "success",
        "frame_count": clip.frame_count,
        "output_paths": paths,
    }, indent=2)


@mcp.tool()
async def generate_ui_elements(
    ctx,
    element_descriptions: list[str],
    resolution: str = "64x64",
    style: str = "16-bit RPG UI style",
    max_colors: int = 8,
) -> str:
    """Generate pixel art UI elements in batch.

    Args:
        element_descriptions: List of UI element descriptions.
        resolution: Element resolution.
        style: Pixel art style.
        max_colors: Max palette colors.

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)

    spec = UIElementSpec(
        descriptions=element_descriptions,
        resolution=resolution,
        style=style,
        max_colors=max_colors,
    )

    assets = await state.generator.generate_ui_elements(spec)

    output_dir = state.settings.output_dir / "ui"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for asset in assets:
        name_slug = (asset.animation_name or f"ui_{asset.frame_index}").replace(" ", "_")
        p = output_dir / f"{name_slug}.png"
        asset.image.save(p)
        paths.append(str(p))

    return json.dumps({
        "status": "success",
        "element_count": len(assets),
        "output_paths": paths,
    }, indent=2)


@mcp.tool()
async def generate_custom(
    ctx,
    prompt: str,
    frame_count: int = 1,
    layout: str = "horizontal_strip",
) -> str:
    """Generate pixel art from a custom freeform prompt.

    Args:
        prompt: Your custom generation prompt.
        frame_count: Number of frames to extract from the composite.
        layout: Layout of frames in the composite: horizontal_strip, vertical_strip, grid, auto_detect.

    Returns:
        JSON with output paths.
    """
    from pixel_magic.models.asset import CompositeLayout

    state = _get_state(ctx)

    layout_enum = CompositeLayout(layout)
    assets = await state.generator.generate_custom(prompt, frame_count, layout_enum)

    output_dir = state.settings.output_dir / "custom"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for asset in assets:
        p = output_dir / f"custom_{asset.frame_index:03d}.png"
        asset.image.save(p)
        paths.append(str(p))

    return json.dumps({
        "status": "success",
        "frame_count": len(assets),
        "output_paths": paths,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  PIPELINE TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def convert_image(
    ctx,
    image_path: str,
    target_resolution: str | None = None,
    palette_name: str | None = None,
    max_colors: int = 16,
    alpha_policy: str = "binary",
    remove_bg: bool = False,
) -> str:
    """Convert any image through the pixel art pipeline.

    Takes an input image and processes it through grid inference, projection,
    palette quantization, and cleanup to produce a clean pixel art sprite.

    Args:
        image_path: Path to the input image.
        target_resolution: Optional target resolution (e.g., "64x64"). If provided, grid is inferred from this.
        palette_name: Optional palette name to use.
        max_colors: Number of colors for adaptive palette.
        alpha_policy: "binary" or "keep8bit".
        remove_bg: Whether to remove solid-color background.

    Returns:
        JSON with output path and pipeline details.
    """
    state = _get_state(ctx)
    settings = state.settings

    # Ingest
    img = normalize_sprite(
        Path(image_path),
        alpha_policy=alpha_policy,
        alpha_threshold=settings.alpha_threshold,
        remove_bg=remove_bg,
    )

    # Grid inference
    target_res = None
    if target_resolution:
        parts = target_resolution.lower().split("x")
        if len(parts) == 2:
            target_res = (int(parts[0]), int(parts[1]))

    grid = infer_grid(img, (settings.grid_range_min, settings.grid_range_max), target_res)

    # Projection
    projected = img
    if grid.macro_size > 1:
        projected = project_to_grid(img, grid.macro_size, grid.offset_x, grid.offset_y)

    # Palette
    palette = _load_palette(settings, palette_name)
    if palette is None:
        palette = extract_adaptive_palette([projected], max_colors)

    quantized = quantize_image(projected, palette)

    # Cleanup
    cleaned = cleanup_sprite(
        quantized,
        palette.colors,
        settings.min_island_size,
        settings.max_hole_size,
        settings.enforce_outline,
    )

    # Save
    output_dir = settings.output_dir / "converted"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem
    output_path = output_dir / f"{stem}_pixel.png"
    cleaned.save(output_path)

    return json.dumps({
        "status": "success",
        "output_path": str(output_path),
        "grid": {"macro_size": grid.macro_size, "confidence": grid.confidence},
        "palette_size": palette.size,
        "resolution": f"{cleaned.width}x{cleaned.height}",
    }, indent=2)


@mcp.tool()
async def process_sprite_sheet(
    ctx,
    image_path: str,
    frame_count: int | None = None,
    layout: str = "auto_detect",
    palette_name: str | None = None,
    max_colors: int = 16,
    name: str = "sheet",
) -> str:
    """Process an existing sprite sheet through the cleanup pipeline.

    Args:
        image_path: Path to the sprite sheet image.
        frame_count: Expected number of frames (helps extraction).
        layout: Frame layout: horizontal_strip, vertical_strip, grid, auto_detect.
        palette_name: Optional palette name.
        max_colors: Palette size for adaptive mode.
        name: Asset name for exports.

    Returns:
        JSON with output paths and QA results.
    """
    from pixel_magic.generation.extractor import extract_frames, normalize_frame_sizes
    from pixel_magic.models.asset import CompositeLayout

    state = _get_state(ctx)
    settings = state.settings

    img = normalize_sprite(Path(image_path))
    layout_enum = CompositeLayout(layout)

    frames = extract_frames(img, layout_enum, frame_count)
    frames = normalize_frame_sizes(frames)

    # Palette
    palette = _load_palette(settings, palette_name)
    if palette is None:
        palette = extract_adaptive_palette(frames, max_colors)

    processed = []
    for f in frames:
        q = quantize_image(f, palette)
        c = cleanup_sprite(q, palette.colors)
        processed.append(c)

    # Save
    output_dir = settings.output_dir / name
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, f in enumerate(processed):
        p = output_dir / f"{name}_{i:03d}.png"
        f.save(p)
        paths.append(str(p))

    qa = run_deterministic_qa(processed, palette)

    return json.dumps({
        "status": "success",
        "frame_count": len(processed),
        "output_paths": paths,
        "qa": qa.to_dict(),
    }, indent=2)


@mcp.tool()
async def extract_frames_tool(
    ctx,
    image_path: str,
    frame_count: int | None = None,
    layout: str = "auto_detect",
) -> str:
    """Extract individual frames from a composite/sheet image.

    Args:
        image_path: Path to the composite image.
        frame_count: Expected number of frames.
        layout: Frame layout: horizontal_strip, vertical_strip, grid, auto_detect.

    Returns:
        JSON with extracted frame paths.
    """
    from pixel_magic.generation.extractor import extract_frames, normalize_frame_sizes
    from pixel_magic.models.asset import CompositeLayout

    state = _get_state(ctx)
    settings = state.settings

    img = Image.open(image_path).convert("RGBA")
    layout_enum = CompositeLayout(layout)

    frames = extract_frames(img, layout_enum, frame_count)
    frames = normalize_frame_sizes(frames)

    output_dir = settings.output_dir / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, f in enumerate(frames):
        p = output_dir / f"frame_{i:03d}.png"
        f.save(p)
        paths.append(str(p))

    return json.dumps({
        "status": "success",
        "frame_count": len(frames),
        "output_paths": paths,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  QA TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def run_qa_check(
    ctx,
    image_paths: list[str],
    palette_name: str | None = None,
    alpha_policy: str = "binary",
    run_vision: bool = False,
) -> str:
    """Run QA checks on one or more sprite images.

    Args:
        image_paths: List of image file paths to check.
        palette_name: Optional palette name for palette compliance check.
        alpha_policy: "binary" or "keep8bit".
        run_vision: Whether to also run AI vision QA (costs API credits).

    Returns:
        JSON QA report.
    """
    state = _get_state(ctx)
    settings = state.settings

    frames = [Image.open(p).convert("RGBA") for p in image_paths]
    palette = _load_palette(settings, palette_name)

    report = run_deterministic_qa(frames, palette, alpha_policy)

    if run_vision and settings.qa_vision_enabled:
        vision_report = await run_vision_qa(
            state.provider, frames, min_score=settings.qa_min_vision_score
        )
        report.checks.extend(vision_report.checks)

    return json.dumps(report.to_dict(), indent=2)


# ══════════════════════════════════════════════════════════════════════
#  UTILITY TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def list_palettes(ctx) -> str:
    """List all available color palettes.

    Returns:
        JSON list of palette names and their colors.
    """
    state = _get_state(ctx)
    palettes_dir = state.settings.palettes_dir

    result = []
    if palettes_dir.exists():
        for f in sorted(palettes_dir.glob("*.hex")):
            pal = Palette.from_hex_file(f)
            result.append({
                "name": pal.name,
                "size": pal.size,
                "colors": pal.to_hex_list()[:8],  # Preview first 8
                "path": str(f),
            })

    return json.dumps(result, indent=2)


@mcp.tool()
async def list_animations(ctx) -> str:
    """List available animation presets.

    Returns:
        JSON of default animation definitions.
    """
    result = {}
    for name, adef in DEFAULT_ANIMATIONS.items():
        result[name] = {
            "frame_count": adef.frame_count,
            "description": adef.description,
            "duration_ms": adef.duration_ms,
            "is_looping": adef.is_looping,
        }

    return json.dumps(result, indent=2)


@mcp.tool()
async def list_prompt_templates(ctx) -> str:
    """List all available prompt templates and their parameters.

    Returns:
        JSON list of template names, descriptions, and parameter lists.
    """
    state = _get_state(ctx)

    templates = state.prompts.list_templates()
    result = []
    for t in templates:
        result.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": list(t["parameters"].keys()) if t.get("parameters") else [],
            "reference_strategy": t.get("reference_strategy", ""),
        })

    return json.dumps(result, indent=2)


@mcp.tool()
async def set_provider(ctx, provider: str) -> str:
    """Switch between AI providers.

    Args:
        provider: "gemini" or "openai".

    Returns:
        Confirmation message.
    """
    if provider not in ("gemini", "openai"):
        return json.dumps({"error": f"Unknown provider: {provider}. Use 'gemini' or 'openai'."})

    state = _get_state(ctx)

    # Close old provider
    await state.provider.close()

    # Update settings
    state.settings.provider = provider
    state.provider = _create_provider(state.settings)
    state.generator = SpriteGenerator(state.provider, state.prompts, state.settings)

    return json.dumps({"status": "success", "provider": provider})


@mcp.tool()
async def set_style_defaults(
    ctx,
    direction_mode: int | None = None,
    resolution: str | None = None,
    palette_size: int | None = None,
    alpha_policy: str | None = None,
) -> str:
    """Set default style parameters for future generations.

    Args:
        direction_mode: 4 or 8 directions.
        resolution: Default sprite resolution (e.g., "64x64").
        palette_size: Default max palette colors.
        alpha_policy: "binary" or "keep8bit".

    Returns:
        Updated settings.
    """
    state = _get_state(ctx)

    if direction_mode is not None:
        state.settings.direction_mode = direction_mode
    if resolution is not None:
        state.settings.default_resolution = resolution
    if palette_size is not None:
        state.settings.palette_size = palette_size
    if alpha_policy is not None:
        state.settings.alpha_policy = alpha_policy

    return json.dumps({
        "status": "success",
        "direction_mode": state.settings.direction_mode,
        "resolution": state.settings.default_resolution,
        "palette_size": state.settings.palette_size,
        "alpha_policy": state.settings.alpha_policy,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  EVALUATION TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def run_evaluation(
    ctx,
    variant_label: str = "default",
    case_names: list[str] | None = None,
    repeats: int = 1,
) -> str:
    """Run the LLM-as-judge evaluation on standard test cases.

    Generates pixel art for each test case and evaluates quality using
    structured rubrics. Results are saved to output/eval/<variant_label>/.

    Args:
        variant_label: Label for this evaluation run (e.g., "gemini_v1", "openai_baseline").
        case_names: Optional list of specific case names to run. Runs all if omitted.
        repeats: Number of times to repeat each case (for statistical significance).

    Returns:
        JSON summary with per-case scores and aggregate statistics.
    """
    from pixel_magic.evaluation.cases import get_standard_cases
    from pixel_magic.evaluation.metrics import aggregate_results
    from pixel_magic.evaluation.runner import EvalRunner

    state = _get_state(ctx)
    runner = EvalRunner(state.provider, state.prompts, state.settings)

    cases = get_standard_cases()
    if case_names:
        cases = [c for c in cases if c.name in case_names]

    run = await runner.run_all(cases, variant_label=variant_label, repeats=repeats)
    agg = aggregate_results(run.results, variant_label)

    return json.dumps({
        "status": "success",
        "variant": variant_label,
        "total_cases": agg.total_runs,
        "errors": agg.error_count,
        "overall_mean": round(agg.overall_mean, 3),
        "overall_pass_rate": round(agg.overall_pass_rate, 3),
        "dimensions": {k: round(v.mean, 3) for k, v in agg.dimensions.items()},
        "results_path": str(state.settings.output_dir / "eval" / variant_label / "results.json"),
    }, indent=2)


@mcp.tool()
async def compare_evaluations(
    ctx,
    run_paths: list[str],
) -> str:
    """Compare multiple evaluation runs and generate a scientific report.

    Args:
        run_paths: List of paths to evaluation results.json files.

    Returns:
        Markdown comparison report with statistical analysis.
    """
    from pixel_magic.evaluation.report import generate_report
    from pixel_magic.evaluation.runner import EvalRun

    state = _get_state(ctx)

    runs = [EvalRun.load(Path(p)) for p in run_paths]
    report_dir = state.settings.output_dir / "eval" / "comparison"
    md = generate_report(runs, output_dir=report_dir)

    return md


@mcp.tool()
async def list_eval_cases(ctx) -> str:
    """List all available evaluation test cases.

    Returns:
        JSON list of test case definitions.
    """
    from pixel_magic.evaluation.cases import get_standard_cases

    cases = get_standard_cases()
    return json.dumps([c.to_dict() for c in cases], indent=2)
