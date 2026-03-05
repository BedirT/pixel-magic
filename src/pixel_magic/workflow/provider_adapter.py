"""Unified provider adapter for OpenAI and Gemini image backends."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.providers.base import GenerationConfig, GenerationResult, ImageProvider


def create_provider(settings: Settings) -> ImageProvider:
    """Create provider from runtime settings."""
    if settings.provider == "openai":
        from pixel_magic.providers.openai import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            quality=settings.openai_quality,
        )

    from pixel_magic.providers.gemini import GeminiProvider

    return GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_model,
        image_model=settings.gemini_image_model,
        fallback_image_model=settings.gemini_image_fallback_model,
        enable_fallback=settings.gemini_enable_image_fallback,
        fallback_after_seconds=settings.gemini_fallback_timeout_s,
    )


@dataclass
class ProviderAdapter:
    """Thin wrapper that normalizes generation and evaluation usage."""

    provider: ImageProvider
    settings: Settings

    @property
    def provider_name(self) -> str:
        return self.settings.provider

    @property
    def model_name(self) -> str:
        if self.settings.provider == "openai":
            return self.settings.openai_model
        return self.settings.gemini_image_model

    async def generate(
        self,
        prompt: str,
        references: list[Image.Image] | None = None,
    ) -> GenerationResult:
        """Generate an image with optional references."""
        config = GenerationConfig(
            image_size=self.settings.image_size,
            quality=self.settings.openai_quality,
            thinking_level=self.settings.gemini_thinking_level,
        )
        if references:
            return await self.provider.generate_with_references(prompt, references, config)
        return await self.provider.generate(prompt, config)

    async def evaluate(self, image: Image.Image, prompt: str) -> dict:
        """Evaluate generated content through provider vision endpoint."""
        return await self.provider.evaluate_image(image, prompt)

    async def close(self) -> None:
        """Release provider resources."""
        await self.provider.close()
