"""
OpenTelemetry Instrumentation Module

Provides toggleable distributed tracing for:
- FastAPI request/response
- SQLAlchemy database queries
- httpx HTTP client calls

Enable via configuration:
    OTEL_ENABLED=true
    OTEL_EXPORTER_ENDPOINT=http://jaeger:4317
    OTEL_TRACE_SAMPLE_RATE=0.1  # 10% sampling
"""
from __future__ import annotations

import structlog
from typing import Optional

from app.config import settings

logger = structlog.get_logger(__name__)

_instrumented = False


def setup_otel(app=None) -> bool:
    """
    Initialize OpenTelemetry instrumentation if enabled.

    Args:
        app: Optional FastAPI app instance for FastAPI instrumentation

    Returns:
        True if OTEL was initialized, False otherwise
    """
    global _instrumented

    if not settings.otel_enabled:
        logger.info("otel_disabled", message="OTEL_ENABLED=false, skipping instrumentation")
        return False

    if _instrumented:
        logger.debug("otel_already_instrumented")
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_NAMESPACE

        # Create resource with service identity
        resource = Resource.create({
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_NAMESPACE: settings.otel_service_namespace,
            "service.instance.id": settings.platform_instance_id or "local",
            "deployment.environment": settings.environment,
        })

        # Create sampler based on configured rate
        sampler = TraceIdRatioBased(settings.otel_trace_sample_rate)

        # Create and set tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)
        trace.set_tracer_provider(provider)

        # Setup exporter if endpoint configured
        if settings.otel_exporter_endpoint:
            _setup_exporter(provider)

        # Instrument components
        _instrument_fastapi(app)
        _instrument_sqlalchemy()
        _instrument_httpx()

        _instrumented = True
        logger.info(
            "otel_initialized",
            service_name=settings.otel_service_name,
            sample_rate=settings.otel_trace_sample_rate,
            exporter_endpoint=settings.otel_exporter_endpoint,
        )
        return True

    except ImportError as e:
        logger.warning(
            "otel_import_error",
            message="OpenTelemetry packages not installed, skipping instrumentation",
            error=str(e),
        )
        return False
    except Exception as e:
        logger.error("otel_setup_error", error=str(e))
        return False


def _setup_exporter(provider) -> None:
    """Setup OTLP exporter for sending traces to collector."""
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = settings.otel_exporter_endpoint or ""
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=not endpoint.startswith("https"),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("otel_exporter_configured", endpoint=settings.otel_exporter_endpoint)
    except ImportError:
        logger.warning("otel_exporter_not_available", message="OTLP exporter not installed")
    except Exception as e:
        logger.error("otel_exporter_error", error=str(e))


def _instrument_fastapi(app) -> None:
    """Instrument FastAPI for request tracing."""
    if app is None:
        logger.debug("otel_fastapi_skipped", reason="no app provided")
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/metrics,/ready",  # Exclude health endpoints from tracing
        )
        logger.info("otel_fastapi_instrumented")
    except ImportError:
        logger.warning("otel_fastapi_not_available", message="FastAPI instrumentor not installed")
    except Exception as e:
        logger.error("otel_fastapi_error", error=str(e))


def _instrument_sqlalchemy() -> None:
    """Instrument SQLAlchemy for database query tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(
            enable_commenter=True,  # Add trace context to SQL comments
            commenter_options={
                "db_driver": True,
                "db_framework": False,  # Reduce noise
                "opentelemetry_values": True,
            },
        )
        logger.info("otel_sqlalchemy_instrumented")
    except ImportError:
        logger.warning("otel_sqlalchemy_not_available", message="SQLAlchemy instrumentor not installed")
    except Exception as e:
        logger.error("otel_sqlalchemy_error", error=str(e))


def _instrument_httpx() -> None:
    """Instrument httpx for outbound HTTP call tracing."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation

        HTTPXClientInstrumentation().instrument()
        logger.info("otel_httpx_instrumented")
    except ImportError:
        logger.warning("otel_httpx_not_available", message="httpx instrumentor not installed")
    except Exception as e:
        logger.error("otel_httpx_error", error=str(e))


def get_tracer(name: str = "dotmac-insights"):
    """
    Get a tracer for manual span creation.

    Usage:
        from app.observability.otel import get_tracer
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span("my_operation") as span:
            span.set_attribute("key", "value")
            # do work
    """
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        # Return a no-op tracer if OTEL not installed
        return _NoOpTracer()


class _NoOpTracer:
    """No-op tracer for when OTEL is not available."""

    def start_as_current_span(self, name, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key, value):
        pass

    def add_event(self, name, attributes=None):
        pass

    def set_status(self, status):
        pass


def shutdown_otel() -> None:
    """Gracefully shutdown OTEL instrumentation."""
    global _instrumented
    if not _instrumented:
        return

    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, 'shutdown'):
            provider.shutdown()
        _instrumented = False
        logger.info("otel_shutdown_complete")
    except Exception as e:
        logger.error("otel_shutdown_error", error=str(e))
