"""Fiscal: Fiscal years, fiscal periods, cost centers."""
from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.models.accounting import FiscalYear
from app.services.accounting.fiscal import FiscalService
from app.services.accounting.fiscal_types import (
    CostCenterCreateData,
    CostCenterUpdateData,
    FiscalYearCreateData,
    FiscalYearUpdateData,
)
from app.services.errors import NotFoundError

from .helpers import parse_date, invalidate_report_cache

router = APIRouter()


def get_fiscal_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> FiscalService:
    """Dependency to get FiscalService instance."""
    return FiscalService(db, principal)


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


# FISCAL YEARS

@router.get("/fiscal-years", dependencies=[Depends(Require("accounting:read"))])
def get_fiscal_years(
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Get fiscal years list.

    Returns:
        List of fiscal years ordered by most recent first
    """
    years = service.list_fiscal_years()

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
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Create a fiscal year locally."""
    create_data = FiscalYearCreateData(
        year=payload.year,
        year_start_date=payload.year_start_date,
        year_end_date=payload.year_end_date,
        is_short_year=payload.is_short_year,
        disabled=payload.disabled,
        auto_created=payload.auto_created,
    )
    fiscal_year = service.create_fiscal_year(create_data)
    db.commit()
    return {"id": fiscal_year.id}


@router.patch("/fiscal-years/{fiscal_year_id}", dependencies=[Depends(Require("accounting:write"))])
def update_fiscal_year(
    fiscal_year_id: int,
    payload: FiscalYearUpdateRequest,
    db: Session = Depends(get_db),
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Update a fiscal year locally."""
    update_data = FiscalYearUpdateData(
        year=payload.year,
        year_start_date=payload.year_start_date,
        year_end_date=payload.year_end_date,
        is_short_year=payload.is_short_year,
        disabled=payload.disabled,
        auto_created=payload.auto_created,
    )
    try:
        fiscal_year = service.update_fiscal_year(fiscal_year_id, update_data)
        db.commit()
        return {"id": fiscal_year.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.delete("/fiscal-years/{fiscal_year_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_fiscal_year(
    fiscal_year_id: int,
    db: Session = Depends(get_db),
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Disable a fiscal year."""
    try:
        service.disable_fiscal_year(fiscal_year_id)
        db.commit()
        return {"status": "disabled", "fiscal_year_id": fiscal_year_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


# FISCAL PERIODS

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
    principal: Principal = Depends(get_current_principal),
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
            user_id=principal.id,
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
    principal: Principal = Depends(get_current_principal),
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
            user_id=principal.id,
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
    principal: Principal = Depends(get_current_principal),
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
            user_id=principal.id,
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
    principal: Principal = Depends(get_current_principal),
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
            user_id=principal.id,
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


# COST CENTERS

@router.get("/cost-centers", dependencies=[Depends(Require("accounting:read"))])
def get_cost_centers(
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Get cost centers list.

    Returns:
        List of cost centers
    """
    centers = service.list_cost_centers()

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
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Get cost center detail with expense breakdown.

    Args:
        cost_center_id: Cost center ID
        start_date: Filter from date
        end_date: Filter to date

    Returns:
        Cost center details with expense breakdown
    """
    start_dt = parse_date(start_date, "start_date")
    end_dt = parse_date(end_date, "end_date")

    try:
        result = service.get_cost_center_expenses(cost_center_id, start_dt, end_dt)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    return {
        "id": result.id,
        "erpnext_id": result.erpnext_id,
        "name": result.name,
        "number": result.number,
        "parent": result.parent,
        "company": result.company,
        "period": {
            "start_date": result.start_date.isoformat() if result.start_date else None,
            "end_date": result.end_date.isoformat() if result.end_date else None,
        },
        "total_expenses": result.total_expenses,
        "breakdown": [
            {"account": e.account, "account_name": e.account_name, "amount": e.amount}
            for e in result.breakdown
        ],
    }


@router.post("/cost-centers", dependencies=[Depends(Require("accounting:write"))])
def create_cost_center(
    payload: CostCenterCreateRequest,
    db: Session = Depends(get_db),
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Create a cost center locally."""
    create_data = CostCenterCreateData(
        cost_center_name=payload.cost_center_name,
        cost_center_number=payload.cost_center_number,
        parent_cost_center=payload.parent_cost_center,
        company=payload.company,
        is_group=payload.is_group,
        disabled=payload.disabled,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    center = service.create_cost_center(create_data)
    db.commit()
    return {"id": center.id}


@router.patch("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:write"))])
def update_cost_center(
    cost_center_id: int,
    payload: CostCenterUpdateRequest,
    db: Session = Depends(get_db),
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Update a cost center locally."""
    update_data = CostCenterUpdateData(
        cost_center_name=payload.cost_center_name,
        cost_center_number=payload.cost_center_number,
        parent_cost_center=payload.parent_cost_center,
        company=payload.company,
        is_group=payload.is_group,
        disabled=payload.disabled,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    try:
        center = service.update_cost_center(cost_center_id, update_data)
        db.commit()
        return {"id": center.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.delete("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_cost_center(
    cost_center_id: int,
    db: Session = Depends(get_db),
    service: FiscalService = Depends(get_fiscal_service),
) -> Dict[str, Any]:
    """Disable a cost center."""
    try:
        service.disable_cost_center(cost_center_id)
        db.commit()
        return {"status": "disabled", "cost_center_id": cost_center_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
