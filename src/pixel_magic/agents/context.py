"""Shared context for all sprite generation agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.providers.base import ImageProvider, Session


@dataclass
class AgentContext:
    """Mutable context shared across agent tool calls.

    Images are stored by string key so the LLM agent can reference them
    without passing raw binary data.  The ``saved_clips`` list collects
    structured output that the runner converts into AnimationClip objects
    after the agent finishes.
    """

    provider: ImageProvider
    settings: Settings
    output_dir: Path

    # Gemini multi-turn editing session (created lazily)
    session: Session | None = None

    # Image store: key -> PIL Image
    images: dict[str, Image.Image] = field(default_factory=dict)
    _counter: int = 0

    # Structured results produced by save_frames tool
    saved_clips: list[dict[str, Any]] = field(default_factory=list)

    def store_image(self, image: Image.Image, prefix: str = "img") -> str:
        """Store an image and return its key."""
        self._counter += 1
        key = f"{prefix}_{self._counter:03d}"
        self.images[key] = image
        return key

    def get_image(self, key: str) -> Image.Image:
        """Retrieve an image by key, raising KeyError if not found."""
        if key not in self.images:
            available = ", ".join(sorted(self.images.keys())[:10])
            raise KeyError(
                f"Image key '{key}' not found. Available: {available}"
            )
        return self.images[key]
