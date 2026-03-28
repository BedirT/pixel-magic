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
        raise argparse.ArgumentTypeError("--variants must be >= 1")
    return ivalue


def _resolve_tile_chromakey(
    args_chromakey: str | None,
    settings_chromakey: str,
) -> str:
    """Tile generation defaults to blue so green terrain survives extraction."""
    if args_chromakey is not None:
        return args_chromakey
    return "blue" if settings_chromakey == "green" else settings_chromakey


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
    anim.add_argument("--animation", default="walk", help="Animation type (default: walk)")
    anim.add_argument("--description", default="", help="Character description (helps model consistency)")
    anim.add_argument("--frames", type=int, default=5, help="Total frames in cycle (default: 5)")
    anim.add_argument("--loop", action="store_true", default=True, help="Looping animation (default)")
    anim.add_argument("--no-loop", dest="loop", action="store_false", help="One-shot animation (attack, death, etc.)")
    anim.add_argument("--direction", default="front_right", help="Which view to animate (default: front_right — east-facing works best)")
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

    tile = sub.add_parser("tile", help="Generate isometric terrain tiles")
    tile_mode = tile.add_mutually_exclusive_group(required=True)
    tile_mode.add_argument("--type", dest="tile_type", help="Single tile type with variants (e.g., grass, stone, water)")
    tile_mode.add_argument("--theme", help="Themed tile set (e.g., forest, dungeon, desert, winter, custom)")
    tile.add_argument("--variants", type=_positive_int, default=4, help="Number of variants per tile type (--type mode only, default: 4)")
    tile.add_argument("--types", default="", help="Custom tile types for --theme custom (comma-separated)")
    tile.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    tile.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    tile.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    tile.add_argument("--chromakey", choices=["green", "blue"], default=None, help="Chromakey color")
    tile.add_argument("--depth", type=int, default=4, help="Tile side depth in pixels (default: 4, 0=flat)")
    tile.add_argument(
        "--sizes", default="",
        help='Resize tiles to pixel art sizes (e.g. "32,64" or "all")',
    )
    tile.add_argument("--num-colors", type=int, default=None, help="Palette size for resized tiles")

    return parser


def _view_labels(directions: int) -> list[str]:
    """Return direction labels matching the prompt view order."""
    if directions == 4:
        return ["front_left", "back_right"]
    return ["back", "back_right", "right", "front_right", "front"]


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

        # Clean sprites (mask hardening + contamination removal)
        from pixel_magic.cleanup import cleanup_sprite

        views_dir = out_dir / "views"
        views_dir.mkdir(exist_ok=True)
        cleaned_sprites = []
        for i, sprite in enumerate(sprites):
            label = view_labels[i] if i < len(view_labels) else f"view_{i}"
            cleaned = cleanup_sprite(sprite, chromakey_color=chromakey_color)
            cleaned.save(views_dir / f"{label}.png")
            cleaned_sprites.append(cleaned)
            print(f"  {label}: {cleaned.width}x{cleaned.height}")
        print(f"Extracted {len(cleaned_sprites)} sprites to {views_dir}")

        # Use cleaned sprites for resize
        sprites = cleaned_sprites

        # Resize to pixel art sizes if requested
        if args.sizes:
            from pixel_magic.resize import parse_sizes, resize_sprite

            sizes = parse_sizes(args.sizes)
            for size in sizes:
                size_dir = views_dir / f"{size}x{size}"
                size_dir.mkdir(exist_ok=True)
                for i, sprite in enumerate(sprites):
                    label = view_labels[i] if i < len(view_labels) else f"view_{i}"
                    resized = resize_sprite(sprite, size, num_colors=args.num_colors)
                    resized.save(size_dir / f"{label}.png")
                print(f"  Resized to {size}x{size}")
            print(f"Saved {len(sizes)} size variants")
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

    # Find reference frame
    if args.reference:
        ref_path = Path(args.reference)
    else:
        ref_path = Path(args.output_dir) / args.name / "views" / f"{args.direction}.png"

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

    anim_frames = await generate_animation(
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

    sheet = assemble_sprite_sheet(anim_frames)
    sheet.save(anim_dir / "sheet.png")
    print(f"Saved {len(anim_frames)} frames + sheet to {anim_dir}")


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
    chromakey_color = _resolve_tile_chromakey(args.chromakey, settings.chromakey_color)

    # Resolve tile labels
    set_name, tile_labels = resolve_tile_labels(
        tile_type=args.tile_type,
        theme=args.theme,
        custom_types=args.types,
        variants=args.variants,
    )

    out_dir = Path(args.output_dir) / "tiles" / set_name
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

    # Background removal + cleanup on each tile
    from pixel_magic.background import remove_background
    from pixel_magic.cleanup import cleanup_tile

    for label, tile_img in tiles.items():
        # Remove chromakey background
        tile_img = remove_background(tile_img, chromakey_color=chromakey_color)
        # Clean mask (no outline stripping)
        tile_img = cleanup_tile(tile_img, chromakey_color=chromakey_color)
        # Fit to standard bounding box
        tile_img = fit_tile(tile_img, target_width=64, depth=args.depth)

        safe_name = label.replace(" ", "_").replace("/", "_")
        tile_img.save(out_dir / f"{safe_name}.png")
        print(f"  {label}: {tile_img.width}x{tile_img.height}")

    print(f"Saved {len(tiles)} tiles to {out_dir}")

    # Optional pixel art resize
    if args.sizes:
        from pixel_magic.resize import parse_sizes, resize_sprite

        sizes = parse_sizes(args.sizes)
        for size in sizes:
            size_dir = out_dir / f"{size}x{size}"
            size_dir.mkdir(exist_ok=True)
            for label in tile_labels:
                safe_name = label.replace(" ", "_").replace("/", "_")
                src = Image.open(out_dir / f"{safe_name}.png").convert("RGBA")
                resized = resize_sprite(src, size, num_colors=args.num_colors)
                resized.save(size_dir / f"{safe_name}.png")
            print(f"  Resized to {size}x{size}")
        print(f"Saved {len(sizes)} size variants")


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
    elif args.command == "tile":
        try:
            asyncio.run(_tile(args))
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
