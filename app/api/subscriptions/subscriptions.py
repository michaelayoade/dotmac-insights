"""
Subscription CRUD and Lifecycle API

Core subscription management endpoints.
"""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    SubscriptionService,
    SubscriptionFilters,
    SubscriptionCreateData,
    SubscriptionUpdateData,
    NetworkAssignmentData,
    ProvisioningConfigData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class SubscriptionCreateSchema(BaseModel):
    """Schema for creating a subscription."""

    party_id: int = Field(..., description="Party (customer) ID")
    plan_name: str = Field(..., min_length=1, max_length=255)
    price: Decimal = Field(..., ge=0)

    tariff_id: Optional[int] = None
    service_type: str = Field("internet", pattern="^(internet|voice|custom|bundle)$")
    plan_code: Optional[str] = None
    description: Optional[str] = None
    currency: str = Field("NGN", max_length=10)
    billing_cycle: str = Field("monthly", pattern="^(daily|weekly|monthly|quarterly|yearly)$")

    download_speed: Optional[int] = None
    upload_speed: Optional[int] = None
    data_cap: Optional[int] = None

    router_id: Optional[int] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None

    access_method: Optional[str] = None
    ppp_username: Optional[str] = None
    ppp_password: Optional[str] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SubscriptionUpdateSchema(BaseModel):
    """Schema for updating a subscription."""

    plan_name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan_code: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    billing_cycle: Optional[str] = None
    tariff_id: Optional[int] = None
    service_type: Optional[str] = None
    download_speed: Optional[int] = None
    upload_speed: Optional[int] = None
    data_cap: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class NetworkAssignmentSchema(BaseModel):
    """Schema for assigning network resources."""

    router_id: Optional[int] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None


class ProvisioningConfigSchema(BaseModel):
    """Schema for configuring provisioning."""

    router_id: Optional[int] = None
    access_method: Optional[str] = None
    ppp_username: Optional[str] = None
    ppp_password: Optional[str] = None


class UpgradeSchema(BaseModel):
    """Schema for upgrading subscription."""

    new_tariff_id: int = Field(..., description="Target tariff ID")
    effective: str = Field("immediate", pattern="^(immediate|next_cycle)$")
    prorate: bool = True


class DowngradeSchema(BaseModel):
    """Schema for downgrading subscription."""

    new_tariff_id: int = Field(..., description="Target tariff ID")
    effective: str = Field("next_cycle", pattern="^(immediate|next_cycle)$")
    prorate: bool = False


class RenewSchema(BaseModel):
    """Schema for renewing subscription."""

    periods: int = Field(1, ge=1, le=24, description="Number of billing periods")
    new_end_date: Optional[datetime] = None


class StatusChangeSchema(BaseModel):
    """Schema for status change."""

    reason: Optional[str] = None


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def list_subscriptions(
    search: Optional[str] = Query(None, description="Search in plan name, IP, MAC, username"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service_type: Optional[str] = Query(None, description="Filter by service type"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    router_id: Optional[int] = Query(None, description="Filter by router"),
    tariff_id: Optional[int] = Query(None, description="Filter by tariff"),
    billing_cycle: Optional[str] = Query(None, description="Filter by billing cycle"),
    has_router: Optional[bool] = Query(None, description="Filter by router assignment"),
    is_provisioned: Optional[bool] = Query(None, description="Filter by provisioning status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List subscriptions with optional filters.
    """
    service = SubscriptionService(db, principal)

    filters = SubscriptionFilters(
        search=search,
        status=status,
        service_type=service_type,
        party_id=party_id,
        router_id=router_id,
        tariff_id=tariff_id,
        billing_cycle=billing_cycle,
        has_router=has_router,
        is_provisioned=is_provisioned,
    )

    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = service.list_subscriptions(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_subscription(s) for s in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
        "pages": (result.total + per_page - 1) // per_page,
    }


@router.post("", dependencies=[Depends(Require("subscriptions:create"))])
async def create_subscription(
    data: SubscriptionCreateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Create a new subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.create_subscription(
            SubscriptionCreateData(
                party_id=data.party_id,
                plan_name=data.plan_name,
                price=data.price,
                tariff_id=data.tariff_id,
                service_type=data.service_type,
                plan_code=data.plan_code,
                description=data.description,
                currency=data.currency,
                billing_cycle=data.billing_cycle,
                download_speed=data.download_speed,
                upload_speed=data.upload_speed,
                data_cap=data.data_cap,
                router_id=data.router_id,
                ipv4_address=data.ipv4_address,
                ipv6_address=data.ipv6_address,
                mac_address=data.mac_address,
                access_method=data.access_method,
                ppp_username=data.ppp_username,
                ppp_password=data.ppp_password,
                start_date=data.start_date,
                end_date=data.end_date,
            )
        )
        db.commit()
        return _serialize_subscription(subscription)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats", dependencies=[Depends(Require("subscriptions:read"))])
async def get_stats(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscription statistics.
    """
    service = SubscriptionService(db, principal)
    stats = service.get_stats()

    return {
        "active": stats.active,
        "suspended": stats.suspended,
        "pending": stats.pending,
        "cancelled": stats.cancelled,
        "total": stats.total,
        "mrr": float(stats.mrr),
        "new_this_month": stats.new_this_month,
        "provisioned": stats.provisioned,
        "pending_provisioning": stats.pending_provisioning,
        "failed_provisioning": stats.failed_provisioning,
    }


@router.get("/{subscription_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription(
    subscription_id: int = Path(..., description="Subscription ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscription details.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.get_subscription(subscription_id)
        return _serialize_subscription(subscription, include_details=True)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{subscription_id}", dependencies=[Depends(Require("subscriptions:update"))])
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Update subscription details.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.update_subscription(
            subscription_id,
            SubscriptionUpdateData(
                plan_name=data.plan_name,
                plan_code=data.plan_code,
                description=data.description,
                price=data.price,
                currency=data.currency,
                billing_cycle=data.billing_cycle,
                tariff_id=data.tariff_id,
                service_type=data.service_type,
                download_speed=data.download_speed,
                upload_speed=data.upload_speed,
                data_cap=data.data_cap,
                start_date=data.start_date,
                end_date=data.end_date,
            )
        )
        db.commit()
        return _serialize_subscription(subscription)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{subscription_id}", dependencies=[Depends(Require("subscriptions:delete"))])
async def cancel_subscription(
    subscription_id: int,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Cancel a subscription (soft delete).
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.cancel(subscription_id, reason=reason)
        db.commit()
        return {"message": "Subscription cancelled", "id": subscription.id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


# =============================================================================
# LIFECYCLE ENDPOINTS
# =============================================================================

@router.post("/{subscription_id}/activate", dependencies=[Depends(Require("subscriptions:update"))])
async def activate_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Activate a pending subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.activate(subscription_id)
        db.commit()
        return {"message": "Subscription activated", "subscription": _serialize_subscription(subscription)}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, ConflictError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/suspend", dependencies=[Depends(Require("subscriptions:update"))])
async def suspend_subscription(
    subscription_id: int,
    data: StatusChangeSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Suspend an active subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.suspend(subscription_id, reason=data.reason)
        db.commit()
        return {"message": "Subscription suspended", "subscription": _serialize_subscription(subscription)}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, ConflictError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/reactivate", dependencies=[Depends(Require("subscriptions:update"))])
async def reactivate_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Reactivate a suspended subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.reactivate(subscription_id)
        db.commit()
        return {"message": "Subscription reactivated", "subscription": _serialize_subscription(subscription)}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, ConflictError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/upgrade", dependencies=[Depends(Require("subscriptions:update"))])
async def upgrade_subscription(
    subscription_id: int,
    data: UpgradeSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Upgrade subscription to a higher-tier plan.
    """
    service = SubscriptionService(db, principal)

    try:
        result = service.upgrade(
            subscription_id=subscription_id,
            new_tariff_id=data.new_tariff_id,
            effective=data.effective,
            prorate=data.prorate,
        )
        db.commit()
        return {
            "message": "Subscription upgraded",
            "old_plan": result.old_plan,
            "new_plan": result.new_plan,
            "old_price": float(result.old_price),
            "new_price": float(result.new_price),
            "proration_amount": float(result.proration_amount),
            "effective": result.effective,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/downgrade", dependencies=[Depends(Require("subscriptions:update"))])
async def downgrade_subscription(
    subscription_id: int,
    data: DowngradeSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Downgrade subscription to a lower-tier plan.
    """
    service = SubscriptionService(db, principal)

    try:
        result = service.downgrade(
            subscription_id=subscription_id,
            new_tariff_id=data.new_tariff_id,
            effective=data.effective,
            prorate=data.prorate,
        )
        db.commit()
        return {
            "message": "Subscription downgraded",
            "old_plan": result.old_plan,
            "new_plan": result.new_plan,
            "old_price": float(result.old_price),
            "new_price": float(result.new_price),
            "proration_credit": float(result.proration_credit),
            "effective": result.effective,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/renew", dependencies=[Depends(Require("subscriptions:update"))])
async def renew_subscription(
    subscription_id: int,
    data: RenewSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Renew a subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        result = service.renew(
            subscription_id=subscription_id,
            periods=data.periods,
            new_end_date=data.new_end_date,
        )
        db.commit()
        return {
            "message": "Subscription renewed",
            "old_end_date": result.old_end_date.isoformat() if result.old_end_date else None,
            "new_end_date": result.new_end_date.isoformat() if result.new_end_date else None,
            "periods": result.periods,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# NETWORK & PROVISIONING
# =============================================================================

@router.patch("/{subscription_id}/network", dependencies=[Depends(Require("subscriptions:update"))])
async def assign_network(
    subscription_id: int,
    data: NetworkAssignmentSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Assign network resources to subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.assign_network(
            subscription_id,
            NetworkAssignmentData(
                router_id=data.router_id,
                ipv4_address=data.ipv4_address,
                ipv6_address=data.ipv6_address,
                mac_address=data.mac_address,
            )
        )
        db.commit()
        return _serialize_subscription(subscription)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{subscription_id}/provisioning", dependencies=[Depends(Require("subscriptions:update"))])
async def configure_provisioning(
    subscription_id: int,
    data: ProvisioningConfigSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Configure provisioning settings.
    """
    service = SubscriptionService(db, principal)

    try:
        subscription = service.configure_provisioning(
            subscription_id,
            ProvisioningConfigData(
                router_id=data.router_id,
                access_method=data.access_method,
                ppp_username=data.ppp_username,
                ppp_password=data.ppp_password,
            )
        )
        db.commit()
        return _serialize_subscription(subscription)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{subscription_id}/transitions", dependencies=[Depends(Require("subscriptions:read"))])
async def get_available_transitions(
    subscription_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get available status transitions for a subscription.
    """
    service = SubscriptionService(db, principal)

    try:
        transitions = service.get_available_transitions(subscription_id)
        return {
            "transitions": [
                {"target_status": t.target_status, "label": t.label, "color": t.color}
                for t in transitions
            ]
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# HELPERS
# =============================================================================

def _serialize_subscription(subscription, include_details: bool = False) -> Dict[str, Any]:
    """Serialize subscription to dict."""
    data = {
        "id": subscription.id,
        "party_id": subscription.party_id,
        "tariff_id": subscription.tariff_id,
        "plan_name": subscription.plan_name,
        "plan_code": subscription.plan_code,
        "service_type": subscription.service_type.value if subscription.service_type else None,
        "status": subscription.status.value if subscription.status else None,
        "price": float(subscription.price) if subscription.price else 0,
        "currency": subscription.currency,
        "billing_cycle": subscription.billing_cycle,
        "download_speed": subscription.download_speed,
        "upload_speed": subscription.upload_speed,
        "data_cap": subscription.data_cap,
        "router_id": subscription.router_id,
        "ipv4_address": subscription.ipv4_address,
        "provisioned_at": subscription.provisioned_at.isoformat() if subscription.provisioned_at else None,
        "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
        "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
    }

    if include_details:
        data.update({
            "description": subscription.description,
            "ipv6_address": subscription.ipv6_address,
            "mac_address": subscription.mac_address,
            "access_method": subscription.access_method,
            "ppp_username": subscription.ppp_username,
            "provisioning_error": subscription.provisioning_error,
            "cancelled_date": subscription.cancelled_date.isoformat() if subscription.cancelled_date else None,
            "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
        })

        # Include related data
        if subscription.tariff:
            data["tariff"] = {
                "id": subscription.tariff.id,
                "title": subscription.tariff.title,
                "price": float(subscription.tariff.price) if subscription.tariff.price else 0,
            }

        if subscription.router:
            data["router"] = {
                "id": subscription.router.id,
                "title": subscription.router.title,
            }

    return data
