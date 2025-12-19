"""
Prometheus Metrics Module

Defines and manages Prometheus metrics for monitoring:
- Authentication failures (webhooks, contacts API)
- Contacts drift percentage (for sync monitoring)
- Outbound sync success/failure rates
- Contacts query latency

Usage:
    from app.middleware.metrics import increment_webhook_auth_failure

    # In webhook handler
    increment_webhook_auth_failure("paystack", "invalid_signature")

    # In auth middleware
    increment_contacts_auth_failure("403")

Metrics are exposed at /metrics endpoint when configured.
"""

import logging
from contextlib import contextmanager
from time import time
from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Auth failure counters
    WEBHOOK_AUTH_FAILURES = Counter(
        'webhook_auth_failures_total',
        'Webhook authentication failures',
        ['provider', 'error_type']  # error_type: invalid_signature, missing_signature
    )

    CONTACTS_AUTH_FAILURES = Counter(
        'contacts_auth_failures_total',
        'Contacts API authentication/authorization failures',
        ['error_type']  # error_type: 401, 403
    )

    # Dual-write metrics (legacy sync) - Contacts
    CONTACTS_DUAL_WRITE_SUCCESS = Counter(
        'contacts_dual_write_success_total',
        'Successful dual-write operations to legacy Customer',
        ['operation']  # operation: create, update, delete, status_change
    )
    CONTACTS_DUAL_WRITE_FAILURES = Counter(
        'contacts_dual_write_failures_total',
        'Failed dual-write operations to legacy Customer',
        ['operation']  # operation: create, update, delete, status_change
    )

    # Dual-write metrics (legacy sync) - Tickets
    TICKETS_DUAL_WRITE_SUCCESS = Counter(
        'tickets_dual_write_success_total',
        'Successful dual-write operations to legacy Ticket',
        ['operation']  # operation: create, update, sync_from_legacy
    )
    TICKETS_DUAL_WRITE_FAILURES = Counter(
        'tickets_dual_write_failures_total',
        'Failed dual-write operations to legacy Ticket',
    )

    # Outbound sync metrics
    OUTBOUND_SYNC_TOTAL = Counter(
        'outbound_sync_total',
        'Outbound sync attempts',
        ['entity_type', 'target', 'status']  # status: success, failure
    )

    # Contacts drift gauge (set by reconciliation job)
    CONTACTS_DRIFT_PCT = Gauge(
        'contacts_drift_pct',
        'Percentage of contacts with field mismatches',
        ['system']  # system: splynx, erpnext
    )

    # Tickets drift gauge (set by reconciliation job)
    TICKETS_DRIFT_PCT = Gauge(
        'tickets_drift_pct',
        'Percentage of tickets with field mismatches',
        ['system']  # system: splynx, erpnext, chatwoot, ticket_legacy
    )

    # Contacts query latency histogram
    CONTACTS_QUERY_LATENCY = Histogram(
        'contacts_query_latency_seconds',
        'Contacts API query latency',
        ['endpoint'],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    # General API metrics
    API_REQUEST_LATENCY = Histogram(
        'api_request_latency_seconds',
        'API request latency',
        ['method', 'endpoint', 'status_code'],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    API_REQUESTS_TOTAL = Counter(
        'api_requests_total',
        'Total API requests',
        ['method', 'endpoint', 'status_code']
    )

else:
    # Stub implementations when prometheus_client is not available
    class StubCounter:
        def labels(self, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def get(self):
            return 0
        def get(self):
            return 0

    class StubGauge:
        def labels(self, **kwargs):
            return self
        def set(self, value):
            pass

    class StubHistogram:
        def labels(self, **kwargs):
            return self
        def observe(self, value):
            pass

    WEBHOOK_AUTH_FAILURES = StubCounter()
    CONTACTS_AUTH_FAILURES = StubCounter()
    CONTACTS_DUAL_WRITE_SUCCESS = StubCounter()
    CONTACTS_DUAL_WRITE_FAILURES = StubCounter()
    TICKETS_DUAL_WRITE_SUCCESS = StubCounter()
    TICKETS_DUAL_WRITE_FAILURES = StubCounter()
    OUTBOUND_SYNC_TOTAL = StubCounter()
    CONTACTS_DRIFT_PCT = StubGauge()
    TICKETS_DRIFT_PCT = StubGauge()
    CONTACTS_QUERY_LATENCY = StubHistogram()
    API_REQUEST_LATENCY = StubHistogram()
    API_REQUESTS_TOTAL = StubCounter()

    logger.warning("prometheus_client not installed - metrics are disabled")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def increment_webhook_auth_failure(provider: str, error_type: str) -> None:
    """
    Increment webhook auth failure counter.

    Args:
        provider: Payment provider (paystack, flutterwave, omni, etc.)
        error_type: Type of error (invalid_signature, missing_signature, no_secret)
    """
    try:
        WEBHOOK_AUTH_FAILURES.labels(provider=provider, error_type=error_type).inc()
        logger.debug("webhook_auth_failure_recorded", provider=provider, error_type=error_type)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="webhook_auth_failures", error=str(e))


def increment_contacts_auth_failure(error_type: str) -> None:
    """
    Increment contacts API auth failure counter.

    Args:
        error_type: HTTP status code as string (401, 403)
    """
    try:
        CONTACTS_AUTH_FAILURES.labels(error_type=error_type).inc()
        logger.debug("contacts_auth_failure_recorded", error_type=error_type)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="contacts_auth_failures", error=str(e))


def record_outbound_sync(entity_type: str, target: str, success: bool) -> None:
    """
    Record outbound sync attempt.

    Args:
        entity_type: Type of entity being synced (unified_contact, ticket, etc.)
        target: Target system (splynx, erpnext, chatwoot)
        success: Whether the sync was successful
    """
    try:
        status = "success" if success else "failure"
        OUTBOUND_SYNC_TOTAL.labels(entity_type=entity_type, target=target, status=status).inc()
    except Exception as e:
        logger.error("failed_to_record_metric", metric="outbound_sync_total", error=str(e))


def record_dual_write(operation: str, success: bool) -> None:
    """
    Record dual-write outcomes to legacy Customer.

    Args:
        operation: Operation type (create, update, delete, status_change)
        success: Whether the dual-write succeeded
    """
    try:
        if success:
            CONTACTS_DUAL_WRITE_SUCCESS.labels(operation=operation).inc()
        else:
            CONTACTS_DUAL_WRITE_FAILURES.labels(operation=operation).inc()
    except Exception as e:
        logger.error("failed_to_record_metric", metric="contacts_dual_write", error=str(e))


def record_ticket_dual_write(operation: str, success: bool) -> None:
    """
    Record dual-write outcomes to legacy Ticket.

    Args:
        operation: Operation type (create, update, sync_from_legacy)
        success: Whether the dual-write succeeded
    """
    try:
        if success:
            TICKETS_DUAL_WRITE_SUCCESS.labels(operation=operation).inc()
        else:
            TICKETS_DUAL_WRITE_FAILURES.inc()
    except Exception as e:
        logger.error("failed_to_record_metric", metric="tickets_dual_write", error=str(e))


def set_contacts_drift(system: str, drift_pct: float) -> None:
    """
    Set contacts drift percentage for a system.

    Args:
        system: External system (splynx, erpnext)
        drift_pct: Percentage of contacts with mismatched fields (0-100)
    """
    try:
        CONTACTS_DRIFT_PCT.labels(system=system).set(drift_pct)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="contacts_drift_pct", error=str(e))


def set_tickets_drift(system: str, drift_pct: float) -> None:
    """
    Set tickets drift percentage for a system.

    Args:
        system: External system (splynx, erpnext, chatwoot, ticket_legacy)
        drift_pct: Percentage of tickets with mismatched fields (0-100)
    """
    try:
        TICKETS_DRIFT_PCT.labels(system=system).set(drift_pct)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="tickets_drift_pct", error=str(e))


def observe_contacts_query_latency(endpoint: str, latency_seconds: float) -> None:
    """
    Record contacts query latency.

    Args:
        endpoint: API endpoint path
        latency_seconds: Query latency in seconds
    """
    try:
        CONTACTS_QUERY_LATENCY.labels(endpoint=endpoint).observe(latency_seconds)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="contacts_query_latency", error=str(e))


@contextmanager
def measure_latency(endpoint: str):
    """
    Context manager to measure and record latency for contacts endpoints.

    Usage:
        with measure_latency("/api/contacts"):
            # perform query
            pass
    """
    start = time()
    try:
        yield
    finally:
        latency = time() - start
        observe_contacts_query_latency(endpoint, latency)


def record_api_request(method: str, endpoint: str, status_code: int, latency_seconds: float) -> None:
    """
    Record general API request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        status_code: HTTP response status code
        latency_seconds: Request latency in seconds
    """
    try:
        API_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
        API_REQUEST_LATENCY.labels(method=method, endpoint=endpoint, status_code=str(status_code)).observe(latency_seconds)
    except Exception as e:
        logger.error("failed_to_record_metric", metric="api_request", error=str(e))


# =============================================================================
# METRICS ENDPOINT HELPERS
# =============================================================================


def get_metrics_response() -> tuple[bytes, str]:
    """
    Get Prometheus metrics response for /metrics endpoint.

    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    if PROMETHEUS_AVAILABLE:
        return generate_latest(), CONTENT_TYPE_LATEST
    else:
        return b"# prometheus_client not installed\n", "text/plain; charset=utf-8"
