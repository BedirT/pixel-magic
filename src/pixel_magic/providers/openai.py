"""OpenAI image generation provider."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging

from PIL import Image

from pixel_magic.providers.base import (
    GenerationConfig,
    GenerationResult,
    ImageProvider,
    Session,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0


def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


class OpenAISession(Session):
    """Multi-turn OpenAI session using Responses API with previous_response_id."""

    def __init__(self, client, model: str, quality: str):
        self._client = client
        self._model = model
        self._quality = quality
        self._previous_response_id: str | None = None

    async def send(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        input_parts: list = []
        if reference_images:
            for ref in reference_images:
                b64 = _image_to_base64(ref)
                input_parts.append({
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{b64}",
                })
        input_parts.append({"type": "input_text", "text": prompt})

        kwargs: dict = {
            "model": self._model,
            "input": input_parts,
            "tools": [{"type": "image_generation", "quality": self._quality, "background": "transparent", "output_format": "png"}],
        }
        if self._previous_response_id:
            kwargs["previous_response_id"] = self._previous_response_id

        response = await asyncio.to_thread(self._client.responses.create, **kwargs)
        self._previous_response_id = response.id

        image = _extract_openai_image(response)
        return GenerationResult(
            image=image,
            prompt_used=prompt,
            model_used=self._model,
        )

    async def close(self) -> None:
        self._previous_response_id = None


class OpenAIProvider(ImageProvider):
    """OpenAI image generation provider with native transparency support."""

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

        size = config.image_size if config.image_size else "1024x1024"

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
                logger.warning(
                    "OpenAI generation attempt %d failed: %s. Retrying in %.1fs",
                    attempt + 1, e, delay,
                )
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(delay)

        raise RuntimeError("OpenAI generation failed after all retries")

    async def generate_with_references(
        self,
        prompt: str,
        reference_images: list[Image.Image],
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        # OpenAI: use Responses API for reference-based generation
        input_parts: list = []
        for ref in reference_images:
            b64 = _image_to_base64(ref)
            input_parts.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{b64}",
            })
        input_parts.append({"type": "input_text", "text": prompt})

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._client.responses.create,
                    model=self._model,
                    input=input_parts,
                    tools=[{
                        "type": "image_generation",
                        "quality": self._quality,
                        "background": "transparent",
                        "output_format": "png",
                    }],
                )
                image = _extract_openai_image(response)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt,
                    model_used=self._model,
                )
            except Exception as e:
                delay = BASE_DELAY * (2**attempt)
                logger.warning(
                    "OpenAI ref generation attempt %d failed: %s. Retrying in %.1fs",
                    attempt + 1, e, delay,
                )
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(delay)

        raise RuntimeError("OpenAI generation failed after all retries")

    async def start_session(
        self,
        config: GenerationConfig | None = None,
    ) -> OpenAISession:
        return OpenAISession(self._client, self._model, self._quality)

    async def evaluate_image(
        self,
        image: Image.Image,
        prompt: str,
    ) -> dict:
        """Use OpenAI vision to evaluate a sprite image."""
        b64 = _image_to_base64(image)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, AttributeError, IndexError):
            logger.warning("Failed to parse OpenAI evaluation response as JSON")
            return {"error": "Failed to parse response"}

    async def close(self) -> None:
        self._client = None


def _decode_b64_image(b64_json: str) -> Image.Image:
    """Decode a base64 image string to PIL Image."""
    img_bytes = base64.b64decode(b64_json)
    return Image.open(io.BytesIO(img_bytes)).convert("RGBA")


def _extract_openai_image(response) -> Image.Image:
    """Extract image from an OpenAI Responses API response."""
    for output in response.output:
        if output.type == "image_generation_call":
            return _decode_b64_image(output.result)
    raise RuntimeError("No image found in OpenAI response.")
