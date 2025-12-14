"""
Tax Settings Endpoints

Company-level Nigerian tax configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    TaxSettingsCreate,
    TaxSettingsUpdate,
    TaxSettingsResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=TaxSettingsResponse)
def get_tax_settings(
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get tax settings for a company.

    Returns company-level tax configuration including:
    - TIN and VAT registration
    - Jurisdiction preferences (Federal/State)
    - Company size classification
    - VAT and WHT settings
    - E-invoicing configuration
    - PAYE filing frequency
    """
    service = NigerianTaxService(db)
    settings = service.get_settings(company)

    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found for this company"
        )

    return TaxSettingsResponse.model_validate(settings)


@router.post("", response_model=TaxSettingsResponse)
def create_tax_settings(
    data: TaxSettingsCreate,
    db: Session = Depends(get_db),
    company: str = Depends(get_single_company),
    _: None = Depends(require_tax_write()),
):
    """
    Create tax settings for a company.

    Required for Nigerian tax compliance:
    - TIN: Tax Identification Number (Federal)
    - VAT registration number
    - State TIN (for PAYE)
    - Company size classification (affects CIT rate)
    """
    service = NigerianTaxService(db)

    # Check if settings already exist
    existing = service.get_settings(company)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Tax settings already exist for this company. Use PATCH to update."
        )

    payload = data.model_dump()
    payload["company"] = company
    settings = service.create_settings(payload)
    return TaxSettingsResponse.model_validate(settings)


@router.patch("", response_model=TaxSettingsResponse)
def update_tax_settings(
    data: TaxSettingsUpdate,
    db: Session = Depends(get_db),
    company: str = Depends(get_single_company),
    _: None = Depends(require_tax_write()),
):
    """
    Update tax settings for a company.

    All fields are optional - only provided fields will be updated.
    """
    service = NigerianTaxService(db)

    # Only include non-None values
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No update data provided"
        )

    settings = service.update_settings(company, update_data)

    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Tax settings not found for this company"
        )

    return TaxSettingsResponse.model_validate(settings)
