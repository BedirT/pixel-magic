"""Google Gemini image generation provider."""

from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image

from pixel_magic.providers.base import GenerationConfig, GenerationResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 5.0
RETRY_STATUS_CODES = {429, 500, 503}


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        return await self._generate_content(contents=prompt, prompt_text=prompt)

    async def generate_with_images(
        self,
        prompt: str,
        images: list[Image.Image],
        config: GenerationConfig | None = None,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GenerationResult:
        contents: list[Image.Image | str] = [*images, prompt]
        return await self._generate_content(
            contents=contents,
            prompt_text=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    async def _generate_content(
        self,
        contents,
        prompt_text: str,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GenerationResult:
        from google.genai import types

        gen_config: dict = {"response_modalities": ["IMAGE", "TEXT"]}
        if aspect_ratio or image_size:
            img_cfg: dict = {}
            if aspect_ratio:
                img_cfg["aspect_ratio"] = aspect_ratio
            if image_size:
                img_cfg["image_size"] = image_size
            gen_config["image_config"] = types.ImageConfig(**img_cfg)

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model,
                    contents=contents,
                    config=types.GenerateContentConfig(**gen_config),
                )
                image = _extract_image(response)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt_text,
                    model_used=self._model,
                )
            except Exception as e:
                if _is_retryable(e) and attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2**attempt)
                    logger.warning("Attempt %d failed: %s. Retrying in %.1fs", attempt + 1, e, delay)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise RuntimeError("Gemini generation failed after all retries")


def _extract_image(response) -> Image.Image:
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")
    raise RuntimeError("No image found in Gemini response.")


def _is_retryable(error: Exception) -> bool:
    error_str = str(error)
    return any(str(code) in error_str for code in RETRY_STATUS_CODES)
