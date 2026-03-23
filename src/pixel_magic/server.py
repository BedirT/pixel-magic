"""FastMCP server — all tool definitions for the Pixel Magic pipeline."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from PIL import Image

from pixel_magic.config import Settings, get_settings
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.models.asset import DEFAULT_ANIMATIONS
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.cleanup import cleanup_sprite
from pixel_magic.pipeline.grid import infer_grid
from pixel_magic.pipeline.ingest import normalize_sprite
from pixel_magic.pipeline.palette import extract_adaptive_palette, quantize_image
from pixel_magic.pipeline.projection import project_to_grid
from pixel_magic.qa.deterministic import run_deterministic_qa
from pixel_magic.qa.vision import run_vision_qa
from pixel_magic.workflow import (
    AgentRuntime,
    AssetType,
    GenerationRequest,
    JobResult,
    ProviderAdapter,
    WorkflowExecutor,
    create_provider,
)

logger = logging.getLogger(__name__)


# ── Provider factory ──────────────────────────────────────────────────

def _create_provider(settings: Settings):
    """Create the image provider based on settings."""
    return create_provider(settings)


# ── App state ─────────────────────────────────────────────────────────

class AppState:
    """Shared application state across MCP tools."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = _create_provider(settings)
        self.provider_adapter = ProviderAdapter(self.provider, settings)
        self.workflow_agents = AgentRuntime(
            model=settings.agent_model,
            api_key=settings.openai_api_key,
            provider=settings.provider,
            chromakey_color=settings.chromakey_color,
        )
        self.workflow_executor = WorkflowExecutor(
            settings=settings,
            provider=self.provider_adapter,
            agents=self.workflow_agents,
        )
        self.prompts = PromptBuilder(settings.prompts_dir)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize provider and shared state on startup."""
    from pixel_magic.tracing import init_tracing

    init_tracing()

    settings = get_settings()
    state = AppState(settings)
    try:
        yield state
    finally:
        await state.provider.close()


mcp = FastMCP(
    "Pixel Magic",
    instructions="AI-powered pixel art sprite generation and conversion pipeline",
    lifespan=lifespan,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _get_state(ctx) -> AppState:
    """Extract AppState from MCP context."""
    return ctx.request_context.lifespan_context


def _load_palette(settings: Settings, palette_name: str | None = None) -> Palette | None:
    """Load a palette by name from the palettes directory."""
    if not palette_name:
        return None
    path = settings.palettes_dir / f"{palette_name}.hex"
    if path.exists():
        return Palette.from_hex_file(path)
    return None


def _flatten_frame_paths(frame_paths: dict[str, list[str]]) -> list[str]:
    paths: list[str] = []
    for key in sorted(frame_paths):
        paths.extend(frame_paths[key])
    return paths


def _serialize_workflow_result(result: JobResult, *, deprecation_note: str = "") -> str:
    payload = result.model_dump(mode="json", exclude_none=True)
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, dict):
        frame_paths = artifacts.get("frame_paths", {})
        payload["output_paths"] = _flatten_frame_paths(frame_paths)
        payload["output_dir"] = artifacts.get("output_dir")
    if deprecation_note:
        payload.setdefault("warnings", [])
        payload["warnings"].append(deprecation_note)
    return json.dumps(payload, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  HIGH-LEVEL GENERATION TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def generate_character(
    ctx: Context,
    character_description: str,
    name: str = "character",
    style: str = "16-bit SNES RPG style",
    palette_hint: str = "",
) -> str:
    """Generate a pixel art character sprite with 4 isometric directions.

    Generates 2 direction poses (SE, NE) and mirrors them to get all 4 directions.

    Args:
        character_description: Detailed description of the character's appearance.
        name: Character name (used for file naming).
        style: Pixel art style description (e.g., "16-bit SNES RPG style").
        palette_hint: Text hint for color palette (e.g., "warm earth tones").

    Returns:
        JSON string with generation results and output file paths.
    """
    state = _get_state(ctx)
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name=name,
        objective=character_description,
        style=style,
        resolution="64x64",
        max_colors=16,
        parameters={
            "direction_mode": 4,
            "palette_hint": palette_hint,
        },
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def extend_character_animation(
    ctx: Context,
    character_name: str,
    animation_name: str,
    reference_image_path: str,
    frame_count: int = 4,
    description: str = "",
    duration_ms: int = 100,
    is_looping: bool = True,
    direction_mode: Literal[4, 8] = 4,
    style: str = "16-bit SNES RPG style",
    resolution: str = "64x64",
    max_colors: int = 16,
    palette_name: str | None = None,
) -> str:
    """Create a new animation for an existing character design from a reference image.

    Args:
        character_name: Existing character identity for naming and metadata.
        animation_name: Animation name (e.g., "jump", "fishing", "cast").
        reference_image_path: Filesystem path to a reference sprite image.
        frame_count: Number of animation frames.
        description: Motion description for the target animation.
        duration_ms: Duration per frame in milliseconds.
        is_looping: Whether the animation loops.
        direction_mode: 4 or 8 directional generation mode.
        style: Pixel art style string.
        resolution: Per-frame output resolution (e.g., 64x64).
        max_colors: Max color count for quantization.
        palette_name: Optional named palette.

    Returns:
        Workflow JobResult JSON plus flattened output_paths.
    """
    state = _get_state(ctx)
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name=f"{character_name}_{animation_name}",
        objective=(
            f"Extend character '{character_name}' with animation '{animation_name}'. "
            f"Animation brief: {description or animation_name}."
        ),
        style=style,
        resolution=resolution,
        max_colors=max_colors,
        expected_frames=frame_count,
        palette_name=palette_name,
        parameters={
            "extension_mode": True,
            "character_name": character_name,
            "animation_name": animation_name,
            "direction_mode": direction_mode,
            "reference_image_path": reference_image_path,
            "external_reference_paths": [reference_image_path],
            "animations": {
                animation_name: {
                    "frame_count": frame_count,
                    "description": description or animation_name,
                    "duration_ms": duration_ms,
                    "is_looping": is_looping,
                }
            },
        },
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def generate_tileset(
    ctx: Context,
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
    request = GenerationRequest(
        asset_type=AssetType.TILESET,
        name=name,
        objective=f"{biome} isometric tileset",
        style=style,
        resolution=f"{tile_width}x{tile_height}",
        max_colors=max_colors,
        expected_frames=max(1, len(tile_types)),
        palette_name=palette_name,
        parameters={
            "biome": biome,
            "tile_types": tile_types,
            "tile_width": tile_width,
            "tile_height": tile_height,
        },
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def generate_items(
    ctx: Context,
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
    request = GenerationRequest(
        asset_type=AssetType.ITEMS,
        name="items",
        objective=f"Item icon set: {', '.join(item_descriptions)}",
        style=style,
        resolution=resolution,
        max_colors=max_colors,
        expected_frames=max(1, len(item_descriptions)),
        palette_name=palette_name,
        parameters={
            "descriptions": item_descriptions,
            "view": view,
        },
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def generate_effect(
    ctx: Context,
    effect_description: str,
    frame_count: int = 6,
    resolution: str = "64x64",
    style: str = "16-bit pixel art",
    max_colors: int = 12,
    color_emphasis: str = "",
    perspective: str = "isometric",
) -> str:
    """Generate an animated pixel art visual effect (explosion, magic, etc.).

    Args:
        effect_description: Description of the effect.
        frame_count: Number of animation frames.
        resolution: Frame resolution.
        style: Pixel art style.
        max_colors: Max palette colors.
        color_emphasis: Dominant colors (e.g., "fire: orange, red, yellow").
        perspective: Perspective style ("isometric" or "flat").

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)
    request = GenerationRequest(
        asset_type=AssetType.EFFECT,
        name="effects",
        objective=effect_description,
        style=style,
        resolution=resolution,
        max_colors=max_colors,
        expected_frames=frame_count,
        parameters={
            "frame_count": frame_count,
            "color_emphasis": color_emphasis,
            "perspective": perspective,
        },
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def generate_ui_elements(
    ctx: Context,
    element_descriptions: list[str],
    resolution: str = "160x128",
    style: str = "16-bit RPG UI style",
    max_colors: int = 16,
) -> str:
    """Generate pixel art UI elements in batch.

    Args:
        element_descriptions: List of UI element descriptions.
        resolution: Element resolution (default 160x128 for more usable panel space).
        style: Pixel art style.
        max_colors: Max palette colors.

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)
    request = GenerationRequest(
        asset_type=AssetType.UI,
        name="ui",
        objective=f"UI element set: {', '.join(element_descriptions)}",
        style=style,
        resolution=resolution,
        max_colors=max_colors,
        expected_frames=max(1, len(element_descriptions)),
        parameters={"descriptions": element_descriptions},
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


@mcp.tool()
async def generate_custom(
    ctx: Context,
    prompt: str,
    frame_count: int = 1,
    layout: Literal["horizontal_strip", "vertical_strip", "grid", "auto_detect"] = "horizontal_strip",
    style: str = "16-bit pixel art",
    resolution: str = "64x64",
    max_colors: int = 16,
    perspective: str = "isometric",
) -> str:
    """Generate pixel art from a custom freeform prompt.

    Args:
        prompt: Your custom generation prompt.
        frame_count: Number of frames to extract from the composite.
        layout: Layout of frames in the composite:
            horizontal_strip, vertical_strip, grid, auto_detect.
        style: Pixel art style.
        resolution: Sprite resolution.
        max_colors: Max palette colors.
        perspective: Perspective style ("isometric" or "flat").

    Returns:
        JSON with output paths.
    """
    state = _get_state(ctx)
    request = GenerationRequest(
        asset_type=AssetType.CUSTOM,
        name="custom",
        objective=prompt,
        style=style,
        resolution=resolution,
        max_colors=max_colors,
        expected_frames=frame_count,
        layout=layout,
        parameters={"perspective": perspective},
    )
    result = await state.workflow_executor.run(request)
    return _serialize_workflow_result(result)


# ══════════════════════════════════════════════════════════════════════
#  PIPELINE TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def convert_image(
    ctx: Context,
    image_path: str,
    target_resolution: str | None = None,
    palette_name: str | None = None,
    max_colors: int = 16,
    alpha_policy: Literal["binary", "keep8bit"] = "binary",
    remove_bg: bool = False,
) -> str:
    """Convert any image through the pixel art pipeline.

    Takes an input image and processes it through grid inference, projection,
    palette quantization, and cleanup to produce a clean pixel art sprite.

    Args:
        image_path: Path to the input image.
        target_resolution: Optional target resolution (e.g., "64x64").
            If provided, grid is inferred from this.
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
    ctx: Context,
    image_path: str,
    frame_count: int | None = None,
    layout: Literal["horizontal_strip", "vertical_strip", "grid", "auto_detect"] = "auto_detect",
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
    ctx: Context,
    image_path: str,
    frame_count: int | None = None,
    layout: Literal["horizontal_strip", "vertical_strip", "grid", "auto_detect"] = "auto_detect",
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
    ctx: Context,
    image_paths: list[str],
    palette_name: str | None = None,
    alpha_policy: Literal["binary", "keep8bit"] = "binary",
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
async def list_palettes(ctx: Context) -> str:
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
async def list_animations(ctx: Context) -> str:
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
async def list_prompt_templates(ctx: Context) -> str:
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
async def set_provider(ctx: Context, provider: Literal["gemini", "openai"]) -> str:
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
    state.provider_adapter = ProviderAdapter(state.provider, state.settings)
    state.workflow_agents = AgentRuntime(
        model=state.settings.agent_model,
        api_key=state.settings.openai_api_key,
        provider=state.settings.provider,
        chromakey_color=state.settings.chromakey_color,
    )
    state.workflow_executor = WorkflowExecutor(
        settings=state.settings,
        provider=state.provider_adapter,
        agents=state.workflow_agents,
    )

    return json.dumps({"status": "success", "provider": provider})


@mcp.tool()
async def set_style_defaults(
    ctx: Context,
    direction_mode: Literal[4, 8] | None = None,
    resolution: str | None = None,
    palette_size: int | None = None,
    alpha_policy: Literal["binary", "keep8bit"] | None = None,
    chromakey_color: Literal["green", "blue"] | None = None,
) -> str:
    """Set default style parameters for future generations.

    Args:
        direction_mode: 4 or 8 directions.
        resolution: Default sprite resolution (e.g., "64x64").
        palette_size: Default max palette colors.
        alpha_policy: "binary" or "keep8bit".
        chromakey_color: Chromakey background color for Gemini provider.
            "green" (default) or "blue" (for green-heavy sprites).

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
    if chromakey_color is not None:
        state.settings.chromakey_color = chromakey_color

    return json.dumps({
        "status": "success",
        "direction_mode": state.settings.direction_mode,
        "resolution": state.settings.default_resolution,
        "palette_size": state.settings.palette_size,
        "alpha_policy": state.settings.alpha_policy,
        "chromakey_color": state.settings.chromakey_color,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  EVALUATION TOOLS
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
async def run_evaluation(
    ctx: Context,
    variant_label: str = "default",
    case_names: list[str] | None = None,
    repeats: int = 1,
    mode: Literal["direct", "agent"] = "direct",
) -> str:
    """Run the LLM-as-judge evaluation on standard test cases.

    Generates pixel art for each test case and evaluates quality using
    structured rubrics. Results are saved to output/eval/<variant_label>/.

    Args:
        variant_label: Label for this evaluation run (e.g., "gemini_v1", "openai_baseline").
        case_names: Optional list of specific case names to run. Runs all if omitted.
        repeats: Number of times to repeat each case (for statistical significance).
        mode: "direct" uses PromptBuilder+provider (fast), "agent" uses the full agent pipeline.

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

    eval_mode = "agent" if mode == "agent" else "direct"
    run = await runner.run_all(
        cases, variant_label=variant_label, repeats=repeats, mode=eval_mode,
    )
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
    ctx: Context,
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
async def list_eval_cases(ctx: Context) -> str:
    """List all available evaluation test cases.

    Returns:
        JSON list of test case definitions.
    """
    from pixel_magic.evaluation.cases import get_standard_cases

    cases = get_standard_cases()
    return json.dumps([c.to_dict() for c in cases], indent=2)
