"""Palette and color-related data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PaletteMode(str, Enum):
    """How the palette is determined."""

    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    SHARED = "shared"


class DitherType(str, Enum):
    """Dithering algorithm type."""

    NONE = "none"
    ORDERED = "ordered"
    ERROR_DIFFUSION = "error_diffusion"


class BayerSize(int, Enum):
    """Bayer matrix size for ordered dithering."""

    B2 = 2
    B4 = 4
    B8 = 8


@dataclass
class DitherConfig:
    """Configuration for dithering during palette quantization."""

    type: DitherType = DitherType.NONE
    strength: float = 0.3
    bayer_size: BayerSize = BayerSize.B4


@dataclass
class Palette:
    """A color palette — a list of RGBA tuples."""

    name: str
    colors: list[tuple[int, int, int, int]]

    @property
    def size(self) -> int:
        return len(self.colors)

    @classmethod
    def from_hex_file(cls, path: Path) -> Palette:
        """Load a palette from a .hex file (one hex color per line)."""
        colors: list[tuple[int, int, int, int]] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Support both "RRGGBB" and "RRGGBBAA"
                hex_str = line.lstrip("#")
                if len(hex_str) == 6:
                    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                    colors.append((r, g, b, 255))
                elif len(hex_str) == 8:
                    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                    a = int(hex_str[6:8], 16)
                    colors.append((r, g, b, a))
        return cls(name=path.stem, colors=colors)

    def to_hex_list(self) -> list[str]:
        """Export as list of hex strings."""
        result = []
        for r, g, b, a in self.colors:
            if a == 255:
                result.append(f"#{r:02x}{g:02x}{b:02x}")
            else:
                result.append(f"#{r:02x}{g:02x}{b:02x}{a:02x}")
        return result
