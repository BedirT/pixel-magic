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

from pixel_magic.tracing import attach_multimodal_input, attach_output_image, get_tracer
from pixel_magic.usage import build_usage_entry, normalize_usage_metadata

logger = logging.getLogger(__name__)
_tracer = get_tracer("pixel_magic.providers.gemini")

# Retry config
MAX_RETRIES = 3
BASE_DELAY = 5.0
RETRY_STATUS_CODES = {429, 500, 503}
DEFAULT_FALLBACK_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_FALLBACK_TIMEOUT_S = 120.0

def _image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    import io

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

    def __init__(
        self,
        api_key: str,
        model: str,
        image_model: str,
        thinking_level: str = "minimal",
        fallback_image_model: str | None = DEFAULT_FALLBACK_IMAGE_MODEL,
        enable_fallback: bool = True,
        fallback_after_seconds: float = DEFAULT_FALLBACK_TIMEOUT_S,
    ):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._image_model = image_model
        # Map semantic level to integer token budget for ThinkingConfig
        _level_to_budget = {"minimal": 0, "medium": 8192, "high": 24576}
        self._thinking_budget: int = _level_to_budget.get(thinking_level, 0)
        self._fallback_image_model = fallback_image_model
        self._enable_fallback = enable_fallback
        self._fallback_after_seconds = max(0.0, fallback_after_seconds)

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

        with _tracer.start_as_current_span("gemini.generate_image") as span:
            span.set_attribute("llm.prompt_length", len(prompt))
            span.set_attribute("llm.has_references", bool(references))
            attach_multimodal_input(span, prompt=prompt, reference_images=references)

            contents: list = []
            if references:
                for ref in references:
                    img_bytes = _image_to_bytes(ref)
                    contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
                span.set_attribute("llm.reference_count", len(references))
            contents.append(prompt)

            gen_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    image_size="1K",
                ),
            )
            primary_model = self._image_model
            fallback_model = self._fallback_image_model
            can_fallback = (
                self._enable_fallback
                and bool(fallback_model)
                and fallback_model != primary_model
            )
            span.set_attribute("llm.model", primary_model)

            try:
                t0 = time.monotonic()
                response = await self._generate_with_retries(
                    model_name=primary_model,
                    contents=contents,
                    gen_config=gen_config,
                    timeout_budget_s=self._fallback_after_seconds if can_fallback else None,
                )
                span.set_attribute("llm.duration_s", round(time.monotonic() - t0, 2))
                span.set_attribute("llm.fallback_used", False)

                metadata = _extract_gemini_metadata(
                    response,
                    primary_model,
                    endpoint="models.generate_content",
                    image_size="1K",
                    reference_count=len(references or []),
                )
                if can_fallback:
                    metadata["fallback"] = {
                        "enabled": True,
                        "used": False,
                        "primary_model": primary_model,
                        "fallback_model": fallback_model,
                        "timeout_s": self._fallback_after_seconds,
                    }
                # Record token usage on span (both custom and OpenInference conventions)
                normalized = metadata.get("normalized_usage", {})
                for k, v in normalized.items():
                    span.set_attribute(f"llm.usage.{k}", v)
                # OpenInference semantic conventions for Phoenix UI
                span.set_attribute("llm.token_count.prompt", normalized.get("input_tokens", 0))
                span.set_attribute("llm.token_count.completion", normalized.get("output_tokens", 0))
                span.set_attribute("llm.token_count.total", normalized.get("total_tokens", 0))
                # Also record raw Gemini-specific fields
                raw = metadata.get("raw_usage", {})
                for k, v in raw.items():
                    if isinstance(v, int):
                        span.set_attribute(f"llm.usage.raw.{k}", v)

                image = _extract_image(response)
                span.set_attribute("llm.output_size", f"{image.width}x{image.height}")
                attach_output_image(span, image)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt,
                    model_used=primary_model,
                    metadata=metadata,
                )
            except Exception as primary_error:
                if not can_fallback:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(primary_error))
                    raise

                span.add_event("fallback_triggered", {
                    "primary_error": str(primary_error),
                    "fallback_model": fallback_model,
                })

                logger.warning(
                    "Primary Gemini image model '%s' failed or timed out (%s). "
                    "Falling back to '%s'.",
                    primary_model,
                    primary_error,
                    fallback_model,
                )

                span.set_attribute("llm.model", fallback_model)
                span.set_attribute("llm.fallback_used", True)

                t0 = time.monotonic()
                response = await self._generate_with_retries(
                    model_name=fallback_model,
                    contents=contents,
                    gen_config=gen_config,
                    timeout_budget_s=None,
                )
                span.set_attribute("llm.duration_s", round(time.monotonic() - t0, 2))

                metadata = _extract_gemini_metadata(
                    response,
                    fallback_model,
                    endpoint="models.generate_content",
                    image_size="1K",
                    reference_count=len(references or []),
                )
                metadata["fallback"] = {
                    "enabled": True,
                    "used": True,
                    "primary_model": primary_model,
                    "fallback_model": fallback_model,
                    "timeout_s": self._fallback_after_seconds,
                    "primary_error": str(primary_error),
                }
                normalized = metadata.get("normalized_usage", {})
                for k, v in normalized.items():
                    span.set_attribute(f"llm.usage.{k}", v)
                span.set_attribute("llm.token_count.prompt", normalized.get("input_tokens", 0))
                span.set_attribute("llm.token_count.completion", normalized.get("output_tokens", 0))
                span.set_attribute("llm.token_count.total", normalized.get("total_tokens", 0))
                raw = metadata.get("raw_usage", {})
                for k, v in raw.items():
                    if isinstance(v, int):
                        span.set_attribute(f"llm.usage.raw.{k}", v)

                image = _extract_image(response)
                span.set_attribute("llm.output_size", f"{image.width}x{image.height}")
                attach_output_image(span, image)
                return GenerationResult(
                    image=image,
                    prompt_used=prompt,
                    model_used=fallback_model,
                    metadata=metadata,
                )

    async def _generate_with_retries(
        self,
        model_name: str,
        contents: list,
        gen_config,
        timeout_budget_s: float | None,
    ):
        start = time.monotonic()

        for attempt in range(MAX_RETRIES):
            try:
                timeout_for_attempt = None
                if timeout_budget_s is not None:
                    elapsed = time.monotonic() - start
                    remaining = timeout_budget_s - elapsed
                    if remaining <= 0:
                        raise asyncio.TimeoutError(
                            f"Timed out after {timeout_budget_s:.1f}s waiting for model {model_name}"
                        )
                    timeout_for_attempt = remaining

                call = asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=gen_config,
                )
                if timeout_for_attempt is None:
                    response = await call
                else:
                    response = await asyncio.wait_for(call, timeout=timeout_for_attempt)
                return response
            except asyncio.TimeoutError:
                raise
            except Exception as e:
                retryable = _is_retryable_gemini_error(e)
                if attempt == MAX_RETRIES - 1 or not retryable:
                    raise

                delay = BASE_DELAY * (2**attempt)
                if timeout_budget_s is not None:
                    elapsed = time.monotonic() - start
                    remaining = timeout_budget_s - elapsed
                    if remaining <= 0:
                        raise asyncio.TimeoutError(
                            f"Timed out after {timeout_budget_s:.1f}s waiting for model {model_name}"
                        )
                    delay = min(delay, remaining)

                logger.warning(
                    "Gemini generation attempt %d for '%s' failed: %s. Retrying in %.1fs",
                    attempt + 1,
                    model_name,
                    e,
                    delay,
                )
                # Record retry event on current span
                from opentelemetry import trace as _trace
                current_span = _trace.get_current_span()
                if current_span.is_recording():
                    current_span.add_event("retry", {
                        "attempt": attempt + 1,
                        "error": str(e),
                        "delay_s": delay,
                        "model": model_name,
                    })
                await asyncio.sleep(delay)

        raise RuntimeError("Gemini generation failed after all retries")

    async def start_session(
        self,
        config: GenerationConfig | None = None,
    ) -> GeminiSession:
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                image_size="1K",
            ),
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

        usage_entry = build_usage_entry(
            _extract_gemini_metadata(
                response,
                self._model,
                endpoint="models.generate_content",
                image_size="vision",
                reference_count=1,
            ),
            provider="gemini",
            model=self._model,
        )

        try:
            payload = json.loads(response.text)
            if isinstance(payload, dict):
                payload["_usage"] = usage_entry
            return payload
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse Gemini evaluation response as JSON")
            return {
                "error": "Failed to parse response",
                "raw": str(response.text),
                "_usage": usage_entry,
            }

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


def _is_retryable_gemini_error(error: Exception) -> bool:
    """Best-effort check for retryable Gemini backend failures."""
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and status_code in RETRY_STATUS_CODES:
        return True

    code = getattr(error, "code", None)
    if isinstance(code, int) and code in RETRY_STATUS_CODES:
        return True

    message = str(error).lower()
    for token in (" 429", " 500", " 503", "resource_exhausted", "internal", "unavailable", "capacity"):
        if token in message:
            return True
    return False


def _extract_gemini_metadata(
    response,
    model_used: str,
    *,
    endpoint: str,
    image_size: str,
    reference_count: int,
) -> dict:
    """Extract best-effort usage metadata from Gemini response objects."""
    usage = getattr(response, "usage_metadata", None)
    usage_dict: dict[str, int] = {}
    if usage is not None:
        for key in (
            "prompt_token_count",
            "candidates_token_count",
            "total_token_count",
            "cached_content_token_count",
            "thoughts_token_count",
        ):
            value = getattr(usage, key, None)
            if isinstance(value, int):
                usage_dict[key] = value
        # Also capture any additional image-related token fields
        for key in dir(usage):
            if "token" in key.lower() and not key.startswith("_"):
                value = getattr(usage, key, None)
                if isinstance(value, int) and key not in usage_dict:
                    usage_dict[key] = value

    # If Gemini returns zero tokens (common for pure image generation),
    # estimate based on prompt length and image output
    if usage_dict.get("total_token_count", 0) == 0 and usage_dict.get("prompt_token_count", 0) == 0:
        logger.debug(
            "Gemini returned zero token counts for model %s — "
            "image generation models may not report token usage",
            model_used,
        )

    metadata = {
        "provider": "gemini",
        "model": model_used,
        "endpoint": endpoint,
        "image_size": image_size,
        "reference_count": reference_count,
        "usage": usage_dict,
        "raw_usage": usage_dict,
    }
    metadata["normalized_usage"] = normalize_usage_metadata(metadata, provider="gemini")
    metadata["cost_inputs"] = {
        "provider": "gemini",
        "model": model_used,
        **metadata["normalized_usage"],
    }

    return metadata
