"""OpenAI image generation provider."""

from __future__ import annotations

import asyncio
import base64
import io
import logging

from PIL import Image

from pixel_magic.providers.base import GenerationConfig, GenerationResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, quality: str = "medium"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._quality = quality

    async def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        config = config or GenerationConfig()
        size = config.image_size or "1024x1024"

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._client.images.generate,
                    model=self._model,
                    prompt=prompt,
                    n=1,
                    size=size,
                    quality=self._quality,
                    background="transparent",
                    output_format="png",
                )
                img_data = response.data[0]
                image = _decode_b64_image(img_data.b64_json)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt,
                    model_used=self._model,
                )
            except Exception as e:
                delay = BASE_DELAY * (2**attempt)
                logger.warning("Attempt %d failed: %s. Retrying in %.1fs", attempt + 1, e, delay)
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(delay)

        raise RuntimeError("OpenAI generation failed after all retries")


def _decode_b64_image(b64_json: str) -> Image.Image:
    img_bytes = base64.b64decode(b64_json)
    return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
