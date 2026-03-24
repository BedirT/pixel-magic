"""CLI entry point for pixel-magic."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


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
    gen.add_argument("--provider", choices=["openai", "gemini"], help="Override provider (default: from .env)")
    gen.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    gen.add_argument("--resolution", default="64x64", help="Target resolution per view (default: 64x64)")
    gen.add_argument("--max-colors", type=int, default=16, help="Max color count (default: 16)")
    gen.add_argument("--style", default="16-bit SNES RPG style", help="Art style")
    gen.add_argument("--palette-hint", default="", help="Color palette hint")

    return parser


def _view_labels(directions: int) -> list[str]:
    """Return direction labels matching the prompt view order."""
    if directions == 4:
        return ["front_left", "back_right"]
    return ["back", "back_right", "right", "front_right", "front"]


async def _generate(args: argparse.Namespace) -> None:
    from pixel_magic.config import Settings
    from pixel_magic.prompts import build_character_sheet_prompt

    settings = Settings()
    provider_name = args.provider or settings.provider

    # Build prompt
    prompt = build_character_sheet_prompt(
        character_description=args.description,
        direction_mode=args.directions,
        style=args.style,
        resolution=args.resolution,
        max_colors=args.max_colors,
        palette_hint=args.palette_hint,
        provider=provider_name,
        chromakey_color=settings.chromakey_color,
    )

    # Create provider
    if provider_name == "openai":
        from pixel_magic.providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            quality=settings.openai_quality,
        )
    else:
        from pixel_magic.providers.gemini import GeminiProvider

        provider = GeminiProvider(
            api_key=settings.google_api_key,
            model=settings.gemini_image_model,
        )

    # Generate
    view_count = 2 if args.directions == 4 else 5
    print(f"Generating {args.name} ({view_count} views, {provider_name})...")
    result = await provider.generate(prompt)

    # Save raw image — zero processing
    out_dir = Path(args.output_dir) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.png"
    result.image.save(raw_path)
    print(f"Saved raw: {raw_path} ({result.image.width}x{result.image.height})")

    # Remove chromakey background for Gemini images
    if provider_name == "gemini":
        from pixel_magic.background import remove_background

        sheet = remove_background(result.image)
        sheet_path = out_dir / "sheet.png"
        sheet.save(sheet_path)
        print(f"Saved sheet: {sheet_path} (background removed)")
    else:
        sheet = result.image

    # Extract individual sprites
    from pixel_magic.extract import extract_sprites

    sprites = extract_sprites(sheet, expected_count=view_count)
    if sprites:
        views_dir = out_dir / "views"
        views_dir.mkdir(exist_ok=True)
        view_labels = _view_labels(args.directions)
        for i, sprite in enumerate(sprites):
            label = view_labels[i] if i < len(view_labels) else f"view_{i}"
            sprite_path = views_dir / f"{label}.png"
            sprite.save(sprite_path)
            print(f"  {label}: {sprite.width}x{sprite.height}")
        print(f"Extracted {len(sprites)} sprites to {views_dir}")
    else:
        print("Warning: could not extract individual sprites from sheet")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "generate":
        asyncio.run(_generate(args))


if __name__ == "__main__":
    main()
