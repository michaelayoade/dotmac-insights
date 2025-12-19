"""
License enforcement middleware/dep.

Gates API requests based on platform license status. Fail-open is honored for
GRACE_PERIOD if configured; EXPIRED/INVALID returns 503.
"""
from fastapi import HTTPException, Request
from app.services.platform_integration import validate_license, get_license_status, LicenseStatus
from app.config import settings


async def enforce_license(request: Request):
    """
    FastAPI dependency to enforce license validity.

    Returns:
        None if license is valid/within grace; raises HTTPException otherwise.
    """
    # If platform integration is not configured, allow by default
    if not settings.platform_api_url or not settings.platform_instance_id:
        return

    # Check cache + platform (best effort)
    is_valid = validate_license()
    status = get_license_status()["status"]

    if is_valid:
        return

    # Allow grace period
    if status == LicenseStatus.GRACE_PERIOD:
        return

    # Block on expired/invalid
    raise HTTPException(status_code=503, detail="License invalid or expired")
