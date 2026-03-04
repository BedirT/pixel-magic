"""Gemini (Google GenAI) image generation provider."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import time

from PIL import Image

from pixel_magic.providers.base import (
    GenerationConfig,
    GenerationResult,
    ImageProvider,
    Session,
)

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 3
BASE_DELAY = 1.0
RETRY_STATUS_CODES = {429, 500, 503}


def _image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class GeminiSession(Session):
    """Multi-turn Gemini chat session for iterative sprite generation."""

    def __init__(self, chat, model: str):
        self._chat = chat
        self._model = model

    async def send(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        from google.genai import types

        parts: list = []
        if reference_images:
            for ref in reference_images:
                img_bytes = _image_to_bytes(ref)
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        parts.append(prompt)

        response = await asyncio.to_thread(self._chat.send_message, parts)

        image = _extract_image(response)
        return GenerationResult(
            image=image,
            prompt_used=prompt,
            model_used=self._model,
        )

    async def close(self) -> None:
        self._chat = None


class GeminiProvider(ImageProvider):
    """Google Gemini image generation provider."""

    def __init__(self, api_key: str, model: str, image_model: str, thinking_level: str = "minimal"):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._image_model = image_model
        self._thinking_level = thinking_level

    async def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        config = config or GenerationConfig()
        return await self._generate_impl(prompt, references=None, config=config)

    async def generate_with_references(
        self,
        prompt: str,
        reference_images: list[Image.Image],
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        config = config or GenerationConfig()
        return await self._generate_impl(prompt, references=reference_images, config=config)

    async def _generate_impl(
        self,
        prompt: str,
        references: list[Image.Image] | None,
        config: GenerationConfig,
    ) -> GenerationResult:
        from google.genai import types

        contents: list = []
        if references:
            for ref in references:
                img_bytes = _image_to_bytes(ref)
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        contents.append(prompt)

        gen_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._image_model,
                    contents=contents,
                    config=gen_config,
                )
                image = _extract_image(response)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt,
                    model_used=self._image_model,
                )
            except Exception as e:
                delay = BASE_DELAY * (2**attempt)
                logger.warning(
                    "Gemini generation attempt %d failed: %s. Retrying in %.1fs",
                    attempt + 1, e, delay,
                )
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(delay)

        raise RuntimeError("Gemini generation failed after all retries")  # unreachable

    async def start_session(
        self,
        config: GenerationConfig | None = None,
    ) -> GeminiSession:
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )

        chat = self._client.chats.create(
            model=self._image_model,
            config=gen_config,
        )
        return GeminiSession(chat, self._image_model)

    async def evaluate_image(
        self,
        image: Image.Image,
        prompt: str,
    ) -> dict:
        """Use Gemini's vision to evaluate a sprite image."""
        from google.genai import types

        img_bytes = _image_to_bytes(image)
        contents = [
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            prompt,
        ]

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=contents,
            config=gen_config,
        )

        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse Gemini evaluation response as JSON")
            return {"error": "Failed to parse response", "raw": str(response.text)}

    async def close(self) -> None:
        self._client = None


def _extract_image(response) -> Image.Image:
    """Extract the first image from a Gemini response."""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data is not None:
                return Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")

    raise RuntimeError(
        "No image found in Gemini response. "
        "The model may have refused the request or returned text only."
    )
