"""OpenAI image generation provider."""

from __future__ import annotations

import asyncio
import base64
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
from pixel_magic.tracing import attach_multimodal_input, attach_output_image, get_tracer
from pixel_magic.usage import build_usage_entry, normalize_usage_metadata

logger = logging.getLogger(__name__)
_tracer = get_tracer("pixel_magic.providers.openai")

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

        # Use a multimodal mainline model for the Responses API; gpt-image-*
        # handles the actual image generation via the image_generation tool.
        chat_model = _RESPONSES_CHAT_MODEL if reference_images else self._model
        kwargs: dict = {
            "model": chat_model,
            "input": [{"role": "user", "content": input_parts}],
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


# Mainline model used for the Responses API (image_generation tool).
# gpt-image-* models are image-only; Responses API calls must use a
# multimodal model that can understand reference images and invoke tools.
_RESPONSES_CHAT_MODEL = "gpt-5-mini"


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

        with _tracer.start_as_current_span("openai.generate_image") as span:
            span.set_attribute("llm.model", self._model)
            span.set_attribute("llm.prompt_length", len(prompt))
            span.set_attribute("llm.has_references", False)
            attach_multimodal_input(span, prompt=prompt)

            for attempt in range(MAX_RETRIES):
                try:
                    t0 = time.monotonic()
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
                    span.set_attribute("llm.duration_s", round(time.monotonic() - t0, 2))
                    img_data = response.data[0]
                    image = _decode_b64_image(img_data.b64_json)
                    metadata = _extract_openai_metadata(
                        response=response,
                        model_used=self._model,
                        size=size,
                        quality=self._quality,
                        endpoint="images.generate",
                        reference_count=0,
                    )
                    _record_usage_on_span(span, metadata)
                    span.set_attribute("llm.output_size", f"{image.width}x{image.height}")
                    attach_output_image(span, image)
                    return GenerationResult(
                        image=image,
                        prompt_used=prompt,
                        model_used=self._model,
                        metadata=metadata,
                    )
                except Exception as e:
                    delay = BASE_DELAY * (2**attempt)
                    logger.warning(
                        "OpenAI generation attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1, e, delay,
                    )
                    span.add_event("retry", {
                        "attempt": attempt + 1,
                        "error": str(e),
                        "delay_s": delay,
                    })
                    if attempt == MAX_RETRIES - 1:
                        span.set_attribute("error", True)
                        span.set_attribute("error.message", str(e))
                        raise
                    await asyncio.sleep(delay)

        raise RuntimeError("OpenAI generation failed after all retries")

    async def generate_with_references(
        self,
        prompt: str,
        reference_images: list[Image.Image],
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        # OpenAI: use Responses API with a mainline model for reference-based generation
        config = config or GenerationConfig()
        content_parts: list = []
        for ref in reference_images:
            b64 = _image_to_base64(ref)
            content_parts.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{b64}",
            })
        content_parts.append({"type": "input_text", "text": prompt})

        with _tracer.start_as_current_span("openai.generate_image") as span:
            span.set_attribute("llm.model", _RESPONSES_CHAT_MODEL)
            span.set_attribute("llm.prompt_length", len(prompt))
            span.set_attribute("llm.has_references", True)
            attach_multimodal_input(span, prompt=prompt, reference_images=reference_images)

            for attempt in range(MAX_RETRIES):
                try:
                    t0 = time.monotonic()
                    response = await asyncio.to_thread(
                        self._client.responses.create,
                        model=_RESPONSES_CHAT_MODEL,
                        input=[{"role": "user", "content": content_parts}],
                        tools=[{
                            "type": "image_generation",
                            "quality": self._quality,
                            "background": "transparent",
                            "output_format": "png",
                        }],
                    )
                    span.set_attribute("llm.duration_s", round(time.monotonic() - t0, 2))
                    image = _extract_openai_image(response)
                    metadata = _extract_openai_metadata(
                        response=response,
                        model_used=_RESPONSES_CHAT_MODEL,
                        size=config.image_size,
                        quality=self._quality,
                        endpoint="responses.create",
                        reference_count=len(reference_images),
                    )
                    _record_usage_on_span(span, metadata)
                    span.set_attribute("llm.output_size", f"{image.width}x{image.height}")
                    attach_output_image(span, image)
                    return GenerationResult(
                        image=image,
                        prompt_used=prompt,
                        model_used=self._model,
                        metadata=metadata,
                    )
                except Exception as e:
                    delay = BASE_DELAY * (2**attempt)
                    logger.warning(
                        "OpenAI ref generation attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1, e, delay,
                    )
                    span.add_event("retry", {
                        "attempt": attempt + 1,
                        "error": str(e),
                        "delay_s": delay,
                    })
                    if attempt == MAX_RETRIES - 1:
                        span.set_attribute("error", True)
                        span.set_attribute("error.message", str(e))
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
            model="gpt-5-mini",
            messages=messages,
            response_format={"type": "json_object"},
        )

        usage_entry = build_usage_entry(
            _extract_openai_metadata(
                response=response,
                model_used="gpt-5-mini",
                size="vision",
                quality="n/a",
                endpoint="chat.completions.create",
                reference_count=1,
            ),
            provider="openai",
            model="gpt-5-mini",
        )

        try:
            payload = json.loads(response.choices[0].message.content)
            if isinstance(payload, dict):
                payload["_usage"] = usage_entry
            return payload
        except (json.JSONDecodeError, AttributeError, IndexError):
            logger.warning("Failed to parse OpenAI evaluation response as JSON")
            return {"error": "Failed to parse response", "_usage": usage_entry}

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


def _extract_openai_metadata(
    response,
    model_used: str,
    size: str,
    quality: str,
    endpoint: str,
    reference_count: int = 0,
) -> dict:
    """Extract best-effort usage metadata from OpenAI responses."""
    usage_dict: dict[str, int] = {}
    usage = getattr(response, "usage", None)

    if usage is not None:
        for key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ):
            value = getattr(usage, key, None)
            if isinstance(value, int):
                usage_dict[key] = value

    metadata = {
        "provider": "openai",
        "model": model_used,
        "size": size,
        "image_size": size,
        "quality": quality,
        "endpoint": endpoint,
        "reference_count": reference_count,
        "usage": usage_dict,
        "raw_usage": usage_dict,
    }
    metadata["normalized_usage"] = normalize_usage_metadata(metadata, provider="openai")
    metadata["cost_inputs"] = {
        "provider": "openai",
        "model": model_used,
        **metadata["normalized_usage"],
    }
    return metadata


def _record_usage_on_span(span, metadata: dict) -> None:
    normalized = metadata.get("normalized_usage", {})
    for key, value in normalized.items():
        span.set_attribute(f"llm.usage.{key}", value)
    # OpenInference semantic conventions for Phoenix UI
    span.set_attribute("llm.token_count.prompt", normalized.get("input_tokens", 0))
    span.set_attribute("llm.token_count.completion", normalized.get("output_tokens", 0))
    span.set_attribute("llm.token_count.total", normalized.get("total_tokens", 0))
