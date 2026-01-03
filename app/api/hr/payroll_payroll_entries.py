"""
Payroll Entries Endpoints

Uses PayrollService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import (
    PayrollEntryFilters,
    PayrollEntryCreateData,
    PayrollEntryUpdateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import PayrollEntryNotFoundError, ValidationError as HRValidationError

router = APIRouter()

# =============================================================================
# PAYROLL ENTRY
# =============================================================================


class PayrollEntryCreate(BaseModel):
    posting_date: date
    payroll_frequency: Optional[str] = None
    start_date: date
    end_date: date
    company: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: Optional[str] = "USD"
    exchange_rate: Optional[Decimal] = Decimal("1")
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None
    docstatus: Optional[int] = 0


class PayrollEntryUpdate(BaseModel):
    posting_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None
    salary_slips_created: Optional[bool] = None
    salary_slips_submitted: Optional[bool] = None
    docstatus: Optional[int] = None


def _serialize_entry(e, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a PayrollEntry model to dict."""
    result = {
        "id": e.id,
        "erpnext_id": e.erpnext_id,
        "posting_date": e.posting_date.isoformat() if e.posting_date else None,
        "payroll_frequency": e.payroll_frequency,
        "start_date": e.start_date.isoformat() if e.start_date else None,
        "end_date": e.end_date.isoformat() if e.end_date else None,
        "company": e.company,
        "salary_slips_created": e.salary_slips_created,
        "salary_slips_submitted": e.salary_slips_submitted,
    }
    if include_timestamps:
        result["department"] = e.department
        result["branch"] = e.branch
        result["designation"] = e.designation
        result["currency"] = e.currency
        result["exchange_rate"] = float(e.exchange_rate) if e.exchange_rate else 1
        result["payment_account"] = e.payment_account
        result["bank_account"] = e.bank_account
        result["docstatus"] = e.docstatus
        result["created_at"] = e.created_at.isoformat() if e.created_at else None
        result["updated_at"] = e.updated_at.isoformat() if e.updated_at else None
    return result


@router.get("/payroll-entries", dependencies=[Depends(Require("hr:read"))])
def list_payroll_entries(
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payroll entries with filtering."""
    service = PayrollService(db)

    filters = PayrollEntryFilters(
        company=company,
        from_date=from_date,
        to_date=to_date,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_payroll_entries(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_entry(e) for e in result.items],
    }


@router.get("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:read"))])
def get_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll entry detail."""
    service = PayrollService(db)
    try:
        e = service.get_payroll_entry(entry_id)
    except PayrollEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    return _serialize_entry(e, include_timestamps=True)


@router.post("/payroll-entries", dependencies=[Depends(Require("hr:write"))])
def create_payroll_entry(
    payload: PayrollEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new payroll entry."""
    service = PayrollService(db, current_user)

    # Validate date order
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    create_data = PayrollEntryCreateData(
        posting_date=payload.posting_date,
        payroll_frequency=payload.payroll_frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
        department=payload.department,
        branch=payload.branch,
        designation=payload.designation,
        currency=payload.currency or "USD",
        exchange_rate=payload.exchange_rate or Decimal("1"),
        payment_account=payload.payment_account,
        bank_account=payload.bank_account,
    )

    try:
        entry = service.create_payroll_entry(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_payroll_entry(entry.id, db)


@router.patch("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
def update_payroll_entry(
    entry_id: int,
    payload: PayrollEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a payroll entry."""
    service = PayrollService(db, current_user)

    update_data = PayrollEntryUpdateData(
        posting_date=payload.posting_date,
        payroll_frequency=payload.payroll_frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
        department=payload.department,
        branch=payload.branch,
        designation=payload.designation,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        payment_account=payload.payment_account,
        bank_account=payload.bank_account,
    )

    try:
        service.update_payroll_entry(entry_id, update_data)
        db.commit()
    except PayrollEntryNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_payroll_entry(entry_id, db)


@router.delete("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
def delete_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a payroll entry."""
    service = PayrollService(db, current_user)

    try:
        service.delete_payroll_entry(entry_id)
        db.commit()
    except PayrollEntryNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    return {"message": "Payroll entry deleted", "id": entry_id}
