"""
Usage API

Bandwidth and data usage tracking endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import UsageService, UsageFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

router = APIRouter()


@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def list_usage(
    subscription_id: Optional[int] = Query(None, description="Filter by subscription"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List usage records.
    """
    service = UsageService(db, principal)

    filters = UsageFilters(
        subscription_id=subscription_id,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
    )

    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = service.list_usage(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_usage(u) for u in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{subscription_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription_usage(
    subscription_id: int = Path(..., description="Subscription ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get usage records for a subscription.
    """
    service = UsageService(db, principal)

    result = service.list_usage(
        filters=UsageFilters(
            subscription_id=subscription_id,
            date_from=date_from,
            date_to=date_to,
        ),
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "subscription_id": subscription_id,
        "items": [_serialize_usage(u) for u in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{subscription_id}/summary", dependencies=[Depends(Require("subscriptions:read"))])
async def get_usage_summary(
    subscription_id: int = Path(..., description="Subscription ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get usage summary for a subscription.
    """
    service = UsageService(db, principal)

    try:
        summary = service.get_usage_summary(
            subscription_id=subscription_id,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "subscription_id": summary.subscription_id,
            "period_start": str(summary.period_start),
            "period_end": str(summary.period_end),
            "total_upload_gb": summary.total_upload_gb,
            "total_download_gb": summary.total_download_gb,
            "total_gb": summary.total_gb,
            "daily_average_gb": summary.daily_average_gb,
            "peak_day": str(summary.peak_day) if summary.peak_day else None,
            "peak_day_gb": summary.peak_day_gb,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{subscription_id}/data-cap", dependencies=[Depends(Require("subscriptions:read"))])
async def get_data_cap_status(
    subscription_id: int = Path(..., description="Subscription ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get data cap status for a subscription.
    """
    service = UsageService(db, principal)

    try:
        status = service.get_data_cap_status(subscription_id)
        return {
            "subscription_id": status.subscription_id,
            "data_cap_gb": status.data_cap_gb,
            "used_gb": status.used_gb,
            "remaining_gb": status.remaining_gb,
            "usage_percent": status.usage_percent,
            "is_exceeded": status.is_exceeded,
            "billing_cycle_start": str(status.billing_cycle_start),
            "billing_cycle_end": str(status.billing_cycle_end),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _serialize_usage(usage) -> Dict[str, Any]:
    """Serialize usage record."""
    return {
        "id": usage.id,
        "subscription_id": usage.subscription_id,
        "usage_date": str(usage.usage_date),
        "upload_bytes": usage.upload_bytes,
        "download_bytes": usage.download_bytes,
        "total_bytes": usage.upload_bytes + usage.download_bytes,
        "upload_gb": round(usage.upload_bytes / (1024**3), 3),
        "download_gb": round(usage.download_bytes / (1024**3), 3),
    }
