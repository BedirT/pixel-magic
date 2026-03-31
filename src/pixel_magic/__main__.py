"""CLI entry point for pixel-magic."""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path

from PIL import Image


def _positive_int(value: str) -> int:
    """argparse type that rejects zero and negative integers."""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return ivalue


def _resolve_chromakey_pink(
    args_chromakey: str | None,
) -> str:
    """Default to pink chromakey so green and blue content survives extraction."""
    if args_chromakey is not None:
        return args_chromakey
    return "pink"


def _clean_sprite(image: Image.Image, chromakey_color: str) -> Image.Image:
    """Shared post-processing: remove background, clean mask, add outline."""
    from pixel_magic.background import remove_background
    from pixel_magic.cleanup import cleanup_sprite
    from pixel_magic.resize import add_outline

    image = remove_background(image, chromakey_color=chromakey_color)
    image = cleanup_sprite(image, chromakey_color=chromakey_color)
    return add_outline(image)


def _clean_tile(image: Image.Image, chromakey_color: str) -> Image.Image:
    """Post-processing for tiles: remove background, clean mask (no outline strip)."""
    from pixel_magic.background import remove_background
    from pixel_magic.cleanup import cleanup_tile

    image = remove_background(image, chromakey_color=chromakey_color)
    return cleanup_tile(image, chromakey_color=chromakey_color)


def _normalize_animation_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """Pad all frames to the same size with bottom-center anchoring."""
    if not frames:
        return frames
    max_w = max(f.width for f in frames)
    max_h = max(f.height for f in frames)
    normalized = []
    for f in frames:
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        x = (max_w - f.width) // 2
        y = max_h - f.height
        canvas.paste(f, (x, y), f)
        normalized.append(canvas)
    return normalized


def _output_dir(base: str, category: str, name: str) -> Path:
    """Build output path, avoiding doubled category directories.

    If base already ends with the category name (e.g. --output-dir assets/tiles
    for a tile command), don't append it again.
    """
    base_path = Path(base)
    if base_path.name == category:
        return base_path / name
    return base_path / category / name


def _resize_sprites(
    labels: list[str],
    out_dir: Path,
    sizes_str: str,
    num_colors: int | None,
) -> None:
    """Resize saved PNGs to pixel art sizes."""
    if not sizes_str:
        return
    from pixel_magic.resize import parse_sizes, resize_sprite

    sizes = parse_sizes(sizes_str)
    for size in sizes:
        size_dir = out_dir / f"{size}x{size}"
        size_dir.mkdir(exist_ok=True)
        for label in labels:
            safe_name = label.replace(" ", "_").replace("/", "_")
            src = Image.open(out_dir / f"{safe_name}.png").convert("RGBA")
            resized = resize_sprite(src, size, num_colors=num_colors)
            resized.save(size_dir / f"{safe_name}.png")
        print(f"  Resized to {size}x{size}")
    print(f"Saved {len(sizes)} size variants")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixel-magic",
        description="Generate pixel art character sprites.",
    )
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a character sprite sheet")
    gen.add_argument("--name", required=True, help="Character name (used as output folder)")
    gen.add_argument("--description", required=True, help="Character description")
    gen.add_argument("--directions", type=int, default=4, choices=[4, 8], help="Number of directions (default: 4)")
    gen.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    gen.add_argument("--resolution", default="64x64", help="Target resolution per view (default: 64x64)")
    gen.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    gen.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    gen.add_argument("--palette-hint", default="", help="Color palette hint")
    gen.add_argument(
        "--sizes",
        default="",
        help='Resize sprites to pixel art sizes (e.g. "32,64" or "all"). '
        "Valid: 16, 32, 48, 64, 96, 128, 256",
    )
    gen.add_argument(
        "--num-colors",
        type=int,
        default=None,
        help="Color palette size for resized sprites (default: preserve original colors)",
    )
    gen.add_argument(
        "--chromakey",
        choices=["green", "blue"],
        default=None,
        help="Override chromakey color for Gemini background removal (default: from .env)",
    )
    gen.add_argument(
        "--tiles", type=int, default=1, choices=[1, 4, 9],
        help="Character tile footprint: 1 (default), 4 (2x2 — larger creature), 9 (3x3 — boss/mount).",
    )
    gen.add_argument(
        "--no-platform", dest="use_platform", action="store_false", default=True,
        help="Disable platform-guided generation. Uses text-only prompt (more creative freedom, less perspective control).",
    )
    gen.add_argument(
        "--char-ratio", type=float, default=1.2,
        help="Estimated character height as multiple of platform width (default: 1.2). Controls platform vertical placement.",
    )

    anim = sub.add_parser("animate", help="Generate animation frames for an existing character")
    anim.add_argument("--name", required=True, help="Character name (must exist in output dir)")
    anim.add_argument("--animation", default="walk", help="Animation type: walk, idle, attack, run, cast, hurt, death, dodge, jump, block (default: walk)")
    anim.add_argument("--description", default="", help="Character description (helps model consistency)")
    anim.add_argument("--frames", type=int, default=5, help="Total frames in cycle (default: 5)")
    anim.add_argument("--loop", action="store_true", default=True, help="Looping animation (default)")
    anim.add_argument("--no-loop", dest="loop", action="store_false", help="One-shot animation (attack, death, etc.)")
    anim.add_argument(
        "--direction",
        default="south_east",
        help="Which compass-facing view to animate (default: south_east — 3/4 facing works best)",
    )
    anim.add_argument("--reference", default=None, help="Path to reference frame (overrides auto-detect)")
    anim.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    anim.add_argument("--chromakey", choices=["green", "blue"], default=None, help="Chromakey color")
    anim.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    anim.add_argument("--platform", action="store_true", default=False, help="Add isometric platform tiles for perspective reference")
    anim.add_argument("--no-platform", dest="platform", action="store_false", help="No platform (default)")
    anim.add_argument(
        "--tiles", type=int, default=1, choices=[1, 4, 9],
        help="Platform tile count: 1 (default), 4 (2x2 grid), 9 (3x3 grid). More tiles = more room for action poses.",
    )

    anim_obj = sub.add_parser("animate-object", help="Generate animation frames for an existing object")
    anim_obj.add_argument("--set", required=True, help="Object set name (e.g., forest, torch)")
    anim_obj.add_argument("--name", required=True, help="Object name within the set (e.g., oak_tree_1)")
    anim_obj.add_argument("--animation", default="sway", help="Animation type: sway, flicker, burn, pulse, open, bob, spin (default: sway)")
    anim_obj.add_argument("--description", default="", help="Object description (helps model consistency)")
    anim_obj.add_argument("--frames", type=int, default=5, help="Total frames in cycle (default: 5)")
    anim_obj.add_argument("--loop", action="store_true", default=True, help="Looping animation (default)")
    anim_obj.add_argument("--no-loop", dest="loop", action="store_false", help="One-shot animation (open, etc.)")
    anim_obj.add_argument("--reference", default=None, help="Path to reference frame (overrides auto-detect)")
    anim_obj.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    anim_obj.add_argument("--chromakey", choices=["green", "blue", "pink"], default=None, help="Chromakey color (default: pink)")
    anim_obj.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    anim_obj.add_argument("--platform", action="store_true", default=False, help="Add isometric platform for perspective")
    anim_obj.add_argument("--no-platform", dest="platform", action="store_false", help="No platform (default)")
    anim_obj.add_argument(
        "--tiles", type=int, default=1, choices=[1, 4, 9],
        help="Platform tile count: 1 (default), 4 (2x2 grid), 9 (3x3 grid).",
    )
    anim_obj.add_argument(
        "--sizes", default="",
        help='Resize frames to pixel art sizes (e.g. "32,64" or "all")',
    )
    anim_obj.add_argument("--num-colors", type=int, default=None, help="Palette size for resized frames")

    tile = sub.add_parser("tile", help="Generate isometric terrain tiles")
    tile_mode = tile.add_mutually_exclusive_group(required=True)
    tile_mode.add_argument("--type", dest="tile_type", help="Single tile type with variants (e.g., grass, stone, water)")
    tile_mode.add_argument("--theme", help="Themed tile set (e.g., forest, dungeon, desert, winter, custom)")
    tile.add_argument("--variants", type=_positive_int, default=4, help="Number of variants per tile type (--type mode only, default: 4)")
    tile.add_argument("--types", default="", help="Custom tile types for --theme custom (comma-separated)")
    tile.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    tile.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    tile.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    tile.add_argument("--chromakey", choices=["green", "blue", "pink"], default=None, help="Chromakey color")
    tile.add_argument("--depth", type=int, default=4, help="Tile side depth in pixels (default: 4, 0=flat)")
    tile.add_argument(
        "--sizes", default="",
        help='Resize tiles to pixel art sizes (e.g. "32,64" or "all")',
    )
    tile.add_argument("--num-colors", type=int, default=None, help="Palette size for resized tiles")

    obj = sub.add_parser("object", help="Generate isometric world objects/props")
    obj_mode = obj.add_mutually_exclusive_group(required=True)
    obj_mode.add_argument("--name", help="Single object type with variants (e.g., tree, rock, chest)")
    obj_mode.add_argument("--preset", help="Themed object set (e.g., forest, dungeon, camp, custom)")
    obj.add_argument("--variants", type=_positive_int, default=4, help="Number of variants (--name mode only, default: 4)")
    obj.add_argument("--names", default="", help="Custom object names for --preset custom (comma-separated)")
    obj.add_argument("--description", default="", help="Optional theme/style description")
    obj.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    obj.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    obj.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    obj.add_argument("--chromakey", choices=["green", "blue", "pink"], default=None, help="Chromakey color")
    obj.add_argument("--depth", type=int, default=8, help="Platform side depth in pixels (default: 8)")
    obj.add_argument(
        "--sizes", default="",
        help='Resize objects to pixel art sizes (e.g. "32,64" or "all")',
    )
    obj.add_argument("--num-colors", type=int, default=None, help="Palette size for resized objects")

    eff = sub.add_parser("effect", help="Generate animated VFX effects (explosions, smoke, magic, etc.)")
    eff_mode = eff.add_mutually_exclusive_group(required=True)
    eff_mode.add_argument("--name", help="Single effect name (e.g., explosion, fire, magic_circle)")
    eff_mode.add_argument("--preset", help="Effect preset group (e.g., combat, magic, nature, status, custom)")
    eff.add_argument("--names", default="", help="Custom effect names for --preset custom (comma-separated)")
    eff.add_argument("--description", default="", help="Optional effect description (auto-inferred from name if empty)")
    eff.add_argument("--frames", type=_positive_int, default=6, help="Total animation frames (default: 6, minimum: 2)")
    eff.add_argument("--loop", action="store_true", default=None, help="Force looping animation")
    eff.add_argument("--no-loop", dest="loop", action="store_false", help="Force one-shot animation")
    eff.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    eff.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    eff.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    eff.add_argument("--chromakey", choices=["green", "blue", "pink"], default=None, help="Chromakey color (default: pink)")
    eff.add_argument(
        "--sizes", default="",
        help='Resize frames to pixel art sizes (e.g. "32,64" or "all")',
    )
    eff.add_argument("--num-colors", type=int, default=None, help="Palette size for resized frames")

    return parser


def _view_labels(directions: int) -> list[str]:
    """Return direction labels matching the prompt view order."""
    if directions == 4:
        return ["south_west", "north_east"]
    return ["north", "north_east", "east", "south_east", "south"]


_DIRECTION_ALIASES: dict[str, str] = {
    "north": "north",
    "north_east": "north_east",
    "east": "east",
    "south_east": "south_east",
    "south": "south",
    "south_west": "south_west",
    "west": "west",
    "north_west": "north_west",
    "back": "north",
    "back_right": "north_east",
    "right": "east",
    "front_right": "south_east",
    "front": "south",
    "front_left": "south_west",
    "left": "west",
    "back_left": "north_west",
}


# Maps each generated view to its horizontal mirror counterpart.
_MIRROR_MAP: dict[str, str] = {
    "south_west": "south_east",
    "south_east": "south_west",
    "north_west": "north_east",
    "north_east": "north_west",
    "west": "east",
    "east": "west",
}


def _canonical_direction(direction: str) -> str:
    """Normalize a view name to the canonical compass-based label."""
    normalized = direction.strip().lower().replace("-", "_")
    canonical = _DIRECTION_ALIASES.get(normalized)
    if canonical is None:
        valid = ", ".join(sorted({
            "north", "north_east", "east", "south_east",
            "south", "south_west", "west", "north_west",
        }))
        raise ValueError(f"Unknown direction {direction!r}. Use one of: {valid}")
    return canonical


def _resolve_view_path(views_dir: Path, direction: str) -> Path:
    """Find a view sprite, preferring canonical compass filenames over legacy names."""
    canonical = _canonical_direction(direction)
    candidates = [canonical]
    candidates.extend(
        alias
        for alias, mapped in _DIRECTION_ALIASES.items()
        if mapped == canonical and alias != canonical
    )

    for name in candidates:
        path = views_dir / f"{name}.png"
        if path.exists():
            return path

    return views_dir / f"{canonical}.png"


def _mirror_sprites(
    views_dir: Path,
    generated_labels: list[str],
) -> list[str]:
    """Create horizontally-flipped mirrors for generated views.

    Returns the list of newly created mirror labels.
    """
    mirrored_labels: list[str] = []
    for label in generated_labels:
        mirror_label = _MIRROR_MAP.get(label)
        if mirror_label is None or mirror_label in generated_labels:
            continue
        src = Image.open(views_dir / f"{label}.png").convert("RGBA")
        flipped = src.transpose(Image.FLIP_LEFT_RIGHT)
        flipped.save(views_dir / f"{mirror_label}.png")
        mirrored_labels.append(mirror_label)
        print(f"  {mirror_label}: {flipped.width}x{flipped.height} (mirrored from {label})")
    return mirrored_labels


async def _generate(args: argparse.Namespace) -> None:
    from pixel_magic.config import Settings
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = args.chromakey or settings.chromakey_color

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    view_labels = _view_labels(args.directions)
    view_count = len(view_labels)

    out_dir = Path(args.output_dir) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.use_platform:
        result = await _generate_with_platforms(
            args, provider, view_labels, view_count, chromakey_color, out_dir,
        )
    else:
        result = await _generate_text_only(
            args, provider, view_count, chromakey_color, out_dir,
        )

    # Background removal (rembg + despill)
    from pixel_magic.background import remove_background

    sheet = remove_background(result.image, chromakey_color=chromakey_color)
    sheet.save(out_dir / "sheet.png")
    print(f"  Sheet: {sheet.width}x{sheet.height} (background removed)")

    # Extract individual sprites
    from pixel_magic.extract import extract_sprites

    sprites = extract_sprites(sheet, expected_count=view_count)
    if sprites:
        # Save raw extractions for debugging
        views_raw_dir = out_dir / "views_raw"
        views_raw_dir.mkdir(exist_ok=True)
        for i, sprite in enumerate(sprites):
            raw_label = view_labels[i] if i < len(view_labels) else f"view_{i}"
            sprite.save(views_raw_dir / f"{raw_label}.png")

        # Clean sprites (mask hardening + contamination removal + outline)
        views_dir = out_dir / "views"
        views_dir.mkdir(exist_ok=True)
        for i, sprite in enumerate(sprites):
            label = view_labels[i] if i < len(view_labels) else f"view_{i}"
            cleaned = _clean_sprite(sprite, chromakey_color)
            cleaned.save(views_dir / f"{label}.png")
            print(f"  {label}: {cleaned.width}x{cleaned.height}")
        print(f"Extracted {len(sprites)} sprites to {views_dir}")

        actual_labels = [view_labels[i] if i < len(view_labels) else f"view_{i}" for i in range(len(sprites))]

        # Mirror generated views to fill remaining directions
        mirrored = _mirror_sprites(views_dir, actual_labels)
        all_labels = actual_labels + mirrored

        _resize_sprites(all_labels, views_dir, args.sizes, args.num_colors)
    else:
        print("Warning: could not extract individual sprites from sheet")


async def _generate_text_only(args, provider, view_count, chromakey_color, out_dir):
    """Text-only generation — no platform template, maximum creative freedom."""
    from pixel_magic.prompts import build_character_sheet_prompt

    prompt = build_character_sheet_prompt(
        character_description=args.description,
        direction_mode=args.directions,
        style=args.style,
        resolution=args.resolution,
        max_colors=args.max_colors,
        palette_hint=args.palette_hint,
        chromakey_color=chromakey_color,
    )

    print(f"Generating {args.name} ({view_count} views, text-only)...")
    result = await provider.generate(prompt)
    result.image.save(out_dir / "raw.png")
    print(f"  Raw: {result.image.width}x{result.image.height}")
    return result


async def _generate_with_platforms(args, provider, view_labels, view_count, chromakey_color, out_dir):
    """Platform-guided generation — canvas template with labeled platforms."""
    from pixel_magic.animate import build_generation_canvas
    from pixel_magic.prompts import build_generation_canvas_prompt, build_generation_cleanup_prompt

    canvas, grid_cols, slot_size, aspect_ratio, image_size, center_bottom = (
        build_generation_canvas(
            view_labels=view_labels,
            tiles=args.tiles,
            chromakey_color=chromakey_color,
            char_ratio=args.char_ratio,
        )
    )
    grid_rows = math.ceil(view_count / grid_cols)
    canvas.save(out_dir / "canvas_input.png")

    print(f"Generating {args.name} ({view_count} views, tiles={args.tiles})...")
    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid)")
    print(f"  Gemini: {aspect_ratio} ratio, {image_size} output")

    prompt = build_generation_canvas_prompt(
        character_description=args.description,
        direction_mode=args.directions,
        style=args.style,
        max_colors=args.max_colors,
        chromakey_color=chromakey_color,
        tiles=args.tiles,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )

    print("  Generating character views...")
    result = await provider.generate_with_images(
        prompt=prompt,
        images=[canvas],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    result.image.save(out_dir / "raw.png")
    print(f"  Raw: {result.image.width}x{result.image.height}")

    # Second pass: remove platforms + labels
    cleanup_prompt = build_generation_cleanup_prompt(
        view_count, chromakey_color,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )
    print("  Removing platforms...")
    cleaned = await provider.generate_with_images(
        prompt=cleanup_prompt,
        images=[result.image],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    cleaned.image.save(out_dir / "sheet_cleaned.png")
    return cleaned


async def _animate(args: argparse.Namespace) -> None:
    from pixel_magic.animate import assemble_sprite_sheet, generate_animation
    from pixel_magic.config import Settings
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = args.chromakey or settings.chromakey_color
    try:
        direction = _canonical_direction(args.direction)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(2)

    # Find reference frame
    if args.reference:
        ref_path = Path(args.reference)
    else:
        ref_path = _resolve_view_path(Path(args.output_dir) / args.name / "views", direction)

    if not ref_path.exists():
        print(f"Error: reference frame not found at {ref_path}")
        print("Run 'pixel-magic generate' first, or use --reference to specify a path.")
        sys.exit(1)

    reference = Image.open(ref_path).convert("RGBA")
    print(f"Reference: {ref_path} ({reference.width}x{reference.height})")

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    # --tiles > 1 implies --platform
    if args.tiles > 1:
        args.platform = True

    anim_dir = Path(args.output_dir) / args.name / "animations" / args.animation
    print(f"Generating {args.frames}-frame {args.animation} animation...")

    raw_frames = await generate_animation(
        provider=provider,
        reference_frame=reference,
        animation_type=args.animation,
        total_frames=args.frames,
        loop=args.loop,
        character_description=args.description,
        style=args.style,
        chromakey_color=chromakey_color,
        save_dir=anim_dir,
        platform=args.platform,
        tiles=args.tiles,
    )

    # Clean each frame (background removal + outline strip/re-add)
    cleaned_frames = [_clean_sprite(frame, chromakey_color) for frame in raw_frames]
    cleaned_frames = _normalize_animation_frames(cleaned_frames)
    for i, frame in enumerate(cleaned_frames, 1):
        frame.save(anim_dir / f"frame_{i:02d}.png")

    sheet = assemble_sprite_sheet(cleaned_frames)
    sheet.save(anim_dir / "sheet.png")
    print(f"Saved {len(cleaned_frames)} frames + sheet to {anim_dir}")


async def _animate_object(args: argparse.Namespace) -> None:
    from pixel_magic.animate import assemble_sprite_sheet, generate_animation
    from pixel_magic.config import Settings
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = _resolve_chromakey_pink(args.chromakey)

    # Find reference frame
    if args.reference:
        ref_path = Path(args.reference)
    else:
        safe_name = args.name.replace(" ", "_").replace("/", "_")
        ref_path = Path(args.output_dir) / "objects" / args.set / f"{safe_name}.png"

    if not ref_path.exists():
        print(f"Error: reference frame not found at {ref_path}")
        print("Run 'pixel-magic object' first, or use --reference to specify a path.")
        sys.exit(1)

    reference = Image.open(ref_path).convert("RGBA")
    print(f"Reference: {ref_path} ({reference.width}x{reference.height})")

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    if args.tiles > 1:
        args.platform = True

    safe_name = args.name.replace(" ", "_").replace("/", "_")
    anim_dir = Path(args.output_dir) / "objects" / args.set / "animations" / safe_name / args.animation
    print(f"Generating {args.frames}-frame {args.animation} animation for {args.name}...")

    raw_frames = await generate_animation(
        provider=provider,
        reference_frame=reference,
        animation_type=args.animation,
        total_frames=args.frames,
        loop=args.loop,
        character_description=args.description,
        style=args.style,
        chromakey_color=chromakey_color,
        save_dir=anim_dir,
        platform=args.platform,
        tiles=args.tiles,
        subject="object",
    )

    cleaned_frames = [_clean_sprite(frame, chromakey_color) for frame in raw_frames]
    cleaned_frames = _normalize_animation_frames(cleaned_frames)
    for i, frame in enumerate(cleaned_frames, 1):
        frame.save(anim_dir / f"frame_{i:02d}.png")

    sheet = assemble_sprite_sheet(cleaned_frames)
    sheet.save(anim_dir / "sheet.png")
    print(f"Saved {len(cleaned_frames)} frames + sheet to {anim_dir}")

    # Resize frames to target pixel art sizes
    if args.sizes:
        from pixel_magic.resize import parse_sizes, resize_sprite

        sizes = parse_sizes(args.sizes)
        for size in sizes:
            size_dir = anim_dir / f"{size}x{size}"
            size_dir.mkdir(exist_ok=True)
            resized_frames = []
            for i, frame in enumerate(cleaned_frames, 1):
                resized = resize_sprite(frame, size, num_colors=args.num_colors)
                resized.save(size_dir / f"frame_{i:02d}.png")
                resized_frames.append(resized)
            resized_sheet = assemble_sprite_sheet(resized_frames)
            resized_sheet.save(size_dir / "sheet.png")
            print(f"  Resized to {size}x{size}")
        print(f"Saved {len(sizes)} size variants")


async def _effect(args: argparse.Namespace) -> None:
    from pixel_magic.animate import assemble_sprite_sheet
    from pixel_magic.canvas import build_empty_canvas, extract_frames
    from pixel_magic.config import Settings
    from pixel_magic.effect import (
        enforce_loop_closure,
        infer_loop_default,
        resolve_effect_labels,
    )
    from pixel_magic.prompts import (
        build_effect_animation_prompt,
        build_effect_cleanup_prompt,
    )
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = _resolve_chromakey_pink(args.chromakey)

    set_name, effect_labels = resolve_effect_labels(
        name=args.name, preset=args.preset, custom_names=args.names,
    )

    if args.frames < 2:
        raise ValueError("Animations need at least 2 frames")

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    for effect_name in effect_labels:
        # Determine loop behavior: explicit flag > auto-detect from effect name
        loop = args.loop if args.loop is not None else infer_loop_default(effect_name)
        description = args.description or effect_name.replace("_", " ")

        if loop and args.frames < 3:
            raise ValueError("Looping animations need at least 3 frames")

        # Output directory: effects/{name}/ or effects/{preset}/{name}/
        safe_name = effect_name.replace(" ", "_").replace("/", "_")
        if args.preset:
            eff_dir = _output_dir(args.output_dir, "effects", set_name) / safe_name
        else:
            eff_dir = _output_dir(args.output_dir, "effects", safe_name)
        eff_dir.mkdir(parents=True, exist_ok=True)

        print(f"Generating {effect_name} effect ({args.frames} frames, {'loop' if loop else 'one-shot'})...")

        # Build empty grid canvas (no reference frame)
        canvas, grid_cols, slot_size, aspect_ratio, image_size = build_empty_canvas(
            total_frames=args.frames,
            chromakey_color=chromakey_color,
        )
        grid_rows = math.ceil(args.frames / grid_cols)
        canvas.save(eff_dir / "canvas_input.png")

        print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid, {args.frames} frames)")
        print(f"  Gemini: {aspect_ratio} ratio, {image_size} output")

        # Single Gemini call — fill all slots
        prompt = build_effect_animation_prompt(
            effect_name=effect_name,
            total_frames=args.frames,
            effect_description=description,
            style=args.style,
            chromakey_color=chromakey_color,
            loop=loop,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
        )

        print("  Generating animation...")
        result = await provider.generate_with_images(
            prompt=prompt,
            images=[canvas],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        result.image.save(eff_dir / "sheet_raw.png")

        cleanup_prompt = build_effect_cleanup_prompt(
            args.frames,
            chromakey_color,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
        )
        print("  Removing frame numbers...")
        cleaned = await provider.generate_with_images(
            prompt=cleanup_prompt,
            images=[result.image],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        cleaned.image.save(eff_dir / "sheet_cleaned.png")

        # Resize output to match canvas dims if Gemini changed them
        sheet = cleaned.image
        if sheet.size != canvas.size:
            sheet = sheet.resize(canvas.size, Image.NEAREST)

        # Extract frames from grid
        raw_frames = extract_frames(sheet, args.frames, cols=grid_cols, slot_size=slot_size)

        cleaned_frames = [_clean_sprite(frame, chromakey_color) for frame in raw_frames]
        cleaned_frames = _normalize_animation_frames(cleaned_frames)
        cleaned_frames = enforce_loop_closure(cleaned_frames, loop=loop)
        for i, frame in enumerate(cleaned_frames, 1):
            frame.save(eff_dir / f"frame_{i:02d}.png")

        anim_sheet = assemble_sprite_sheet(cleaned_frames)
        anim_sheet.save(eff_dir / "sheet.png")
        print(f"Saved {len(cleaned_frames)} frames + sheet to {eff_dir}")

        # Resize frames to target pixel art sizes
        if args.sizes:
            from pixel_magic.resize import parse_sizes, resize_sprite

            sizes = parse_sizes(args.sizes)
            for size in sizes:
                size_dir = eff_dir / f"{size}x{size}"
                size_dir.mkdir(exist_ok=True)
                resized_frames = []
                for i, frame in enumerate(cleaned_frames, 1):
                    resized = resize_sprite(frame, size, num_colors=args.num_colors)
                    resized.save(size_dir / f"frame_{i:02d}.png")
                    resized_frames.append(resized)
                resized_sheet = assemble_sprite_sheet(resized_frames)
                resized_sheet.save(size_dir / "sheet.png")
                print(f"  Resized to {size}x{size}")
            print(f"Saved {len(sizes)} size variants")


async def _tile(args: argparse.Namespace) -> None:
    from pixel_magic.config import Settings
    from pixel_magic.providers.gemini import GeminiProvider
    from pixel_magic.tile import (
        build_tile_canvas,
        extract_tiles,
        fit_tile,
        resolve_tile_labels,
    )

    settings = Settings()
    chromakey_color = _resolve_chromakey_pink(args.chromakey)

    # Resolve tile labels
    set_name, tile_labels = resolve_tile_labels(
        tile_type=args.tile_type,
        theme=args.theme,
        custom_types=args.types,
        variants=args.variants,
    )

    out_dir = _output_dir(args.output_dir, "tiles", set_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build canvas with diamond wireframes
    canvas, grid_cols, slot_size, aspect_ratio, image_size = build_tile_canvas(
        tile_labels=tile_labels,
        depth=args.depth,
        chromakey_color=chromakey_color,
    )
    grid_rows = math.ceil(len(tile_labels) / grid_cols)
    canvas.save(out_dir / "canvas_input.png")

    print(f"Generating {set_name} tileset ({len(tile_labels)} tiles, depth={args.depth})...")
    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid)")
    print(f"  Gemini: {aspect_ratio} ratio, {image_size} output")

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    # Gemini pass 1: fill diamonds with terrain
    from pixel_magic.prompts import build_tile_canvas_prompt

    prompt = build_tile_canvas_prompt(
        tile_labels=tile_labels,
        style=args.style,
        max_colors=args.max_colors,
        chromakey_color=chromakey_color,
        depth=args.depth,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )

    print("  Generating terrain tiles...")
    result = await provider.generate_with_images(
        prompt=prompt,
        images=[canvas],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    result.image.save(out_dir / "raw.png")
    print(f"  Raw: {result.image.width}x{result.image.height}")

    # Gemini pass 2: remove labels and wireframe guides
    from pixel_magic.prompts import build_tile_cleanup_prompt

    cleanup_prompt = build_tile_cleanup_prompt(
        len(tile_labels), chromakey_color,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )
    print("  Removing labels and guides...")
    cleaned = await provider.generate_with_images(
        prompt=cleanup_prompt,
        images=[result.image],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    cleaned.image.save(out_dir / "sheet_cleaned.png")

    # Resize output to match canvas if Gemini changed dimensions
    sheet = cleaned.image
    if sheet.size != canvas.size:
        sheet = sheet.resize(canvas.size, Image.NEAREST)

    # Extract individual tiles from grid
    tiles = extract_tiles(sheet, tile_labels, cols=grid_cols, slot_size=slot_size)

    # Background removal + cleanup + fit on each tile
    for label, tile_img in tiles.items():
        tile_img = _clean_tile(tile_img, chromakey_color)
        tile_img = fit_tile(tile_img, target_width=64, depth=args.depth)

        safe_name = label.replace(" ", "_").replace("/", "_")
        tile_img.save(out_dir / f"{safe_name}.png")
        print(f"  {label}: {tile_img.width}x{tile_img.height}")

    print(f"Saved {len(tiles)} tiles to {out_dir}")

    _resize_sprites(tile_labels, out_dir, args.sizes, args.num_colors)


async def _object(args: argparse.Namespace) -> None:
    from pixel_magic.config import Settings
    from pixel_magic.object import (
        build_object_canvas,
        extract_objects,
        resolve_object_labels,
    )
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = _resolve_chromakey_pink(args.chromakey)

    # Resolve object labels
    set_name, object_labels = resolve_object_labels(
        name=args.name,
        preset=args.preset,
        custom_names=args.names,
        variants=args.variants,
    )

    out_dir = _output_dir(args.output_dir, "objects", set_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build canvas with labeled platforms
    canvas, grid_cols, slot_size, aspect_ratio, image_size = build_object_canvas(
        object_labels=object_labels,
        depth=args.depth,
        chromakey_color=chromakey_color,
    )
    grid_rows = math.ceil(len(object_labels) / grid_cols)
    canvas.save(out_dir / "canvas_input.png")

    print(f"Generating {set_name} objects ({len(object_labels)} objects, depth={args.depth})...")
    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid)")
    print(f"  Gemini: {aspect_ratio} ratio, {image_size} output")

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    # Gemini pass 1: draw objects on platforms
    from pixel_magic.prompts import build_object_canvas_prompt

    prompt = build_object_canvas_prompt(
        object_labels=object_labels,
        description=args.description,
        style=args.style,
        max_colors=args.max_colors,
        chromakey_color=chromakey_color,
        depth=args.depth,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )

    print("  Generating objects...")
    result = await provider.generate_with_images(
        prompt=prompt,
        images=[canvas],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    result.image.save(out_dir / "raw.png")
    print(f"  Raw: {result.image.width}x{result.image.height}")

    # Gemini pass 2: remove platforms and labels
    from pixel_magic.prompts import build_object_cleanup_prompt

    cleanup_prompt = build_object_cleanup_prompt(
        len(object_labels), chromakey_color,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )
    print("  Removing platforms...")
    cleaned = await provider.generate_with_images(
        prompt=cleanup_prompt,
        images=[result.image],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    cleaned.image.save(out_dir / "sheet_cleaned.png")

    # Resize output to match canvas if Gemini changed dimensions
    sheet = cleaned.image
    if sheet.size != canvas.size:
        sheet = sheet.resize(canvas.size, Image.NEAREST)

    # Extract individual objects from grid
    objects = extract_objects(sheet, object_labels, cols=grid_cols, slot_size=slot_size)

    # Background removal + cleanup on each object
    for label, obj_img in objects.items():
        obj_img = _clean_sprite(obj_img, chromakey_color)

        safe_name = label.replace(" ", "_").replace("/", "_")
        obj_img.save(out_dir / f"{safe_name}.png")
        print(f"  {label}: {obj_img.width}x{obj_img.height}")

    print(f"Saved {len(objects)} objects to {out_dir}")

    _resize_sprites(object_labels, out_dir, args.sizes, args.num_colors)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "generate":
        asyncio.run(_generate(args))
    elif args.command == "animate":
        asyncio.run(_animate(args))
    elif args.command == "animate-object":
        asyncio.run(_animate_object(args))
    elif args.command == "tile":
        try:
            asyncio.run(_tile(args))
        except ValueError as exc:
            parser.error(str(exc))
    elif args.command == "object":
        try:
            asyncio.run(_object(args))
        except ValueError as exc:
            parser.error(str(exc))
    elif args.command == "effect":
        try:
            asyncio.run(_effect(args))
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
