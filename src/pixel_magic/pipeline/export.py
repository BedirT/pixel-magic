"""Export — atlas packing, JSON metadata, individual PNGs, Godot .tres."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from pixel_magic.models.asset import AnimationClip, Direction, DirectionMode, SpriteAsset
from pixel_magic.models.metadata import (
    AnimationEntry,
    AtlasMetadata,
    FrameEntry,
    GridInfo,
    PaletteInfo,
    Pivot,
    Rect,
    Size,
)
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.ingest import trim_transparent

logger = logging.getLogger(__name__)


# ── Direction flipping ────────────────────────────────────────────────

def generate_flipped_directions(
    clips: dict[str, list[AnimationClip]],
    direction_mode: DirectionMode,
) -> dict[str, list[AnimationClip]]:
    """Generate horizontally flipped clips for derived directions.

    For 4-dir: N from S, W from E.
    For 8-dir: SW from SE, W from E, NW from NE.
    """
    flip_map = Direction.flip_pairs()
    # Filter to relevant pairs for this mode
    all_dirs = set(Direction.all_for_mode(direction_mode))
    relevant_flips = {k: v for k, v in flip_map.items() if k in all_dirs}

    result = {}
    for anim_name, anim_clips in clips.items():
        new_clips = list(anim_clips)

        # Index existing clips by direction
        dir_clips: dict[Direction, AnimationClip] = {}
        for clip in anim_clips:
            dir_clips[clip.direction] = clip

        for target_dir, source_dir in relevant_flips.items():
            if target_dir in dir_clips:
                continue  # Already exists
            if source_dir not in dir_clips:
                continue  # Source not available

            source_clip = dir_clips[source_dir]
            flipped_frames = []
            for frame in source_clip.frames:
                flipped_img = frame.image.transpose(Image.FLIP_LEFT_RIGHT)
                flipped_frames.append(SpriteAsset(
                    image=flipped_img,
                    direction=target_dir,
                    animation_name=frame.animation_name,
                    frame_index=frame.frame_index,
                ))

            new_clips.append(AnimationClip(
                name=source_clip.name,
                direction=target_dir,
                frames=flipped_frames,
                duration_ms=source_clip.duration_ms,
                is_looping=source_clip.is_looping,
            ))

        result[anim_name] = new_clips

    return result


# ── Atlas packing (simple shelf packer) ───────────────────────────────

def pack_atlas(
    clips: dict[str, list[AnimationClip]],
    padding: int = 1,
    name: str = "sprite",
) -> tuple[Image.Image, AtlasMetadata]:
    """Pack all frames into a single atlas image.

    Uses a simple shelf-packing algorithm.
    Returns the atlas image and its metadata.
    """
    # Collect all frames with their names
    all_frames: list[tuple[str, SpriteAsset, str, str]] = []  # (frame_name, asset, anim_name, direction)

    for anim_name, anim_clips in clips.items():
        for clip in anim_clips:
            dir_name = clip.direction.value if clip.direction else "none"
            for i, frame in enumerate(clip.frames):
                frame_name = f"{anim_name}_{dir_name}_{i:03d}"
                all_frames.append((frame_name, frame, anim_name, dir_name))

    if not all_frames:
        empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        return empty, AtlasMetadata(source_name=name)

    # Trim frames and record offsets
    trimmed_data: list[tuple[str, Image.Image, tuple[int, int, int, int], int, int]] = []
    for frame_name, asset, anim_name, dir_name in all_frames:
        trimmed, (left, top, right, bottom) = trim_transparent(asset.image)
        trimmed_data.append((
            frame_name,
            trimmed,
            (left, top, right, bottom),
            asset.width,
            asset.height,
        ))

    # Simple shelf packing: sort by height descending for better packing
    sorted_items = sorted(
        enumerate(trimmed_data),
        key=lambda x: x[1][1].height,
        reverse=True,
    )

    # Determine atlas dimensions
    max_width = 2048
    x_cursor = 0
    y_cursor = 0
    shelf_height = 0
    positions: dict[int, tuple[int, int]] = {}

    for idx, (frame_name, img, offsets, orig_w, orig_h) in sorted_items:
        fw, fh = img.size

        if x_cursor + fw + padding > max_width:
            # New shelf
            y_cursor += shelf_height + padding
            x_cursor = 0
            shelf_height = 0

        positions[idx] = (x_cursor, y_cursor)
        shelf_height = max(shelf_height, fh)
        x_cursor += fw + padding

    # Final atlas size
    atlas_w = max_width
    atlas_h = y_cursor + shelf_height + padding
    # Round up to power of 2 for GPU friendliness
    atlas_w = _next_pow2(min(atlas_w, max_width))
    atlas_h = _next_pow2(atlas_h)

    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))

    # Build metadata
    meta = AtlasMetadata(
        source_name=name,
        image_file=f"{name}_atlas.png",
        atlas_size=Size(atlas_w, atlas_h),
    )

    # Place frames
    for idx, (frame_name, img, (left, top, right, bottom), orig_w, orig_h) in enumerate(trimmed_data):
        px, py = positions[idx]
        atlas.paste(img, (px, py))

        fw, fh = img.size
        meta.frames[frame_name] = FrameEntry(
            name=frame_name,
            frame=Rect(px, py, fw, fh),
            trimmed=True,
            sprite_source_size=Rect(left, top, fw, fh),
            source_size=Size(orig_w, orig_h),
            pivot=Pivot(0.5, 1.0),
        )

    # Build animation entries
    for anim_name, anim_clips in clips.items():
        for clip in anim_clips:
            dir_name = clip.direction.value if clip.direction else "none"
            entry_name = f"{anim_name}_{dir_name}"
            frame_names = [
                f"{anim_name}_{dir_name}_{i:03d}"
                for i in range(clip.frame_count)
            ]
            meta.animations[entry_name] = AnimationEntry(
                name=entry_name,
                direction=dir_name,
                frame_names=frame_names,
                is_looping=clip.is_looping,
            )

    # Content hash
    atlas_bytes = np.array(atlas).tobytes()
    meta.content_hash = f"sha256:{hashlib.sha256(atlas_bytes).hexdigest()[:16]}"

    return atlas, meta


def _next_pow2(v: int) -> int:
    """Round up to next power of 2."""
    v -= 1
    v |= v >> 1
    v |= v >> 2
    v |= v >> 4
    v |= v >> 8
    v |= v >> 16
    return max(v + 1, 1)


# ── Individual PNG export ─────────────────────────────────────────────

def export_individual_pngs(
    clips: dict[str, list[AnimationClip]],
    output_dir: Path,
    name: str = "sprite",
) -> list[Path]:
    """Save each frame as an individual PNG file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for anim_name, anim_clips in clips.items():
        for clip in anim_clips:
            dir_name = clip.direction.value if clip.direction else "none"
            for i, frame in enumerate(clip.frames):
                filename = f"{name}_{anim_name}_{dir_name}_{i:03d}.png"
                path = output_dir / filename
                frame.image.save(path)
                paths.append(path)

    return paths


# ── JSON metadata export ─────────────────────────────────────────────

def export_json_metadata(meta: AtlasMetadata, output_path: Path) -> Path:
    """Write atlas metadata as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(meta.to_dict(), f, indent=2)
    return output_path


# ── Godot SpriteFrames .tres export ──────────────────────────────────

def export_godot_spriteframes(
    meta: AtlasMetadata,
    atlas_path: str,
    output_path: Path,
) -> Path:
    """Generate a Godot SpriteFrames .tres resource file.

    Creates animation groups referencing atlas regions.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '[gd_resource type="SpriteFrames" load_steps=2 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_path}" id="1"]',
        "",
        "[resource]",
    ]

    # Build animations array
    anim_entries = []
    for anim_key, anim_entry in meta.animations.items():
        frame_data = []
        for frame_name in anim_entry.frame_names:
            if frame_name not in meta.frames:
                continue
            fe = meta.frames[frame_name]
            # AtlasTexture sub-resource reference
            frame_data.append({
                "texture": 'ExtResource("1")',
                "region": f"Rect2({fe.frame.x}, {fe.frame.y}, {fe.frame.w}, {fe.frame.h})",
                "duration": fe.duration_ms / 1000.0,
            })

        # Determine FPS from duration
        fps = 10.0
        if frame_data:
            avg_duration = sum(fd["duration"] for fd in frame_data) / len(frame_data)
            if avg_duration > 0:
                fps = 1.0 / avg_duration

        anim_entries.append((anim_key, anim_entry, frame_data, fps))

    # Write animations
    lines.append("animations = [{")
    for i, (anim_key, anim_entry, frame_data, fps) in enumerate(anim_entries):
        if i > 0:
            lines.append("}, {")
        lines.append(f'"name": &"{anim_key}",')
        lines.append(f'"speed": {fps:.1f},')
        lines.append(f'"loop": {"true" if anim_entry.is_looping else "false"},')
        lines.append('"frames": [{')

        for j, fd in enumerate(frame_data):
            if j > 0:
                lines.append("}, {")
            lines.append(f'"texture": {fd["texture"]},')
            lines.append(f'"region": {fd["region"]},')
            lines.append(f'"duration": {fd["duration"]:.3f}')

        lines.append("}]")

    lines.append("}]")

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return output_path


# ── Godot TileSet .tres export ────────────────────────────────────────

def export_godot_tileset(
    meta: AtlasMetadata,
    atlas_path: str,
    output_path: Path,
    tile_size: tuple[int, int] = (64, 32),
) -> Path:
    """Generate a Godot TileSet .tres for tileset exports."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_path}" id="1"]',
        "",
        "[resource]",
        f'tile_size = Vector2i({tile_size[0]}, {tile_size[1]})',
        "",
        "[sub_resource type=\"TileSetAtlasSource\" id=\"1\"]",
        'texture = ExtResource("1")',
        f'texture_region_size = Vector2i({tile_size[0]}, {tile_size[1]})',
    ]

    # Add tile entries
    for frame_name, fe in meta.frames.items():
        col = fe.frame.x // tile_size[0]
        row = fe.frame.y // tile_size[1]
        lines.append(f"# {frame_name}: atlas coords ({col}, {row})")

    lines.extend([
        "",
        "[resource]",
        'sources/0 = SubResource("1")',
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return output_path


# ── Full export pipeline ──────────────────────────────────────────────

def export_all(
    clips: dict[str, list[AnimationClip]],
    output_dir: Path,
    name: str = "sprite",
    direction_mode: DirectionMode = DirectionMode.FOUR,
    palette: Palette | None = None,
    grid_info: GridInfo | None = None,
    padding: int = 1,
    export_pngs: bool = True,
    export_godot: bool = True,
) -> dict[str, Path]:
    """Run the complete export pipeline.

    1. Generate flipped directions.
    2. Pack atlas.
    3. Export atlas PNG + JSON metadata.
    4. Optionally export individual PNGs.
    5. Optionally export Godot .tres.

    Returns dict of output paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}

    # 1. Generate flipped directions
    full_clips = generate_flipped_directions(clips, direction_mode)

    # 2. Pack atlas
    atlas_img, meta = pack_atlas(full_clips, padding, name)

    # Add palette/grid info if available
    if palette:
        meta.palette_info = PaletteInfo(
            mode="shared",
            colors_hex=palette.to_hex_list(),
            max_colors=palette.size,
        )
    if grid_info:
        meta.grid_info = grid_info

    # 3. Save atlas PNG
    atlas_path = output_dir / f"{name}_atlas.png"
    atlas_img.save(atlas_path)
    outputs["atlas"] = atlas_path

    # 4. Save JSON metadata
    json_path = output_dir / f"{name}_atlas.json"
    export_json_metadata(meta, json_path)
    outputs["metadata"] = json_path

    # 5. Individual PNGs
    if export_pngs:
        pngs_dir = output_dir / "frames"
        export_individual_pngs(full_clips, pngs_dir, name)
        outputs["frames_dir"] = pngs_dir

    # 6. Godot exports
    if export_godot:
        tres_path = output_dir / f"{name}.tres"
        export_godot_spriteframes(
            meta,
            f"res://{atlas_path.name}",
            tres_path,
        )
        outputs["godot_spriteframes"] = tres_path

    logger.info("Exported %s: %s", name, ", ".join(str(v) for v in outputs.values()))
    return outputs
