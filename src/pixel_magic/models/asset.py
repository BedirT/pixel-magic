"""Sprite asset data models — characters, animations, frames, directions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PIL import Image


class DirectionMode(str, Enum):
    """How many directions a character sprite set covers."""

    FOUR = "4"
    EIGHT = "8"


class Direction(str, Enum):
    """Isometric sprite directions. Named by world-space compass."""

    S = "south"
    SE = "south_east"
    E = "east"
    NE = "north_east"
    N = "north"
    # Derived by horizontal flip:
    SW = "south_west"
    W = "west"
    NW = "north_west"

    @staticmethod
    def unique_for_mode(mode: DirectionMode) -> list[Direction]:
        """Return the directions that need unique generation (rest are flipped)."""
        if mode == DirectionMode.FOUR:
            return [Direction.S, Direction.E]
        return [Direction.S, Direction.SE, Direction.E, Direction.NE, Direction.N]

    @staticmethod
    def flip_pairs() -> dict[Direction, Direction]:
        """Map of derived direction → source direction to flip horizontally."""
        return {
            Direction.N: Direction.S,  # 4-dir: N flips from S
            Direction.W: Direction.E,  # 4-dir: W flips from E
            Direction.SW: Direction.SE,
            Direction.NW: Direction.NE,
        }

    @staticmethod
    def all_for_mode(mode: DirectionMode) -> list[Direction]:
        """Return all directions (unique + flipped) for a mode."""
        if mode == DirectionMode.FOUR:
            return [Direction.S, Direction.E, Direction.N, Direction.W]
        return list(Direction)


class CompositeLayout(str, Enum):
    """How sprites are arranged in a composite image."""

    HORIZONTAL_STRIP = "horizontal_strip"
    VERTICAL_STRIP = "vertical_strip"
    GRID = "grid"
    AUTO_DETECT = "auto_detect"


@dataclass
class AnimationDef:
    """Definition of a single animation clip."""

    name: str
    frame_count: int
    description: str
    duration_ms: int = 100
    is_looping: bool = True


# Default animation presets that users can pick from
DEFAULT_ANIMATIONS: dict[str, AnimationDef] = {
    "idle": AnimationDef("idle", 4, "breathing idle stance", 150, True),
    "walk": AnimationDef("walk", 6, "walking cycle", 100, True),
    "run": AnimationDef("run", 6, "running cycle", 80, True),
    "attack": AnimationDef("attack", 4, "melee attack swing", 80, False),
    "hurt": AnimationDef("hurt", 2, "taking damage flinch", 120, False),
    "death": AnimationDef("death", 4, "falling death", 120, False),
    "cast": AnimationDef("cast", 5, "magic casting", 100, False),
}


@dataclass
class SpriteAsset:
    """A single sprite frame with its metadata."""

    image: Image.Image
    direction: Direction | None = None
    animation_name: str | None = None
    frame_index: int = 0

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height


@dataclass
class AnimationClip:
    """A sequence of frames for one animation in one direction."""

    name: str
    direction: Direction
    frames: list[SpriteAsset] = field(default_factory=list)
    duration_ms: int = 100
    is_looping: bool = True

    @property
    def frame_count(self) -> int:
        return len(self.frames)


@dataclass
class CharacterSpec:
    """Full specification for generating a character sprite set."""

    name: str
    description: str
    style: str = "16-bit SNES RPG style"
    direction_mode: DirectionMode = DirectionMode.FOUR
    resolution: str = "64x64"
    max_colors: int = 16
    palette_hint: str = ""
    animations: dict[str, AnimationDef] = field(default_factory=lambda: {
        "idle": DEFAULT_ANIMATIONS["idle"],
        "walk": DEFAULT_ANIMATIONS["walk"],
    })


@dataclass
class TilesetSpec:
    """Specification for generating an isometric tileset."""

    name: str
    biome: str
    tile_types: list[str]
    tile_width: int = 64
    tile_height: int = 32
    style: str = "16-bit SNES RPG style"
    max_colors: int = 16


@dataclass
class ItemSpec:
    """Specification for generating item/pickup sprites."""

    descriptions: list[str]
    resolution: str = "32x32"
    style: str = "16-bit SNES RPG style"
    max_colors: int = 16
    view: str = "front-facing icon"


@dataclass
class EffectSpec:
    """Specification for generating an animated visual effect."""

    description: str
    frame_count: int = 6
    resolution: str = "64x64"
    style: str = "16-bit SNES RPG style"
    max_colors: int = 12
    color_emphasis: str = ""


@dataclass
class UIElementSpec:
    """Specification for generating UI elements."""

    descriptions: list[str]
    resolution: str = "64x64"
    style: str = "16-bit RPG UI style"
    max_colors: int = 8


@dataclass
class GeneratedAsset:
    """Result of a complete generation + processing workflow."""

    name: str
    atlas_path: Path | None = None
    metadata_path: Path | None = None
    individual_frames_dir: Path | None = None
    godot_resource_path: Path | None = None
    qa_report: dict | None = None
    clips: list[AnimationClip] = field(default_factory=list)
