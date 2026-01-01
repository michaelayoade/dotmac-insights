"""
Celery tasks for platform integration.

Uses async platform client via asyncio.run() for non-blocking platform calls.
"""
import asyncio
import logging
from app.worker import celery_app
from app.database import SessionLocal
from app.services.platform_integration import (
    validate_license_async,
    refresh_feature_flags_from_platform_async,
    report_usage_async,
    send_heartbeat_async,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.platform.validate_license")
def validate_license_task():
    """Validate license using async platform client."""
    ok = asyncio.run(validate_license_async())
    return {"valid": ok}


@celery_app.task(name="app.tasks.platform.refresh_feature_flags")
def refresh_feature_flags_task():
    """Refresh feature flags from platform using async client."""
    asyncio.run(refresh_feature_flags_from_platform_async())
    return {"status": "ok"}


@celery_app.task(name="app.tasks.platform.report_usage")
def report_usage_task():
    """Report usage metrics to platform using async client."""
    db = SessionLocal()
    try:
        asyncio.run(report_usage_async(db))
        return {"status": "ok"}
    finally:
        db.close()


@celery_app.task(name="app.tasks.platform.send_heartbeat")
def send_heartbeat_task():
    """Send heartbeat/health snapshot to platform using async client."""
    db = SessionLocal()
    try:
        asyncio.run(send_heartbeat_async(db))
        return {"status": "ok"}
    finally:
        db.close()
