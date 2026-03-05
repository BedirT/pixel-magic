"""Shared function tools available to all specialist agents."""

from __future__ import annotations

import asyncio
import logging

from PIL import Image

from agents import RunContextWrapper, function_tool

from pixel_magic.agents.context import AgentContext
from pixel_magic.generation.extractor import (
    CompositeLayout,
    extract_frames,
    normalize_frame_sizes,
    _prepare_composite,
    _run_component_detection,
)
from pixel_magic.providers.base import GenerationConfig
from pixel_magic.qa.deterministic import (
    check_alpha_compliance,
    check_island_noise,
)

from pixel_magic.tracing import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("pixel_magic.agents.tools")

# Extra retry delay for rate-limited image generation
_RATE_LIMIT_DELAY_S = 30.0
_TOOL_MAX_RETRIES = 5


@function_tool
async def generate_image(
    ctx: RunContextWrapper[AgentContext],
    prompt: str,
    reference_image_key: str = "",
) -> str:
    """Generate a new image from a text prompt using the AI image provider.

    Args:
        prompt: Detailed description of the image to generate.
        reference_image_key: Optional key of a previously generated image to use as reference.
    """
    agent_ctx = ctx.context
    config = GenerationConfig(image_size=agent_ctx.settings.image_size)

    with _tracer.start_as_current_span("tool.generate_image") as span:
        span.set_attribute("prompt_length", len(prompt))
        span.set_attribute("has_reference", bool(reference_image_key))

        last_error = None
        for attempt in range(_TOOL_MAX_RETRIES):
            try:
                if reference_image_key:
                    ref = agent_ctx.get_image(reference_image_key)
                    result = await agent_ctx.provider.generate_with_references(
                        prompt, [ref], config
                    )
                else:
                    result = await agent_ctx.provider.generate(prompt, config)

                key = agent_ctx.store_image(result.image, prefix="gen")
                w, h = result.image.size
                span.set_attribute("result_key", key)
                span.set_attribute("result_size", f"{w}x{h}")
                span.set_attribute("retry_count", attempt)
                logger.info("generate_image -> %s (%dx%d)", key, w, h)
                return f"Generated '{key}' ({w}x{h}). Use split_frames if this is a composite strip, or resize_to_target if it's a single sprite."
            except Exception as e:
                last_error = e
                err_msg = str(e).lower()
                is_rate_limit = any(t in err_msg for t in ("429", "rate", "resource_exhausted", "quota"))
                if attempt < _TOOL_MAX_RETRIES - 1:
                    delay = _RATE_LIMIT_DELAY_S if is_rate_limit else 3.0
                    logger.warning(
                        "generate_image attempt %d failed: %s. Retrying in %.0fs...",
                        attempt + 1, e, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    logger.error("generate_image failed after %d attempts: %s", _TOOL_MAX_RETRIES, e)

        return f"ERROR: Image generation failed after {_TOOL_MAX_RETRIES} attempts: {last_error}"


@function_tool
async def edit_image(
    ctx: RunContextWrapper[AgentContext],
    image_key: str,
    edit_prompt: str,
) -> str:
    """Edit an existing image using multi-turn AI conversation.

    Args:
        image_key: Key of the image to edit.
        edit_prompt: Instructions for how to modify the image.
    """
    agent_ctx = ctx.context
    image = agent_ctx.get_image(image_key)

    try:
        # Create session if needed
        if agent_ctx.session is None:
            agent_ctx.session = await agent_ctx.provider.start_session()

        result = await agent_ctx.session.send(
            edit_prompt, reference_images=[image]
        )
    except Exception as e:
        return f"ERROR: Image editing failed: {e}"

    key = agent_ctx.store_image(result.image, prefix="edit")
    w, h = result.image.size
    logger.info("edit_image %s -> %s (%dx%d)", image_key, key, w, h)
    return f"Edited image stored as '{key}' ({w}x{h})."


@function_tool
async def analyze_composite(
    ctx: RunContextWrapper[AgentContext],
    image_key: str,
    expected_count: int,
) -> str:
    """Analyze a composite image to detect sprite boundaries using computer vision.

    Returns the number of detected regions, their sizes, and whether it matches expectations.

    Args:
        image_key: Key of the composite image to analyze.
        expected_count: How many sprites/frames are expected.
    """
    agent_ctx = ctx.context
    image = agent_ctx.get_image(image_key)
    image = image.convert("RGBA")

    # Prepare: remove solid background, trim padding
    prepped = _prepare_composite(image)
    prep_w, prep_h = prepped.size

    # Detect components
    frames = _run_component_detection(prepped, expected_count)

    regions = []
    for i, f in enumerate(frames):
        regions.append(f"  [{i}] {f.width}x{f.height}")

    match = len(frames) == expected_count
    lines = [
        f"Analyzed '{image_key}' (original {image.width}x{image.height}, "
        f"prepped {prep_w}x{prep_h})",
        f"Detected {len(frames)} regions (expected {expected_count}): "
        f"{'MATCH' if match else 'MISMATCH'}",
    ]
    lines.extend(regions)

    if not match:
        lines.append(
            "Suggestion: Try re-generating with more spacing between sprites, "
            "or use split_frames which has additional fallback strategies."
        )

    # Check for degenerate results (one blob = entire image)
    total_area = prep_w * prep_h
    for i, f in enumerate(frames):
        if f.width * f.height > total_area * 0.5:
            lines.append(
                f"WARNING: Region [{i}] covers >50% of image — "
                f"likely a single merged blob, not individual sprites."
            )

    return "\n".join(lines)


@function_tool
async def split_frames(
    ctx: RunContextWrapper[AgentContext],
    image_key: str,
    expected_count: int,
) -> str:
    """Split a composite image into individual frames using smart extraction.

    Uses multiple strategies (horizontal strip, auto-detect, grid, vertical)
    to find the best split.

    Args:
        image_key: Key of the composite image to split.
        expected_count: How many frames to extract.
    """
    agent_ctx = ctx.context
    image = agent_ctx.get_image(image_key)

    # For single frame, just trim and return
    if expected_count <= 1:
        from pixel_magic.generation.extractor import _prepare_composite
        trimmed = _prepare_composite(image.convert("RGBA"))
        key = agent_ctx.store_image(trimmed, prefix=f"{image_key}_f")
        w, h = trimmed.size
        logger.info("split_frames %s -> 1 frame (%dx%d)", image_key, w, h)
        return f"Extracted single frame '{key}' ({w}x{h}).\nFrame keys: {key}"

    # Use smart extraction which tries: separators, horizontal strip,
    # auto-detect (OpenCV), grid, vertical strip — in that order
    frames = extract_frames(image, CompositeLayout.HORIZONTAL_STRIP, expected_count)
    frames = normalize_frame_sizes(frames)

    # Validate: check if frames look like individual sprites (not whole composites)
    orig_area = image.width * image.height
    suspicious = any(f.width * f.height > orig_area * 0.5 for f in frames)
    if suspicious and expected_count > 1:
        # Try AUTO_DETECT as fallback
        logger.warning("split_frames: horizontal strip produced suspicious frames, trying auto-detect")
        auto_frames = extract_frames(image, CompositeLayout.AUTO_DETECT, expected_count)
        auto_frames = normalize_frame_sizes(auto_frames)
        auto_suspicious = any(f.width * f.height > orig_area * 0.5 for f in auto_frames)
        if not auto_suspicious:
            frames = auto_frames

    keys = []
    for i, frame in enumerate(frames):
        key = agent_ctx.store_image(frame, prefix=f"{image_key}_f")
        keys.append(key)

    sizes = [f"{f.width}x{f.height}" for f in frames]
    unique_sizes = set(sizes)
    size_info = f"all {list(unique_sizes)[0]}" if len(unique_sizes) == 1 else f"varying: {', '.join(sizes)}"

    logger.info("split_frames %s -> %d frames", image_key, len(keys))
    return (
        f"Split '{image_key}' into {len(keys)} frames ({size_info}).\n"
        f"Frame keys: {', '.join(keys)}"
    )


@function_tool
async def evaluate_quality(
    ctx: RunContextWrapper[AgentContext],
    image_key: str,
) -> str:
    """Run deterministic quality checks on a sprite frame.

    Checks alpha compliance (binary transparency) and island noise
    (disconnected pixel fragments).

    Args:
        image_key: Key of the image to evaluate.
    """
    agent_ctx = ctx.context
    image = agent_ctx.get_image(image_key)
    image = image.convert("RGBA")

    alpha_check = check_alpha_compliance(image, agent_ctx.settings.alpha_policy)
    island_check = check_island_noise(image, agent_ctx.settings.min_island_size)

    passed = alpha_check.passed and island_check.passed
    status = "PASS" if passed else "FAIL"

    return (
        f"Quality {status} for '{image_key}' ({image.width}x{image.height}):\n"
        f"  Alpha: {'PASS' if alpha_check.passed else 'FAIL'} — {alpha_check.details}\n"
        f"  Islands: {'PASS' if island_check.passed else 'FAIL'} — {island_check.details}"
    )


@function_tool
async def resize_to_target(
    ctx: RunContextWrapper[AgentContext],
    frame_keys: str,
    target_resolution: str,
) -> str:
    """Resize frames to target pixel resolution using nearest-neighbor scaling.

    Args:
        frame_keys: Comma-separated list of image keys to resize.
        target_resolution: Target size like "64x64".
    """
    agent_ctx = ctx.context
    keys = [k.strip() for k in frame_keys.split(",") if k.strip()]

    parts = target_resolution.lower().split("x")
    if len(parts) != 2:
        return f"ERROR: Invalid resolution format '{target_resolution}'. Use 'WxH' like '64x64'."

    target_w, target_h = int(parts[0]), int(parts[1])

    for key in keys:
        image = agent_ctx.get_image(key)
        resized = image.resize((target_w, target_h), Image.NEAREST)
        agent_ctx.images[key] = resized

    return f"Resized {len(keys)} frames to {target_w}x{target_h}."


@function_tool
async def save_frames(
    ctx: RunContextWrapper[AgentContext],
    direction: str,
    animation_name: str,
    frame_keys: str,
    duration_ms: int = 100,
    is_looping: bool = True,
) -> str:
    """Register completed animation frames as output and save PNGs.

    Args:
        direction: Direction name (e.g., "south_east", "north_east").
        animation_name: Animation name (e.g., "idle", "walk").
        frame_keys: Comma-separated list of frame image keys in order.
        duration_ms: Duration per frame in milliseconds.
        is_looping: Whether this animation loops.
    """
    agent_ctx = ctx.context
    keys = [k.strip() for k in frame_keys.split(",") if k.strip()]

    # Check if frames are suspiciously large (likely not resized)
    for key in keys:
        image = agent_ctx.get_image(key)
        if image.width > 256 or image.height > 256:
            return (
                f"ERROR: Frame '{key}' is {image.width}x{image.height} — too large! "
                f"You must call resize_to_target before save_frames. "
                f"Resize all frames to the target resolution first."
            )

    # Save individual PNGs
    for i, key in enumerate(keys):
        image = agent_ctx.get_image(key)
        filename = f"{animation_name}_{direction}_{i:03d}.png"
        image.save(agent_ctx.output_dir / filename)

    # Record for runner to build AnimationClips
    agent_ctx.saved_clips.append({
        "direction": direction,
        "animation_name": animation_name,
        "frame_keys": keys,
        "duration_ms": duration_ms,
        "is_looping": is_looping,
    })

    # Trace save event
    with _tracer.start_as_current_span("tool.save_frames") as span:
        span.set_attribute("direction", direction)
        span.set_attribute("animation_name", animation_name)
        span.set_attribute("frame_count", len(keys))
        span.set_attribute("duration_ms", duration_ms)
        span.set_attribute("is_looping", is_looping)

    logger.info(
        "save_frames: %s_%s (%d frames, %dms, loop=%s)",
        animation_name, direction, len(keys), duration_ms, is_looping,
    )
    return (
        f"Saved {len(keys)} frames for {animation_name}_{direction} "
        f"({duration_ms}ms/frame, looping={is_looping})."
    )


def get_all_tools() -> list:
    """Return all shared tools for agent registration."""
    return [
        generate_image,
        edit_image,
        analyze_composite,
        split_frames,
        evaluate_quality,
        resize_to_target,
        save_frames,
    ]
