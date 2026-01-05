"""
Subscription Billing API

Manual billing operations and statistics.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import BillingService
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class DailyBillingTriggerSchema(BaseModel):
    """Schema for triggering daily billing."""

    billing_date: Optional[date] = Field(
        None,
        description="Date to bill for (defaults to yesterday)"
    )
    dry_run: bool = Field(
        False,
        description="Simulate without creating invoices or charges"
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/run-daily", dependencies=[Depends(Require("subscriptions:admin"))])
async def run_daily_billing(
    data: DailyBillingTriggerSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Trigger daily billing run for all eligible subscriptions.

    This processes all subscriptions with daily billing cycle that are due
    for billing, generates invoices, and queues auto-charges for those
    with linked payment subscriptions.

    Requires admin permission. Use dry_run=true to preview without
    creating actual invoices or charges.
    """
    service = BillingService(db, principal)

    summary = service.run_daily_billing(
        billing_date=data.billing_date,
        dry_run=data.dry_run,
    )

    if not data.dry_run:
        db.commit()

    return {
        "run_id": summary.run_id,
        "run_type": summary.run_type,
        "run_date": summary.run_date.isoformat(),
        "dry_run": data.dry_run,
        "total_subscriptions": summary.total_subscriptions,
        "successful": summary.successful,
        "failed": summary.failed,
        "skipped": summary.skipped,
        "total_amount": float(summary.total_amount),
        "currency": summary.currency,
        "started_at": summary.started_at.isoformat() if summary.started_at else None,
        "completed_at": summary.completed_at.isoformat() if summary.completed_at else None,
        "errors": summary.error_details[:20],  # Limit error details in response
    }


@router.get("/billable", dependencies=[Depends(Require("subscriptions:read"))])
async def get_billable_subscriptions(
    billing_cycle: str = Query("daily", description="Billing cycle to check"),
    as_of_date: Optional[date] = Query(None, description="Check as of this date"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get subscriptions due for billing.

    Returns a list of subscriptions that are eligible to be billed
    for the specified billing cycle as of the given date.
    """
    service = BillingService(db, principal)

    billables = service.get_billable_subscriptions(
        billing_cycle=billing_cycle,
        as_of_date=as_of_date,
    )

    return {
        "billing_cycle": billing_cycle,
        "as_of_date": (as_of_date or date.today()).isoformat(),
        "count": len(billables),
        "items": [
            {
                "subscription_id": b.subscription_id,
                "party_id": b.party_id,
                "plan_name": b.plan_name,
                "billing_cycle": b.billing_cycle,
                "price": float(b.price),
                "currency": b.currency,
                "next_billing_date": b.next_billing_date.isoformat() if b.next_billing_date else None,
                "payment_subscription_id": b.payment_subscription_id,
                "has_auto_charge": b.has_auto_charge,
            }
            for b in billables
        ],
    }


@router.get("/stats", dependencies=[Depends(Require("subscriptions:read"))])
async def get_billing_stats(
    period_start: Optional[date] = Query(None, description="Start of reporting period"),
    period_end: Optional[date] = Query(None, description="End of reporting period"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get billing statistics for a period.

    Returns comprehensive billing metrics including:
    - Subscription counts by billing cycle
    - Invoice counts and amounts
    - Collection rates
    - Daily recurring revenue

    If period_start/period_end are not specified, defaults to
    the current month.
    """
    service = BillingService(db, principal)
    return service.get_billing_stats(period_start, period_end)


@router.get("/{subscription_id}/info", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription_billing_info(
    subscription_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get billing information for a specific subscription.

    Returns detailed billing info including:
    - Current price and billing cycle
    - Next billing date
    - Last invoice details
    - Outstanding balance
    - Linked payment subscription (if any)
    """
    service = BillingService(db, principal)

    try:
        info = service.get_billing_info(subscription_id)
        return {
            "subscription_id": info.subscription_id,
            "party_id": info.party_id,
            "plan_name": info.plan_name,
            "price": float(info.price),
            "currency": info.currency,
            "billing_cycle": info.billing_cycle,
            "next_billing_date": info.next_billing_date.isoformat() if info.next_billing_date else None,
            "last_invoice_date": info.last_invoice_date.isoformat() if info.last_invoice_date else None,
            "last_invoice_amount": float(info.last_invoice_amount) if info.last_invoice_amount else None,
            "outstanding_balance": float(info.outstanding_balance) if info.outstanding_balance else 0,
            "payment_subscription_id": info.payment_subscription_id,
            "payment_subscription_status": info.payment_subscription_status,
            "has_auto_charge": info.has_auto_charge,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
