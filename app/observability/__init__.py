"""Observability module for OTEL tracing and metrics."""
from app.observability.otel import setup_otel, shutdown_otel, get_tracer

__all__ = ["setup_otel", "shutdown_otel", "get_tracer"]
