"""Accounts Receivable: AR aging, outstanding receivables."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.cache import cached
from app.database import get_db
from app.models.invoice import Invoice
from app.services.accounting import AccountingSettingsService, ReceivablesService
from app.services.accounting.receivables_types import (
    EnhancedAgingFilters,
    ReceivablesFilters,
)
from app.services.types import PaginationParams

from .helpers import parse_date, resolve_currency_or_raise

router = APIRouter()


def _get_receivables_service(db: Session, principal: Optional[Principal] = None) -> ReceivablesService:
    """Factory to create ReceivablesService with dependencies."""
    settings_service = AccountingSettingsService(db, principal)
    return ReceivablesService(db, settings_service, principal)


# ACCOUNTS RECEIVABLE AGING


@router.get("/accounts-receivable", dependencies=[Depends(Require("accounting:read"))])
def get_accounts_receivable(
    as_of_date: Optional[str] = None,
    party_id: Optional[int] = None,
    customer_account_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get accounts receivable aging report.

    Shows outstanding customer invoices by age bucket.

    Args:
        as_of_date: Calculate aging as of this date (default: today)
        party_id: Filter by party (person or organization)
        customer_account_id: Filter by customer account (billing entity)
        currency: Currency filter

    Returns:
        AR aging with buckets (current, 1-30, 31-60, 61-90, 90+)
    """
    # Parse and validate inputs
    cutoff = parse_date(as_of_date, "as_of_date")
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    # Build filters
    filters = ReceivablesFilters(
        as_of_date=cutoff,
        party_id=party_id,
        customer_account_id=customer_account_id,
        currency=currency,
    )

    # Call service
    service = _get_receivables_service(db, principal)
    report = service.get_aging_report(filters)

    return report.to_dict()


# OUTSTANDING RECEIVABLES


@router.get("/receivables-outstanding", dependencies=[Depends(Require("accounting:read"))])
def get_receivables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Outstanding receivables with top parties.

    Args:
        currency: Currency filter
        top: Number of top parties to return

    Returns:
        Outstanding receivables summary with top parties
    """
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    service = _get_receivables_service(db, principal)
    summary = service.get_outstanding_summary(currency=currency, top_n=top)

    return summary.to_dict()


@router.get("/receivables-aging-enhanced", dependencies=[Depends(Require("accounting:read"))])
@cached("receivables-aging-enhanced", ttl=60)
async def get_receivables_aging_enhanced(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_amount: Optional[float] = Query(None, description="Minimum outstanding amount"),
    search: Optional[str] = Query(None, description="Search by party name"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Enhanced receivables aging grouped by party (matches frontend expectations)."""
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

    # Build filters
    filters = EnhancedAgingFilters(
        currency=currency,
        min_amount=Decimal(str(min_amount)) if min_amount else None,
        search=search,
    )

    pagination = PaginationParams(limit=limit, offset=offset)

    service = _get_receivables_service(db, principal)
    result = service.get_enhanced_aging(filters, pagination)

    return result.to_dict()
