"""Fiscal: Fiscal years, fiscal periods, cost centers."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    AccountType,
    CostCenter,
    FiscalYear,
    GLEntry,
)

from .helpers import parse_date, invalidate_report_cache

router = APIRouter()


class FiscalYearCreateRequest(BaseModel):
    year: str
    year_start_date: Optional[date] = None
    year_end_date: Optional[date] = None
    is_short_year: bool = False
    disabled: bool = False
    auto_created: bool = False


class FiscalYearUpdateRequest(BaseModel):
    year: Optional[str] = None
    year_start_date: Optional[date] = None
    year_end_date: Optional[date] = None
    is_short_year: Optional[bool] = None
    disabled: Optional[bool] = None
    auto_created: Optional[bool] = None


class CostCenterCreateRequest(BaseModel):
    cost_center_name: str
    cost_center_number: Optional[str] = None
    parent_cost_center: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    disabled: bool = False
    lft: Optional[int] = None
    rgt: Optional[int] = None


class CostCenterUpdateRequest(BaseModel):
    cost_center_name: Optional[str] = None
    cost_center_number: Optional[str] = None
    parent_cost_center: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


# =============================================================================
# FISCAL YEARS
# =============================================================================

@router.get("/fiscal-years", dependencies=[Depends(Require("accounting:read"))])
def get_fiscal_years(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get fiscal years list.

    Returns:
        List of fiscal years ordered by most recent first
    """
    years = db.query(FiscalYear).filter(FiscalYear.disabled == False).order_by(FiscalYear.year.desc()).all()

    return {
        "total": len(years),
        "fiscal_years": [
            {
                "id": fy.id,
                "year": fy.year,
                "start_date": fy.year_start_date.isoformat() if fy.year_start_date else None,
                "end_date": fy.year_end_date.isoformat() if fy.year_end_date else None,
                "is_short_year": fy.is_short_year,
            }
            for fy in years
        ],
    }


@router.post("/fiscal-years", dependencies=[Depends(Require("accounting:write"))])
def create_fiscal_year(
    payload: FiscalYearCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a fiscal year locally."""
    fiscal_year = FiscalYear(
        year=payload.year,
        year_start_date=payload.year_start_date,
        year_end_date=payload.year_end_date,
        is_short_year=payload.is_short_year,
        disabled=payload.disabled,
        auto_created=payload.auto_created,
    )
    db.add(fiscal_year)
    db.commit()
    db.refresh(fiscal_year)
    return {"id": fiscal_year.id}


@router.patch("/fiscal-years/{fiscal_year_id}", dependencies=[Depends(Require("accounting:write"))])
def update_fiscal_year(
    fiscal_year_id: int,
    payload: FiscalYearUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a fiscal year locally."""
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(status_code=404, detail="Fiscal year not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fiscal_year, key, value)

    db.commit()
    db.refresh(fiscal_year)
    return {"id": fiscal_year.id}


@router.delete("/fiscal-years/{fiscal_year_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_fiscal_year(
    fiscal_year_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a fiscal year."""
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(status_code=404, detail="Fiscal year not found")

    fiscal_year.disabled = True
    db.commit()
    return {"status": "disabled", "fiscal_year_id": fiscal_year_id}


# =============================================================================
# FISCAL PERIODS
# =============================================================================

@router.get("/fiscal-periods", dependencies=[Depends(Require("books:read"))])
def list_fiscal_periods(
    fiscal_year: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List fiscal periods with optional filtering.

    Args:
        fiscal_year: Filter by fiscal year
        status: Filter by period status

    Returns:
        List of fiscal periods
    """
    from app.models.accounting_ext import FiscalPeriod, FiscalPeriodStatus

    query = db.query(FiscalPeriod).join(FiscalYear, FiscalPeriod.fiscal_year_id == FiscalYear.id)

    if fiscal_year:
        query = query.filter(FiscalYear.year == fiscal_year)
    if status:
        try:
            status_enum = FiscalPeriodStatus(status)
            query = query.filter(FiscalPeriod.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    periods = query.order_by(FiscalPeriod.start_date.desc()).all()

    return {
        "total": len(periods),
        "periods": [
            {
                "id": p.id,
                "fiscal_year_id": p.fiscal_year_id,
                "period_name": p.period_name,
                "period_type": p.period_type.value,
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
                "status": p.status.value,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
                "closed_by_id": p.closed_by_id,
                "has_closing_entry": p.closing_journal_entry_id is not None,
            }
            for p in periods
        ],
    }


@router.get("/fiscal-periods/{period_id}", dependencies=[Depends(Require("books:read"))])
def get_fiscal_period(
    period_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get fiscal period detail with summary.

    Args:
        period_id: Fiscal period ID

    Returns:
        Period details with summary
    """
    from app.services.period_manager import PeriodManager, PeriodNotFoundError

    manager = PeriodManager(db)
    try:
        return manager.get_period_summary(period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fiscal-periods", dependencies=[Depends(Require("books:admin"))])
async def create_fiscal_periods(
    fiscal_year_id: int = Query(..., description="ID of the fiscal year"),
    period_type: str = Query("month", description="Period type: month or quarter"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Auto-create fiscal periods for a fiscal year.

    Args:
        fiscal_year_id: Fiscal year ID
        period_type: Type of periods to create

    Returns:
        Created periods info
    """
    from app.models.accounting_ext import FiscalPeriodType
    from app.services.period_manager import PeriodManager, PeriodError

    try:
        ptype = FiscalPeriodType(period_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid period type: {period_type}")

    manager = PeriodManager(db)
    try:
        periods = manager.create_fiscal_periods_for_year(
            fiscal_year_id=fiscal_year_id,
            period_type=ptype,
            user_id=user.id,
        )
        db.commit()
        return {
            "message": f"Created {len(periods)} periods",
            "count": len(periods),
            "periods": [
                {
                    "id": p.id,
                    "period_name": p.period_name,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat(),
                }
                for p in periods
            ],
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/fiscal-periods/{period_id}/close", dependencies=[Depends(Require("books:close"))])
async def close_fiscal_period(
    period_id: int,
    soft_close: bool = Query(True, description="Soft close (can be reopened) vs hard close"),
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Close a fiscal period.

    Args:
        period_id: Fiscal period ID
        soft_close: Whether to soft close (can reopen) or hard close
        remarks: Closure remarks

    Returns:
        Closure status
    """
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        period = manager.close_period(
            period_id=period_id,
            user_id=user.id,
            soft_close=soft_close,
            remarks=remarks,
        )
        db.commit()

        # Invalidate caches after period close
        await invalidate_report_cache()

        return {
            "message": f"Period {period.period_name} {'soft' if soft_close else 'hard'}-closed",
            "period_id": period.id,
            "period_name": period.period_name,
            "status": period.status.value,
            "closed_at": period.closed_at.isoformat() if period.closed_at else None,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/fiscal-periods/{period_id}/reopen", dependencies=[Depends(Require("books:close"))])
async def reopen_fiscal_period(
    period_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Reopen a soft-closed fiscal period.

    Args:
        period_id: Fiscal period ID
        remarks: Reopening remarks

    Returns:
        Reopen status
    """
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        period = manager.reopen_period(
            period_id=period_id,
            user_id=user.id,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": f"Period {period.period_name} reopened",
            "period_id": period.id,
            "period_name": period.period_name,
            "status": period.status.value,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fiscal-periods/{period_id}/closing-entries", dependencies=[Depends(Require("books:close"))])
async def generate_closing_entries(
    period_id: int,
    retained_earnings_account: Optional[str] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Generate closing journal entries for a fiscal period.

    Args:
        period_id: Fiscal period ID
        retained_earnings_account: Account for retained earnings
        remarks: Closing entry remarks

    Returns:
        Created closing journal entry info
    """
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        je = manager.generate_closing_entries(
            period_id=period_id,
            user_id=user.id,
            retained_earnings_account=retained_earnings_account,
            remarks=remarks,
        )
        db.commit()

        # Invalidate caches after closing entries
        await invalidate_report_cache()

        return {
            "message": "Closing entries generated",
            "journal_entry_id": je.id,
            "total_debit": str(je.total_debit),
            "total_credit": str(je.total_credit),
            "posting_date": je.posting_date.isoformat() if je.posting_date else None,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# COST CENTERS
# =============================================================================

@router.get("/cost-centers", dependencies=[Depends(Require("accounting:read"))])
def get_cost_centers(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost centers list.

    Returns:
        List of cost centers
    """
    centers = db.query(CostCenter).filter(CostCenter.disabled == False).all()

    return {
        "total": len(centers),
        "cost_centers": [
            {
                "id": cc.id,
                "erpnext_id": cc.erpnext_id,
                "name": cc.cost_center_name,
                "number": cc.cost_center_number,
                "parent": cc.parent_cost_center,
                "company": cc.company,
                "is_group": cc.is_group,
            }
            for cc in centers
        ],
    }


@router.get("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:read"))])
def get_cost_center_detail(
    cost_center_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost center detail with expense breakdown.

    Args:
        cost_center_id: Cost center ID
        start_date: Filter from date
        end_date: Filter to date

    Returns:
        Cost center details with expense breakdown
    """
    from sqlalchemy import func

    cc = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost center not found")

    # Get expenses by account for this cost center
    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.cost_center == cc.erpnext_id,
        GLEntry.is_cancelled == False,
    )

    start_dt = parse_date(start_date, "start_date")
    end_dt = parse_date(end_date, "end_date")

    if start_dt:
        query = query.filter(GLEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    results = query.group_by(GLEntry.account).all()

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}
    breakdown = []
    total = Decimal("0")

    for row in results:
        acc = accounts.get(row.account)
        amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
        if acc and acc.root_type == AccountType.EXPENSE:
            breakdown.append({
                "account": row.account,
                "account_name": acc.account_name if acc else row.account,
                "amount": float(amount),
            })
            total += amount

    breakdown.sort(key=lambda x: -abs(x["amount"]))

    return {
        "id": cc.id,
        "erpnext_id": cc.erpnext_id,
        "name": cc.cost_center_name,
        "number": cc.cost_center_number,
        "parent": cc.parent_cost_center,
        "company": cc.company,
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "total_expenses": float(total),
        "breakdown": breakdown,
    }


@router.post("/cost-centers", dependencies=[Depends(Require("accounting:write"))])
def create_cost_center(
    payload: CostCenterCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a cost center locally."""
    center = CostCenter(
        cost_center_name=payload.cost_center_name,
        cost_center_number=payload.cost_center_number,
        parent_cost_center=payload.parent_cost_center,
        company=payload.company,
        is_group=payload.is_group,
        disabled=payload.disabled,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return {"id": center.id}


@router.patch("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:write"))])
def update_cost_center(
    cost_center_id: int,
    payload: CostCenterUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a cost center locally."""
    center = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Cost center not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(center, key, value)

    db.commit()
    db.refresh(center)
    return {"id": center.id}


@router.delete("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_cost_center(
    cost_center_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a cost center."""
    center = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Cost center not found")

    center.disabled = True
    db.commit()
    return {"status": "disabled", "cost_center_id": cost_center_id}
