"""
OpenTelemetry tracer setup for TalentKru.ai.

Uses ConsoleSpanExporter by default (development / no external OTLP endpoint
required). In production, swap SimpleSpanProcessor + ConsoleSpanExporter for
BatchSpanProcessor + OTLPSpanExporter.

Correlation IDs are propagated through background tasks via
`correlation_id_var` from `app.observability.middleware`.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.observability.middleware import correlation_id_var

# ---------------------------------------------------------------------------
# Provider setup
# ---------------------------------------------------------------------------

_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# Register as the global provider so that trace.get_tracer() works anywhere.
trace.set_tracer_provider(_provider)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider.

    Usage::

        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my-operation") as span:
            span.set_attribute("correlation_id", correlation_id_var.get(""))
            ...
    """
    return trace.get_tracer(name)


def instrument_app(app) -> None:
    """Instrument a FastAPI application with OpenTelemetry auto-instrumentation.

    Call this once during application startup, after the app instance is
    created but before the ASGI server starts accepting connections.

    The instrumentation automatically creates a root span for every incoming
    HTTP request and propagates the active context through FastAPI's middleware
    chain.  Background tasks that read ``correlation_id_var`` will carry the
    same correlation ID, linking their spans to the originating request.

    Args:
        app: The FastAPI application instance to instrument.
    """
    FastAPIInstrumentor.instrument_app(app)
