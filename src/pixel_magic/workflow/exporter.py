"""Deterministic exporter for workflow v2 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from pixel_magic.workflow.models import ArtifactManifest


def _safe_name(value: str) -> str:
    allowed = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
        else:
            allowed.append("_")
    safe = "".join(allowed).strip("_")
    return safe or "asset"


def _pack_atlas(groups: dict[str, list[Image.Image]]) -> Image.Image:
    items: list[tuple[str, Image.Image]] = []
    for group_name, frames in groups.items():
        for idx, frame in enumerate(frames):
            items.append((f"{group_name}_{idx:03d}", frame))

    if not items:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    max_height = max(img.height for _, img in items)
    total_width = sum(img.width for _, img in items) + max(0, len(items) - 1)
    atlas = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))

    x = 0
    for _, image in items:
        atlas.paste(image, (x, max_height - image.height))
        x += image.width + 1

    return atlas


def export_assets(
    *,
    groups: dict[str, list[Image.Image]],
    raw_images: dict[str, Image.Image],
    output_root: Path,
    name: str,
) -> ArtifactManifest:
    """Export raw composites, cleaned frames, atlas, and metadata."""
    safe_name = _safe_name(name)
    output_dir = output_root / safe_name
    frames_dir = output_dir / "frames"
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_paths: dict[str, str] = {}
    frame_paths: dict[str, list[str]] = {}

    for key, image in raw_images.items():
        raw_path = raw_dir / f"{_safe_name(key)}.png"
        image.save(raw_path)
        raw_paths[key] = str(raw_path)

    total_frames = 0
    for group_name, frames in groups.items():
        paths: list[str] = []
        safe_group = _safe_name(group_name)
        for idx, frame in enumerate(frames):
            frame_path = frames_dir / f"{safe_name}_{safe_group}_{idx:03d}.png"
            frame.save(frame_path)
            paths.append(str(frame_path))
            total_frames += 1
        frame_paths[group_name] = paths

    atlas = _pack_atlas(groups)
    atlas_path = output_dir / f"{safe_name}_atlas.png"
    atlas.save(atlas_path)

    metadata = {
        "name": safe_name,
        "total_frames": total_frames,
        "groups": {k: len(v) for k, v in groups.items()},
        "raw_paths": raw_paths,
        "frame_paths": frame_paths,
        "atlas_path": str(atlas_path),
    }
    metadata_path = output_dir / f"{safe_name}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return ArtifactManifest(
        output_dir=str(output_dir),
        atlas_path=str(atlas_path),
        metadata_path=str(metadata_path),
        raw_paths=raw_paths,
        frame_paths=frame_paths,
        total_frames=total_frames,
    )
