"""
Tariff API

Tariff/plan management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import TariffService
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

router = APIRouter()


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
