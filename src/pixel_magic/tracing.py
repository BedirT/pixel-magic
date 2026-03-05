"""OpenTelemetry tracing setup for Phoenix Arize."""

from __future__ import annotations

import logging
import os

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

        _initialized = True
        logger.info("Tracing initialized — exporting to %s", endpoint)
    except Exception:
        logger.exception("Failed to initialize tracing")


def get_tracer(name: str):
    """Get a named tracer. Returns a no-op tracer if tracing is not initialized."""
    from opentelemetry import trace

    return trace.get_tracer(name)
