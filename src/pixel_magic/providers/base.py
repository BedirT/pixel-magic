"""Abstract image provider protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class GenerationConfig:
    """Configuration for a single image generation call."""

    image_size: str = "1024x1024"
    aspect_ratio: str = "1:1"
    thinking_level: str = "minimal"
    quality: str = "medium"


@dataclass
class GenerationResult:
    """Result from an image generation call."""

    image: Image.Image
    prompt_used: str = ""
    model_used: str = ""
    tokens_used: int = 0
    metadata: dict = field(default_factory=dict)


class Session(ABC):
    """A multi-turn generation session for iterative refinement."""

    @abstractmethod
    async def send(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        """Send a message in the session and get a generated image back."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the session and free resources."""
        ...


class ImageProvider(ABC):
    """Abstract interface for AI image generation providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        """Generate a single image from a text prompt."""
        ...

    @abstractmethod
    async def generate_with_references(
        self,
        prompt: str,
        reference_images: list[Image.Image],
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        """Generate an image using reference images for consistency."""
        ...

    @abstractmethod
    async def start_session(
        self,
        config: GenerationConfig | None = None,
    ) -> Session:
        """Start a multi-turn generation session."""
        ...

    @abstractmethod
    async def evaluate_image(
        self,
        image: Image.Image,
        prompt: str,
    ) -> dict:
        """Use the provider's vision capability to evaluate an image.

        Returns structured JSON with evaluation scores.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Cleanup provider resources."""
        ...
