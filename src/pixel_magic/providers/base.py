"""Minimal provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image


@dataclass
class GenerationConfig:
    image_size: str = "1024x1024"


@dataclass
class UsageStats:
    """Token usage from a single API call."""
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0


@dataclass
class GenerationResult:
    image: Image.Image
    prompt_used: str = ""
    model_used: str = ""
    metadata: dict = field(default_factory=dict)
    usage: UsageStats = field(default_factory=UsageStats)
