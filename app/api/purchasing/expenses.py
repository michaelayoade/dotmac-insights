"""GL Expenses API endpoints."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.services.purchasing import GLExpenseService, PurchasingAnalyticsService, ExpenseFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

from ._deps import (
    get_expense_service,
    get_analytics_service,
    RequireRead,
    parse_date,
    handle_service_error,
)

router = APIRouter(prefix="/expenses", tags=["purchasing"])


@router.get("", dependencies=[RequireRead])
async def get_expenses(
    account: Optional[str] = None,
    cost_center: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: GLExpenseService = Depends(get_expense_service),
) -> Dict[str, Any]:
    """Get expense entries from GL."""
    filters = ExpenseFilters(
        account=account,
        cost_center=cost_center,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        min_amount=Decimal(str(min_amount)) if min_amount else None,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_expenses(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "expenses": [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "account": e.account,
                "amount": float(e.debit),
                "party": e.party,
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
            }
            for e in result.data
        ],
    }


@router.get("/types", dependencies=[RequireRead])
async def get_expense_types(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: PurchasingAnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Get expense breakdown by account type."""
    return service.get_expense_types(
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
    )


@router.get("/{expense_id}", dependencies=[RequireRead])
async def get_expense_detail(
    expense_id: int,
    service: GLExpenseService = Depends(get_expense_service),
) -> Dict[str, Any]:
    """Get expense entry details."""
    try:
        detail = service.get_expense(expense_id)
    except NotFoundError as e:
        handle_service_error(e)

    expense = detail["expense"]
    account = detail["account"]

    return {
        "id": expense.id,
        "posting_date": expense.posting_date.isoformat() if expense.posting_date else None,
        "account": expense.account,
        "account_name": account.account_name if account else expense.account,
        "account_type": account.account_type if account else None,
        "amount": float(expense.debit),
        "party_type": expense.party_type,
        "party": expense.party,
        "voucher_type": expense.voucher_type,
        "voucher_no": expense.voucher_no,
        "cost_center": expense.cost_center,
        "fiscal_year": expense.fiscal_year,
    }
