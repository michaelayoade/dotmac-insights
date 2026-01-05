"""
Tariff API

Tariff/plan management endpoints.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import TariffService
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ConflictError

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class TariffCreateSchema(BaseModel):
    """Schema for creating a tariff."""

    title: str = Field(..., min_length=1, max_length=255, description="Tariff title")
    tariff_type: str = Field(
        "internet",
        pattern="^(internet|recurring|one_time)$",
        description="Type of tariff"
    )
    price: Decimal = Field(..., ge=0, description="Price amount")
    currency: str = Field("NGN", max_length=10, description="Currency code")
    service_name: Optional[str] = Field(None, max_length=255, description="Service name")
    description: Optional[str] = Field(None, description="Tariff description")
    speed_download: Optional[int] = Field(None, ge=0, description="Download speed in Mbps")
    speed_upload: Optional[int] = Field(None, ge=0, description="Upload speed in Mbps")
    vat_percent: Decimal = Field(Decimal("0"), ge=0, le=100, description="VAT percentage")
    with_vat: bool = Field(True, description="Whether price includes VAT")
    available_for_services: bool = Field(True, description="Available for new subscriptions")
    show_on_customer_portal: bool = Field(False, description="Show on customer portal")
    enabled: bool = Field(True, description="Whether tariff is enabled")


class TariffUpdateSchema(BaseModel):
    """Schema for updating a tariff."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    service_name: Optional[str] = None
    description: Optional[str] = None
    speed_download: Optional[int] = Field(None, ge=0)
    speed_upload: Optional[int] = Field(None, ge=0)
    vat_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    with_vat: Optional[bool] = None
    available_for_services: Optional[bool] = None
    show_on_customer_portal: Optional[bool] = None
    enabled: Optional[bool] = None


# =============================================================================
# READ ENDPOINTS
# =============================================================================


@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def list_tariffs(
    tariff_type: Optional[str] = Query(None, description="Filter by tariff type"),
    enabled_only: bool = Query(True, description="Only show enabled tariffs"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List tariffs/plans.
    """
    service = TariffService(db, principal)

    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = service.list_tariffs(
        tariff_type=tariff_type,
        enabled_only=enabled_only,
        pagination=pagination,
    )

    return {
        "items": [_serialize_tariff(t) for t in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{tariff_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get tariff details.
    """
    service = TariffService(db, principal)

    try:
        tariff = service.get_tariff(tariff_id)
        subscriber_count = service.get_subscription_count(tariff_id)

        data = _serialize_tariff(tariff)
        data["subscriber_count"] = subscriber_count
        return data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{tariff_id}/subscribers", dependencies=[Depends(Require("subscriptions:read"))])
async def get_tariff_subscribers(
    tariff_id: int = Path(..., description="Tariff ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscribers for a tariff.
    """
    from app.services.subscriptions import SubscriptionService, SubscriptionFilters

    sub_service = SubscriptionService(db, principal)

    result = sub_service.list_subscriptions(
        filters=SubscriptionFilters(tariff_id=tariff_id),
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "tariff_id": tariff_id,
        "items": [
            {
                "id": s.id,
                "party_id": s.party_id,
                "plan_name": s.plan_name,
                "status": s.status.value if s.status else None,
                "price": float(s.price) if s.price else 0,
            }
            for s in result.items
        ],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{tariff_id}/stats", dependencies=[Depends(Require("subscriptions:read"))])
async def get_tariff_stats(
    tariff_id: int = Path(..., description="Tariff ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get statistics for a tariff.
    """
    service = TariffService(db, principal)

    try:
        stats = service.get_tariff_stats(tariff_id)
        return stats
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.post("", dependencies=[Depends(Require("subscriptions:create"))])
async def create_tariff(
    data: TariffCreateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Create a new tariff/plan.
    """
    from app.models.tariff import Tariff, TariffType

    # Generate a unique splynx_id for locally created tariffs (negative to avoid conflicts)
    from sqlalchemy import func
    max_id = db.query(func.max(Tariff.id)).scalar() or 0
    local_splynx_id = -(max_id + 1)

    tariff = Tariff(
        splynx_id=local_splynx_id,
        title=data.title,
        tariff_type=TariffType(data.tariff_type.upper()),
        price=data.price,
        currency=data.currency,
        service_name=data.service_name,
        description=data.description,
        speed_download=data.speed_download,
        speed_upload=data.speed_upload,
        vat_percent=data.vat_percent,
        with_vat=data.with_vat,
        available_for_services=data.available_for_services,
        show_on_customer_portal=data.show_on_customer_portal,
        enabled=data.enabled,
    )

    db.add(tariff)
    db.commit()
    db.refresh(tariff)

    return _serialize_tariff(tariff)


@router.patch("/{tariff_id}", dependencies=[Depends(Require("subscriptions:update"))])
async def update_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    data: TariffUpdateSchema = ...,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Update a tariff.
    """
    service = TariffService(db, principal)

    try:
        tariff = service.get_tariff(tariff_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Update fields if provided
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tariff, key, value)

    db.commit()
    db.refresh(tariff)

    return _serialize_tariff(tariff)


@router.delete("/{tariff_id}", dependencies=[Depends(Require("subscriptions:delete"))])
async def delete_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Soft delete a tariff (disable it).

    Tariffs with active subscriptions cannot be deleted.
    """
    service = TariffService(db, principal)

    try:
        tariff = service.get_tariff(tariff_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Check for active subscriptions
    active_count = service.get_subscription_count(tariff_id)
    if active_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete tariff with {active_count} active subscriptions"
        )

    tariff.enabled = False
    tariff.available_for_services = False
    db.commit()

    return {"message": "Tariff disabled", "id": tariff_id}


@router.post("/{tariff_id}/toggle", dependencies=[Depends(Require("subscriptions:update"))])
async def toggle_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Toggle tariff enabled/disabled status.
    """
    service = TariffService(db, principal)

    try:
        tariff = service.get_tariff(tariff_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    tariff.enabled = not tariff.enabled
    db.commit()

    status = "enabled" if tariff.enabled else "disabled"
    return {
        "message": f"Tariff {status}",
        "id": tariff_id,
        "enabled": tariff.enabled,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _serialize_tariff(tariff) -> Dict[str, Any]:
    """Serialize tariff to dict."""
    return {
        "id": tariff.id,
        "title": tariff.title,
        "tariff_type": tariff.tariff_type,
        "price": float(tariff.price) if tariff.price else 0,
        "currency": tariff.currency,
        "billing_cycle": tariff.billing_cycle,
        "download_speed": tariff.download_speed,
        "upload_speed": tariff.upload_speed,
        "data_cap": tariff.data_cap,
        "enabled": tariff.enabled,
        "created_at": tariff.created_at.isoformat() if tariff.created_at else None,
    }
