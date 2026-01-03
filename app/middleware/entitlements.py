"""
Entitlement gating dependencies.

Maps platform-managed entitlements to local feature flags.
"""
from fastapi import HTTPException

from app.feature_flags import feature_flags


def require_entitlement(entitlement: str):
    """FastAPI dependency to check entitlement before route execution."""
    flag_name = f"{entitlement.upper().replace('-', '_')}_ENABLED"

    async def _check():
        if not getattr(feature_flags, flag_name, False):
            raise HTTPException(
                status_code=403,
                detail=f"Required entitlement: {entitlement}. Contact support to upgrade.",
            )

    return _check


def require_nigeria_compliance():
    """Gate all Nigeria compliance endpoints."""
    return require_entitlement("NIGERIA_COMPLIANCE")

