"""Asset Settings API Endpoints

Endpoints for managing asset configuration including depreciation defaults
and alert thresholds.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require
from app.models.asset_settings import AssetSettings

router = APIRouter(prefix="/assets/settings", tags=["asset-settings"])


# =============================================================================
# SCHEMAS
# =============================================================================

class AssetSettingsResponse(BaseModel):
    id: int
    company: Optional[str] = None

    # Depreciation
    default_depreciation_method: str
    default_finance_book: Optional[str] = None
    depreciation_posting_date: str
    auto_post_depreciation: bool

    # CWIP
    enable_cwip_by_default: bool

    # Alerts
    maintenance_alert_days: int
    warranty_alert_days: int
    insurance_alert_days: int

    model_config = ConfigDict(from_attributes=True)


class AssetSettingsUpdate(BaseModel):
    default_depreciation_method: Optional[str] = Field(None, max_length=50)
    default_finance_book: Optional[str] = Field(None, max_length=255)
    depreciation_posting_date: Optional[str] = Field(None, max_length=50)
    auto_post_depreciation: Optional[bool] = None
    enable_cwip_by_default: Optional[bool] = None
    maintenance_alert_days: Optional[int] = Field(None, ge=1, le=365)
    warranty_alert_days: Optional[int] = Field(None, ge=1, le=365)
    insurance_alert_days: Optional[int] = Field(None, ge=1, le=365)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=AssetSettingsResponse, dependencies=[Depends(Require("admin:read"))])
def get_asset_settings(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> AssetSettings:
    """Get asset settings, creating defaults if not found."""
    settings = db.query(AssetSettings).filter(
        AssetSettings.company == company
    ).first()

    if not settings:
        # Create default settings
        settings = AssetSettings(
            company=company,
            default_depreciation_method="straight_line",
            depreciation_posting_date="last_day",
            auto_post_depreciation=False,
            enable_cwip_by_default=False,
            maintenance_alert_days=7,
            warranty_alert_days=30,
            insurance_alert_days=30,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.patch("", response_model=AssetSettingsResponse, dependencies=[Depends(Require("admin:write"))])
def update_asset_settings(
    updates: AssetSettingsUpdate,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> AssetSettings:
    """Update asset settings."""
    settings = db.query(AssetSettings).filter(
        AssetSettings.company == company
    ).first()

    if not settings:
        # Create with defaults then apply updates
        settings = AssetSettings(company=company)
        db.add(settings)

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return settings
