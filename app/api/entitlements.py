"""Entitlements API for frontend gating."""
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_principal
from app.feature_flags import feature_flags
from app.services.platform_integration import get_license_status

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


class EntitlementsResponse(BaseModel):
    license_status: str
    in_grace_period: bool
    entitlements: Optional[dict]
    feature_flags: Dict[str, bool]


@router.get("", response_model=EntitlementsResponse)
def get_entitlements(_: object = Depends(get_current_principal)) -> EntitlementsResponse:
    """Return current entitlements and feature flags for UI gating."""
    license_status = get_license_status()
    flags = {
        name: getattr(feature_flags, name)
        for name in dir(feature_flags)
        if name.isupper() and isinstance(getattr(feature_flags, name), bool)
    }

    return EntitlementsResponse(
        license_status=license_status["status"],
        in_grace_period=license_status.get("in_grace_period", False),
        entitlements=license_status.get("entitlements"),
        feature_flags=flags,
    )

