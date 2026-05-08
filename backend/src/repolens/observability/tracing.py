"""OpenTelemetry tracing setup and LangSmith configuration.

Call ``setup_tracing()`` once at app startup. When OTEL is enabled,
FastAPI requests and outbound HTTP calls are automatically instrumented.
LangSmith tracing is activated by setting LANGSMITH_API_KEY.
"""

import os

import structlog

from repolens.config import get_settings

log = structlog.get_logger(__name__)


def setup_tracing() -> None:
    """Initialize OpenTelemetry and LangSmith tracing if configured."""
    settings = get_settings()

    # LangSmith — set env vars so langchain/langgraph auto-trace
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        log.info("tracing.langsmith_enabled", project=settings.langsmith_project)

    if not settings.otel_enabled:
        log.info("tracing.otel_disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        log.info(
            "tracing.otel_enabled",
            service=settings.otel_service_name,
            endpoint=settings.otel_exporter_endpoint,
        )
    except ImportError:
        log.warning("tracing.otel_import_error", detail="opentelemetry packages not available")


def instrument_fastapi(app: object) -> None:
    """Attach OpenTelemetry instrumentation to a FastAPI app."""
    settings = get_settings()
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
        log.info("tracing.fastapi_instrumented")
    except ImportError:
        log.warning("tracing.fastapi_instrument_failed")
