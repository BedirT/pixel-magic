"""Atlas metadata and QA report models — compatible with TexturePacker/PixiJS format."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QACheckName(str, Enum):
    """Names of QA checks."""

    PALETTE_COMPLIANCE = "palette_compliance"
    ALPHA_COMPLIANCE = "alpha_compliance"
    GRID_COMPLIANCE = "grid_compliance"
    ISLAND_NOISE = "island_noise"
    FRAME_COUNT_MATCH = "frame_count_match"
    FRAME_SIZE_CONSISTENCY = "frame_size_consistency"
    PALETTE_DELTA = "palette_delta"
    TRIM_OFFSET_VALID = "trim_offset_valid"
    ANIM_FLICKER = "anim_flicker"
    PIVOT_DRIFT = "pivot_drift"
    # Vision-based
    VISION_GRID_ALIGNMENT = "vision_grid_alignment"
    VISION_STYLE_ADHERENCE = "vision_style_adherence"
    VISION_SILHOUETTE_CLARITY = "vision_silhouette_clarity"
    VISION_CROSS_FRAME_CONSISTENCY = "vision_cross_frame_consistency"


@dataclass
class QACheck:
    """Result of a single QA check."""

    name: QACheckName
    passed: bool
    score: float = 1.0
    details: str = ""


@dataclass
class QAReport:
    """Full QA report for a set of sprite assets."""

    checks: list[QACheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[QACheck]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [
                {
                    "name": c.name.value,
                    "passed": c.passed,
                    "score": c.score,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


@dataclass
class Rect:
    """A rectangle (x, y, w, h)."""

    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class Size:
    """Width and height."""

    w: int
    h: int

    def to_dict(self) -> dict:
        return {"w": self.w, "h": self.h}


@dataclass
class Pivot:
    """Normalized pivot point (0-1)."""

    x: float = 0.5
    y: float = 1.0  # bottom-center by default (feet)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


@dataclass
class FrameEntry:
    """Metadata for a single frame in the atlas."""

    name: str
    frame: Rect
    rotated: bool = False
    trimmed: bool = False
    sprite_source_size: Rect | None = None
    source_size: Size | None = None
    pivot: Pivot = field(default_factory=Pivot)
    duration_ms: int = 100
    qa: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "frame": self.frame.to_dict(),
            "rotated": self.rotated,
            "trimmed": self.trimmed,
            "pivot": self.pivot.to_dict(),
            "duration_ms": self.duration_ms,
        }
        if self.sprite_source_size:
            d["spriteSourceSize"] = self.sprite_source_size.to_dict()
        if self.source_size:
            d["sourceSize"] = self.source_size.to_dict()
        if self.qa:
            d["qa"] = self.qa
        return d


@dataclass
class AnimationEntry:
    """An animation defined as an ordered list of frame names."""

    name: str
    direction: str
    frame_names: list[str] = field(default_factory=list)
    is_looping: bool = True

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "frames": self.frame_names,
            "looping": self.is_looping,
        }


@dataclass
class GridInfo:
    """Info about the inferred pixel grid."""

    macro_size: int
    offset_x: int = 0
    offset_y: int = 0
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "macro_size": self.macro_size,
            "offset": {"x": self.offset_x, "y": self.offset_y},
            "confidence": self.confidence,
        }


@dataclass
class PaletteInfo:
    """Palette info stored in atlas metadata."""

    mode: str
    colors_hex: list[str]
    max_colors: int
    color_space: str = "oklab"
    dither_type: str = "none"
    dither_strength: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "colors_rgba": self.colors_hex,
            "max_colors": self.max_colors,
            "color_space": self.color_space,
            "dither": {"type": self.dither_type, "strength": self.dither_strength},
        }


@dataclass
class AtlasMetadata:
    """Full atlas metadata in TexturePacker/PixiJS-compatible format."""

    schema_version: str = "sprite-atlas-v1"
    source_name: str = ""
    content_hash: str = ""
    image_file: str = "atlas.png"
    atlas_size: Size = field(default_factory=lambda: Size(0, 0))
    scale: str = "1"
    grid_info: GridInfo | None = None
    palette_info: PaletteInfo | None = None
    alpha_policy: str = "binary"
    frames: dict[str, FrameEntry] = field(default_factory=dict)
    animations: dict[str, AnimationEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        meta: dict = {
            "schema": self.schema_version,
            "source": {"name": self.source_name, "content_hash": self.content_hash},
            "image": self.image_file,
            "size": self.atlas_size.to_dict(),
            "scale": self.scale,
            "alpha_policy": {"mode": self.alpha_policy},
        }
        if self.grid_info:
            meta["pixel_grid"] = self.grid_info.to_dict()
        if self.palette_info:
            meta["palette"] = self.palette_info.to_dict()

        frames_dict = {name: entry.to_dict() for name, entry in self.frames.items()}
        anims_dict = {name: entry.to_dict() for name, entry in self.animations.items()}

        return {"meta": meta, "frames": frames_dict, "animations": anims_dict}
