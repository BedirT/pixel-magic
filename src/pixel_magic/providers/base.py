"""Minimal provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image


@dataclass
class GenerationConfig:
    image_size: str = "1024x1024"


@dataclass
class GenerationResult:
    image: Image.Image
    prompt_used: str = ""
    model_used: str = ""
    metadata: dict = field(default_factory=dict)
