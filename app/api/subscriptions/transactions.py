"""
Service Transactions API

Audit trail and transaction history endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from decimal import Decimal

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    ServiceTransactionService,
    ServiceTransactionFilters,
    ServiceTransactionType,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

router = APIRouter()


class ManualTransactionSchema(BaseModel):
    """Schema for creating manual transactions."""
    subscription_id: int
    transaction_type: str
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChargeSchema(BaseModel):
    """Schema for recording charges."""
    subscription_id: int
    amount: Decimal
    charge_type: str  # installation, activation, reconnection, early_termination, other
    description: Optional[str] = None
    reference: Optional[str] = None
    invoice_id: Optional[int] = None


class CreditSchema(BaseModel):
    """Schema for recording credits."""
    subscription_id: int
    amount: Decimal
    reason: str
    description: Optional[str] = None
    reference: Optional[str] = None


@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def list_transactions(
    subscription_id: Optional[int] = Query(None, description="Filter by subscription"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    transaction_type: Optional[str] = Query(None, description="Filter by type"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List service transactions.
    """
    service = ServiceTransactionService(db, principal)

    filters = ServiceTransactionFilters(
        subscription_id=subscription_id,
        party_id=party_id,
        transaction_type=ServiceTransactionType(transaction_type) if transaction_type else None,
        date_from=date_from,
        date_to=date_to,
    )

    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = service.list_transactions(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_transaction(t) for t in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/summary", dependencies=[Depends(Require("subscriptions:read"))])
async def get_transaction_summary(
    subscription_id: Optional[int] = Query(None, description="Subscription ID"),
    party_id: Optional[int] = Query(None, description="Party ID"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get transaction summary with totals by type.
    """
    service = ServiceTransactionService(db, principal)

    summary = service.get_summary(
        subscription_id=subscription_id,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "total_transactions": summary.total_transactions,
        "total_charges": float(summary.total_charges),
        "total_credits": float(summary.total_credits),
        "net_amount": float(summary.net_amount),
        "by_type": summary.by_type,
        "period_start": str(summary.period_start) if summary.period_start else None,
        "period_end": str(summary.period_end) if summary.period_end else None,
    }


@router.get("/types", dependencies=[Depends(Require("subscriptions:read"))])
async def get_transaction_types() -> Dict[str, Any]:
    """
    Get available transaction types.
    """
    return {
        "types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in ServiceTransactionType
        ]
    }


@router.get("/{transaction_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_transaction(
    transaction_id: int = Path(..., description="Transaction ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get transaction details.
    """
    service = ServiceTransactionService(db, principal)

    try:
        transaction = service.get_transaction(transaction_id)
        return _serialize_transaction(transaction)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/subscription/{subscription_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription_transactions(
    subscription_id: int = Path(..., description="Subscription ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get transactions for a subscription.
    """
    service = ServiceTransactionService(db, principal)

    filters = ServiceTransactionFilters(
        subscription_id=subscription_id,
        transaction_type=ServiceTransactionType(transaction_type) if transaction_type else None,
    )

    result = service.list_transactions(
        filters=filters,
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "subscription_id": subscription_id,
        "items": [_serialize_transaction(t) for t in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/party/{party_id}/history", dependencies=[Depends(Require("subscriptions:read"))])
async def get_party_transaction_history(
    party_id: int = Path(..., description="Party ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get full transaction history for a party.
    """
    service = ServiceTransactionService(db, principal)

    result = service.get_party_history(
        party_id=party_id,
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "party_id": party_id,
        "items": [_serialize_transaction(t) for t in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/charge", dependencies=[Depends(Require("subscriptions:update"))])
async def record_charge(
    data: ChargeSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Record a subscription charge.
    """
    service = ServiceTransactionService(db, principal)

    try:
        transaction = service.record_subscription_charge(
            subscription_id=data.subscription_id,
            amount=data.amount,
            charge_type=data.charge_type,
            description=data.description,
            reference=data.reference,
            invoice_id=data.invoice_id,
        )
        db.commit()

        return {
            "success": True,
            "transaction": _serialize_transaction(transaction),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/credit", dependencies=[Depends(Require("subscriptions:update"))])
async def record_credit(
    data: CreditSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Record a credit for a subscription.
    """
    service = ServiceTransactionService(db, principal)

    try:
        transaction = service.record_credit(
            subscription_id=data.subscription_id,
            amount=data.amount,
            reason=data.reason,
            description=data.description,
            reference=data.reference,
        )
        db.commit()

        return {
            "success": True,
            "transaction": _serialize_transaction(transaction),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _serialize_transaction(transaction) -> Dict[str, Any]:
    """Serialize transaction to dict."""
    return {
        "id": transaction.id,
        "subscription_id": transaction.subscription_id,
        "party_id": transaction.party_id,
        "transaction_type": transaction.transaction_type.value if transaction.transaction_type else None,
        "status": transaction.status,
        "amount": float(transaction.amount) if transaction.amount else None,
        "old_value": transaction.old_value,
        "new_value": transaction.new_value,
        "description": transaction.description,
        "reference": transaction.reference,
        "invoice_id": transaction.invoice_id,
        "payment_id": transaction.payment_id,
        "credit_note_id": transaction.credit_note_id,
        "performed_by": transaction.performed_by,
        "metadata": transaction.metadata,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
    }
