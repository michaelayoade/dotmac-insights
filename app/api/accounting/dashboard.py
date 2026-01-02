"""Dashboard endpoint for accounting overview."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.cache import cached
from app.database import get_db
from app.services.accounting import AccountingSettingsService, DashboardService
from app.services.accounting.dashboard_types import (
    DashboardBundleFilters,
    DashboardFilters,
)

from .helpers import parse_date
from .reports import get_balance_sheet, get_income_statement, get_cash_flow
from .receivables import get_receivables_outstanding
from .payables import get_payables_outstanding
from .banking import get_bank_accounts

router = APIRouter()


def _get_dashboard_service(db: Session, principal: Optional[Principal] = None) -> DashboardService:
    """Factory to create DashboardService with dependencies."""
    settings_service = AccountingSettingsService(db, principal)
    return DashboardService(db, settings_service, principal)


@router.get("/dashboard", dependencies=[Depends(Require("accounting:read"))])
def get_accounting_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get accounting dashboard overview.

    Shows key financial metrics at a glance including:
    - Balance sheet summary (assets, liabilities, equity)
    - Performance metrics (income, expenses, profit)
    - AR/AP summary
    - Bank balances
    - Activity counts

    Args:
        start_date: Period start date (defaults to Jan 1 of current year)
        end_date: Period end date (defaults to today)
        db: Database session

    Returns:
        Dashboard data with all key metrics
    """
    end_dt = parse_date(end_date, "end_date")
    start_dt = parse_date(start_date, "start_date")

    filters = DashboardFilters(
        start_date=start_dt,
        end_date=end_dt,
    )

    service = _get_dashboard_service(db, principal)
    dashboard = service.get_dashboard(filters)

    return dashboard.to_dict()


@router.get("/dashboard/bundle", dependencies=[Depends(Require("accounting:read"))])
@cached("accounting-dashboard-bundle", ttl=60, include_principal=True)
async def get_accounting_dashboard_bundle(
    currency: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get a bundled accounting dashboard payload for core cards.

    Returns dashboard, balance sheet, income statement, cash flow,
    bank accounts, and receivables/payables summaries in one call.
    """
    effective_as_of = as_of_date or end_date

    # Build filters for service
    bundle_filters = DashboardBundleFilters(
        currency=currency,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        as_of_date=parse_date(effective_as_of, "as_of_date"),
        top_n=top,
    )

    # Get dashboard from service
    service = _get_dashboard_service(db, principal)
    dashboard_filters = DashboardFilters(
        start_date=bundle_filters.start_date,
        end_date=bundle_filters.end_date,
    )
    dashboard = service.get_dashboard(dashboard_filters)

    # Call existing route functions for other reports
    # These will be migrated to services in future iterations
    balance_sheet = get_balance_sheet(
        as_of_date=effective_as_of,
        currency=currency,
        db=db,
    )
    income_statement = get_income_statement(
        start_date=start_date,
        end_date=end_date,
        db=db,
    )
    cash_flow = get_cash_flow(
        start_date=start_date,
        end_date=end_date,
        currency=currency,
        db=db,
    )
    receivables = get_receivables_outstanding(
        currency=currency,
        top=top,
        db=db,
        principal=principal,
    )
    payables = get_payables_outstanding(
        currency=currency,
        top=top,
        db=db,
        principal=principal,
    )
    bank_accounts = get_bank_accounts(as_of_date=effective_as_of, db=db)

    return {
        "currency": currency,
        "dashboard": dashboard.to_dict(),
        "balance_sheet": balance_sheet,
        "income_statement": income_statement,
        "cash_flow": cash_flow,
        "receivables_outstanding": receivables,
        "payables_outstanding": payables,
        "bank_accounts": bank_accounts,
    }
