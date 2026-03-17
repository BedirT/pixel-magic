"""OpenTelemetry tracing setup for Phoenix Arize."""

from __future__ import annotations

import base64
import io
import json
import logging
import os

from PIL import Image

logger = logging.getLogger(__name__)

_initialized = False


def init_tracing() -> None:
    """Initialize OTel tracing with Phoenix. No-op if endpoint not set."""
    global _initialized
    if _initialized:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": "pixel-magic"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrument OpenAI SDK (covers agents SDK calls)
        from openinference.instrumentation.openai import OpenAIInstrumentor

        OpenAIInstrumentor().instrument()

        # Auto-instrument Google GenAI SDK (covers Gemini image generation)
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

        GoogleGenAIInstrumentor().instrument()

        _initialized = True
        logger.info("Tracing initialized — exporting to %s", endpoint)
    except Exception:
        logger.exception("Failed to initialize tracing")


def get_tracer(name: str):
    """Get a named tracer. Returns a no-op tracer if tracing is not initialized."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def _image_to_data_url(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    payload = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{payload}"


def attach_multimodal_input(
    span,
    *,
    prompt: str,
    reference_images: list[Image.Image] | None = None,
) -> None:
    """Attach prompt text and optional reference images to a trace span."""
    try:
        payload: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        for image in reference_images or []:
            payload.append({
                "type": "image",
                "image": {"url": _image_to_data_url(image)},
            })
        span.set_attribute("input.value", json.dumps(payload))
        span.set_attribute("input.mime_type", "application/json")
        span.set_attribute("llm.reference_count", len(reference_images or []))
    except Exception:
        logger.debug("Failed to attach multimodal input to span", exc_info=True)


def attach_output_image(span, image: Image.Image) -> None:
    """Attach an output image to a trace span for Phoenix multimodal rendering."""
    try:
        payload = json.dumps([{
            "type": "image",
            "image": {"url": _image_to_data_url(image)},
        }])
        span.set_attribute("output.value", payload)
        span.set_attribute("output.mime_type", "application/json")
    except Exception:
        logger.debug("Failed to attach output image to span", exc_info=True)
