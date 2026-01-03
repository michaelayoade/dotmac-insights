"""
Middleware module for DotMAC Insights.
"""

from app.middleware.metrics import (
    WEBHOOK_AUTH_FAILURES,
    CONTACTS_AUTH_FAILURES,
    OUTBOUND_SYNC_TOTAL,
    CONTACTS_DRIFT_PCT,
    CONTACTS_QUERY_LATENCY,
    increment_webhook_auth_failure,
    increment_contacts_auth_failure,
    record_outbound_sync,
    set_contacts_drift,
    observe_contacts_query_latency,
)

__all__ = [
    "WEBHOOK_AUTH_FAILURES",
    "CONTACTS_AUTH_FAILURES",
    "OUTBOUND_SYNC_TOTAL",
    "CONTACTS_DRIFT_PCT",
    "CONTACTS_QUERY_LATENCY",
    "increment_webhook_auth_failure",
    "increment_contacts_auth_failure",
    "record_outbound_sync",
    "set_contacts_drift",
    "observe_contacts_query_latency",
]
