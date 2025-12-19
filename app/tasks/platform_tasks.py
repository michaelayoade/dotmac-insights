"""
Celery tasks for platform integration.
"""
import logging
from app.worker import celery_app
from app.database import SessionLocal
from app.services.platform_integration import (
    validate_license,
    refresh_feature_flags_from_platform,
    report_usage,
    send_heartbeat,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.platform.validate_license")
def validate_license_task():
    """Validate license (best effort)."""
    ok = validate_license()
    return {"valid": ok}


@celery_app.task(name="app.tasks.platform.refresh_feature_flags")
def refresh_feature_flags_task():
    """Refresh feature flags from platform."""
    refresh_feature_flags_from_platform()
    return {"status": "ok"}


@celery_app.task(name="app.tasks.platform.report_usage")
def report_usage_task():
    """Report usage metrics to platform."""
    db = SessionLocal()
    try:
        report_usage(db)
        return {"status": "ok"}
    finally:
        db.close()


@celery_app.task(name="app.tasks.platform.send_heartbeat")
def send_heartbeat_task():
    """Send heartbeat/health snapshot to platform."""
    db = SessionLocal()
    try:
        send_heartbeat(db)
        return {"status": "ok"}
    finally:
        db.close()
