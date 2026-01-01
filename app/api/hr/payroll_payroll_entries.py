"""
Payroll Entries Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.hr_payroll import PayrollEntry, SalarySlip
from .helpers import decimal_or_default, validate_date_order

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
    query = db.query(PayrollEntry)

    if company:
        query = query.filter(PayrollEntry.company.ilike(f"%{company}%"))
    if from_date:
        query = query.filter(PayrollEntry.start_date >= from_date)
    if to_date:
        query = query.filter(PayrollEntry.end_date <= to_date)

    total = query.count()
    entries = query.order_by(PayrollEntry.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
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
            for e in entries
        ],
    }


@router.get("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:read"))])
def get_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll entry detail."""
    e = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    return {
        "id": e.id,
        "erpnext_id": e.erpnext_id,
        "posting_date": e.posting_date.isoformat() if e.posting_date else None,
        "payroll_frequency": e.payroll_frequency,
        "start_date": e.start_date.isoformat() if e.start_date else None,
        "end_date": e.end_date.isoformat() if e.end_date else None,
        "company": e.company,
        "department": e.department,
        "branch": e.branch,
        "designation": e.designation,
        "currency": e.currency,
        "exchange_rate": float(e.exchange_rate) if e.exchange_rate else 1,
        "payment_account": e.payment_account,
        "bank_account": e.bank_account,
        "salary_slips_created": e.salary_slips_created,
        "salary_slips_submitted": e.salary_slips_submitted,
        "docstatus": e.docstatus,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.post("/payroll-entries", dependencies=[Depends(Require("hr:write"))])
def create_payroll_entry(
    payload: PayrollEntryCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new payroll entry."""
    validate_date_order(payload.start_date, payload.end_date)

    entry = PayrollEntry(
        posting_date=payload.posting_date,
        payroll_frequency=payload.payroll_frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
        department=payload.department,
        branch=payload.branch,
        designation=payload.designation,
        currency=payload.currency or "USD",
        exchange_rate=decimal_or_default(payload.exchange_rate, Decimal("1")),
        payment_account=payload.payment_account,
        bank_account=payload.bank_account,
        docstatus=payload.docstatus or 0,
    )
    db.add(entry)
    db.commit()
    return get_payroll_entry(entry.id, db)


@router.patch("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
def update_payroll_entry(
    entry_id: int,
    payload: PayrollEntryUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payroll entry."""
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "exchange_rate":
                setattr(entry, field, decimal_or_default(value, Decimal("1")))
            else:
                setattr(entry, field, value)

    validate_date_order(entry.start_date, entry.end_date)

    db.commit()
    return get_payroll_entry(entry.id, db)


@router.delete("/payroll-entries/{entry_id}", dependencies=[Depends(Require("hr:write"))])
def delete_payroll_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a payroll entry."""
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")

    db.delete(entry)
    db.commit()
    return {"message": "Payroll entry deleted", "id": entry_id}

