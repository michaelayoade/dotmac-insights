"""
Salary Slips Endpoints

Uses PayrollService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_payroll import SalarySlip, SalarySlipStatus
from app.models.gateway_transaction import GatewayProvider
from app.models.transfer import Transfer, TransferStatus, TransferType
from app.services.audit_logger import AuditLogger
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import (
    SalarySlipFilters,
    SalarySlipCreateData,
    SalarySlipUpdateData,
    SlipEarningData,
    SlipDeductionData,
    SlipPaymentData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import (
    SalarySlipNotFoundError,
    SlipStatusTransitionError,
    PayrollEntryNotFoundError,
    PayrollAlreadyProcessedError,
    ValidationError as HRValidationError,
)
from app.api.integrations.transfers import get_transfer_client, generate_transfer_reference
from app.integrations.payments.base import TransferRecipient, TransferRequest
from app.integrations.payments.config import get_payment_settings
from .helpers import csv_response, now, decimal_or_default, validate_date_order

router = APIRouter()

# =============================================================================
# SALARY SLIP
# =============================================================================

class SalarySlipComponentPayload(BaseModel):
    salary_component: str
    abbr: Optional[str] = None
    amount: Optional[Decimal] = Decimal("0")
    default_amount: Optional[Decimal] = Decimal("0")
    additional_amount: Optional[Decimal] = Decimal("0")
    year_to_date: Optional[Decimal] = Decimal("0")
    statistical_component: Optional[bool] = False
    do_not_include_in_total: Optional[bool] = False
    idx: Optional[int] = 0


class SalarySlipCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    salary_structure: Optional[str] = None
    posting_date: date
    start_date: date
    end_date: date
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = "USD"
    total_working_days: Optional[Decimal] = Decimal("0")
    absent_days: Optional[Decimal] = Decimal("0")
    payment_days: Optional[Decimal] = Decimal("0")
    leave_without_pay: Optional[Decimal] = Decimal("0")
    gross_pay: Optional[Decimal] = Decimal("0")
    total_deduction: Optional[Decimal] = Decimal("0")
    net_pay: Optional[Decimal] = Decimal("0")
    rounded_total: Optional[Decimal] = Decimal("0")
    status: Optional[SalarySlipStatus] = SalarySlipStatus.DRAFT
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    payroll_entry: Optional[str] = None
    docstatus: Optional[int] = 0
    earnings: Optional[List[SalarySlipComponentPayload]] = None
    deductions: Optional[List[SalarySlipComponentPayload]] = None


class PayrollPayoutItem(BaseModel):
    salary_slip_id: int
    account_number: str
    bank_code: str
    account_name: Optional[str] = None


class PayrollEntryPayoutRequest(BaseModel):
    payouts: List[PayrollPayoutItem]
    provider: Optional[str] = None
    currency: Optional[str] = None
    earnings: Optional[List[SalarySlipComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalarySlipComponentPayload]] = Field(default=None)


class SalarySlipUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    salary_structure: Optional[str] = None
    posting_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    total_working_days: Optional[Decimal] = None
    absent_days: Optional[Decimal] = None
    payment_days: Optional[Decimal] = None
    leave_without_pay: Optional[Decimal] = None
    gross_pay: Optional[Decimal] = None
    total_deduction: Optional[Decimal] = None
    net_pay: Optional[Decimal] = None
    rounded_total: Optional[Decimal] = None
    status: Optional[SalarySlipStatus] = None
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    payroll_entry: Optional[str] = None
    docstatus: Optional[int] = None
    earnings: Optional[List[SalarySlipComponentPayload]] = Field(default=None)
    deductions: Optional[List[SalarySlipComponentPayload]] = Field(default=None)


class SalarySlipBulkAction(BaseModel):
    slip_ids: List[int]


def _serialize_slip(s, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a SalarySlip model to dict."""
    result = {
        "id": s.id,
        "erpnext_id": s.erpnext_id,
        "employee": s.employee,
        "employee_id": s.employee_id,
        "employee_name": s.employee_name,
        "posting_date": s.posting_date.isoformat() if s.posting_date else None,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "gross_pay": float(s.gross_pay) if s.gross_pay else 0,
        "total_deduction": float(s.total_deduction) if s.total_deduction else 0,
        "net_pay": float(s.net_pay) if s.net_pay else 0,
        "status": s.status.value if s.status else None,
        "company": s.company,
    }
    if include_details:
        result["department"] = s.department
        result["designation"] = s.designation
        result["branch"] = s.branch
        result["salary_structure"] = s.salary_structure
        result["payroll_frequency"] = s.payroll_frequency
        result["currency"] = s.currency
        result["total_working_days"] = float(s.total_working_days) if s.total_working_days else 0
        result["absent_days"] = float(s.absent_days) if s.absent_days else 0
        result["payment_days"] = float(s.payment_days) if s.payment_days else 0
        result["leave_without_pay"] = float(s.leave_without_pay) if s.leave_without_pay else 0
        result["rounded_total"] = float(s.rounded_total) if s.rounded_total else 0
        result["bank_name"] = s.bank_name
        result["bank_account_no"] = s.bank_account_no
        result["payroll_entry"] = s.payroll_entry
        result["docstatus"] = s.docstatus
        result["earnings"] = [
            {
                "id": e.id,
                "salary_component": e.salary_component,
                "abbr": e.abbr,
                "amount": float(e.amount) if e.amount else 0,
                "default_amount": float(e.default_amount) if e.default_amount else 0,
                "additional_amount": float(e.additional_amount) if e.additional_amount else 0,
                "year_to_date": float(e.year_to_date) if e.year_to_date else 0,
                "statistical_component": e.statistical_component,
                "do_not_include_in_total": e.do_not_include_in_total,
                "idx": e.idx,
            }
            for e in sorted(s.earnings, key=lambda x: x.idx)
        ]
        result["deductions"] = [
            {
                "id": d.id,
                "salary_component": d.salary_component,
                "abbr": d.abbr,
                "amount": float(d.amount) if d.amount else 0,
                "default_amount": float(d.default_amount) if d.default_amount else 0,
                "additional_amount": float(d.additional_amount) if d.additional_amount else 0,
                "year_to_date": float(d.year_to_date) if d.year_to_date else 0,
                "statistical_component": d.statistical_component,
                "do_not_include_in_total": d.do_not_include_in_total,
                "idx": d.idx,
            }
            for d in sorted(s.deductions, key=lambda x: x.idx)
        ]
        result["created_at"] = s.created_at.isoformat() if s.created_at else None
        result["updated_at"] = s.updated_at.isoformat() if s.updated_at else None
    return result


@router.get("/salary-slips", dependencies=[Depends(Require("hr:read"))])
def list_salary_slips(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    payroll_entry: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List salary slips with filtering."""
    service = PayrollService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = SalarySlipStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = SalarySlipFilters(
        employee_id=employee_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
        payroll_entry=payroll_entry,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_salary_slips(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_slip(s) for s in result.items],
    }


@router.get("/salary-slips/export", dependencies=[Depends(Require("hr:read"))])
def export_salary_slips(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export salary slips to CSV."""
    service = PayrollService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = SalarySlipStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = SalarySlipFilters(
        employee_id=employee_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    # Get all for export
    result = service.list_salary_slips(filters, PaginationParams(offset=0, limit=10000))

    rows: List[List[Any]] = [[
        "id",
        "employee",
        "employee_name",
        "posting_date",
        "start_date",
        "end_date",
        "gross_pay",
        "total_deduction",
        "net_pay",
        "status",
        "company",
    ]]
    for s in result.items:
        rows.append([
            s.id,
            s.employee,
            s.employee_name or "",
            s.posting_date.isoformat() if s.posting_date else "",
            s.start_date.isoformat() if s.start_date else "",
            s.end_date.isoformat() if s.end_date else "",
            float(s.gross_pay or 0),
            float(s.total_deduction or 0),
            float(s.net_pay or 0),
            s.status.value if s.status else "",
            s.company or "",
        ])
    return csv_response(rows, "salary_slips.csv")


@router.get("/salary-slips/summary", dependencies=[Depends(Require("hr:read"))])
def salary_slips_summary(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary slips summary statistics."""
    service = PayrollService(db)
    return service.get_slips_summary(from_date, to_date, company)


@router.get("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:read"))])
def get_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get salary slip detail with earnings and deductions."""
    service = PayrollService(db)
    try:
        s = service.get_salary_slip(slip_id)
    except SalarySlipNotFoundError:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    return _serialize_slip(s, include_details=True)


@router.post("/salary-slips", dependencies=[Depends(Require("hr:write"))])
def create_salary_slip(
    payload: SalarySlipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new salary slip with earnings and deductions."""
    validate_date_order(payload.start_date, payload.end_date)

    service = PayrollService(db, current_user)

    # Convert earnings to service data types
    earnings_data = []
    if payload.earnings:
        for idx, e in enumerate(payload.earnings):
            earnings_data.append(SlipEarningData(
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=decimal_or_default(e.amount),
                default_amount=decimal_or_default(e.default_amount),
                additional_amount=decimal_or_default(e.additional_amount),
                year_to_date=decimal_or_default(e.year_to_date),
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            ))

    # Convert deductions to service data types
    deductions_data = []
    if payload.deductions:
        for idx, d in enumerate(payload.deductions):
            deductions_data.append(SlipDeductionData(
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=decimal_or_default(d.amount),
                default_amount=decimal_or_default(d.default_amount),
                additional_amount=decimal_or_default(d.additional_amount),
                year_to_date=decimal_or_default(d.year_to_date),
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            ))

    create_data = SalarySlipCreateData(
        employee=payload.employee,
        employee_id=payload.employee_id or 0,
        employee_name=payload.employee_name,
        department=payload.department,
        designation=payload.designation,
        branch=payload.branch,
        salary_structure=payload.salary_structure,
        posting_date=payload.posting_date,
        start_date=payload.start_date,
        end_date=payload.end_date,
        payroll_frequency=payload.payroll_frequency,
        company=payload.company,
        currency=payload.currency or "USD",
        total_working_days=decimal_or_default(payload.total_working_days),
        absent_days=decimal_or_default(payload.absent_days),
        payment_days=decimal_or_default(payload.payment_days),
        leave_without_pay=decimal_or_default(payload.leave_without_pay),
        gross_pay=decimal_or_default(payload.gross_pay),
        total_deduction=decimal_or_default(payload.total_deduction),
        net_pay=decimal_or_default(payload.net_pay),
        bank_name=payload.bank_name,
        bank_account_no=payload.bank_account_no,
        payroll_entry=payload.payroll_entry,
        earnings=earnings_data,
        deductions=deductions_data,
    )

    try:
        slip = service.create_salary_slip(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip.id, db)


@router.patch("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:write"))])
def update_salary_slip(
    slip_id: int,
    payload: SalarySlipUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a salary slip and optionally replace earnings/deductions."""
    service = PayrollService(db, current_user)

    # Convert earnings to service data types
    earnings_data = None
    if payload.earnings is not None:
        earnings_data = []
        for idx, e in enumerate(payload.earnings):
            earnings_data.append(SlipEarningData(
                salary_component=e.salary_component,
                abbr=e.abbr,
                amount=decimal_or_default(e.amount),
                default_amount=decimal_or_default(e.default_amount),
                additional_amount=decimal_or_default(e.additional_amount),
                year_to_date=decimal_or_default(e.year_to_date),
                statistical_component=e.statistical_component or False,
                do_not_include_in_total=e.do_not_include_in_total or False,
                idx=e.idx if e.idx is not None else idx,
            ))

    # Convert deductions to service data types
    deductions_data = None
    if payload.deductions is not None:
        deductions_data = []
        for idx, d in enumerate(payload.deductions):
            deductions_data.append(SlipDeductionData(
                salary_component=d.salary_component,
                abbr=d.abbr,
                amount=decimal_or_default(d.amount),
                default_amount=decimal_or_default(d.default_amount),
                additional_amount=decimal_or_default(d.additional_amount),
                year_to_date=decimal_or_default(d.year_to_date),
                statistical_component=d.statistical_component or False,
                do_not_include_in_total=d.do_not_include_in_total or False,
                idx=d.idx if d.idx is not None else idx,
            ))

    update_data = SalarySlipUpdateData(
        total_working_days=payload.total_working_days,
        absent_days=payload.absent_days,
        payment_days=payload.payment_days,
        leave_without_pay=payload.leave_without_pay,
        gross_pay=payload.gross_pay,
        total_deduction=payload.total_deduction,
        net_pay=payload.net_pay,
        earnings=earnings_data,
        deductions=deductions_data,
    )

    try:
        service.update_salary_slip(slip_id, update_data)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip_id, db)


@router.delete("/salary-slips/{slip_id}", dependencies=[Depends(Require("hr:write"))])
def delete_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a salary slip (must be in DRAFT status)."""
    service = PayrollService(db, current_user)

    try:
        service.delete_salary_slip(slip_id)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Salary slip deleted", "id": slip_id}


@router.post("/salary-slips/{slip_id}/submit", dependencies=[Depends(Require("hr:write"))])
def submit_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit a salary slip."""
    service = PayrollService(db, current_user)

    try:
        service.submit_salary_slip(slip_id)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip_id, db)


@router.post("/salary-slips/{slip_id}/cancel", dependencies=[Depends(Require("hr:write"))])
def cancel_salary_slip(
    slip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a salary slip."""
    service = PayrollService(db, current_user)

    try:
        service.cancel_salary_slip(slip_id)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip_id, db)


@router.post("/salary-slips/bulk/submit", dependencies=[Depends(Require("hr:write"))])
def bulk_submit_salary_slips(
    payload: SalarySlipBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk submit salary slips."""
    service = PayrollService(db, current_user)
    result = service.bulk_submit_slips(payload.slip_ids)
    db.commit()
    return {"updated": result.succeeded, "requested": result.requested, "failed": result.failed}


@router.post("/salary-slips/bulk/cancel", dependencies=[Depends(Require("hr:write"))])
def bulk_cancel_salary_slips(
    payload: SalarySlipBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk cancel salary slips."""
    service = PayrollService(db, current_user)
    result = service.bulk_cancel_slips(payload.slip_ids)
    db.commit()
    return {"updated": result.succeeded, "requested": result.requested, "failed": result.failed}


# =============================================================================
# PAYROLL GENERATION
# =============================================================================

@router.post("/payroll-entries/{entry_id}/generate-slips", dependencies=[Depends(Require("hr:write"))])
def generate_payroll_slips(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Generate draft salary slips for a payroll entry.

    Finds employees with active salary structure assignments matching the
    payroll entry's filters (company, department, designation) and
    creates draft salary slips for each.

    Uses Nigerian tax compliance when NIGERIA_COMPLIANCE_ENABLED is True.
    """
    service = PayrollService(db, current_user)

    try:
        result = service.generate_salary_slips_with_tax(entry_id)
        db.commit()
    except PayrollEntryNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    except PayrollAlreadyProcessedError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Salary slips already created for this entry")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "created": result.created_count,
        "skipped": result.skipped_count,
        "created_details": [
            {
                "id": d.id,
                "employee": d.employee,
                "employee_id": d.employee_id,
                "gross_pay": float(d.gross_pay),
                "net_pay": float(d.net_pay),
                "paye": float(d.paye),
                "pension": float(d.pension),
                "is_paye_exempt": d.is_paye_exempt,
            }
            for d in result.created_details
        ],
        "skipped_details": [
            {
                "employee_id": d.employee_id,
                "employee": d.employee,
                "reason": d.reason,
            }
            for d in result.skipped_details
        ],
    }


@router.post("/payroll-entries/{entry_id}/regenerate-slips", dependencies=[Depends(Require("hr:write"))])
def regenerate_payroll_slips(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Delete existing draft slips and regenerate for a payroll entry.
    Only draft slips will be deleted; submitted/paid slips are preserved.
    """
    service = PayrollService(db, current_user)

    try:
        result = service.regenerate_salary_slips(entry_id)
        db.commit()
    except PayrollEntryNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "created": result.created_count,
        "skipped": result.skipped_count,
        "deleted_drafts": result.deleted_drafts,
        "created_details": [
            {
                "id": d.id,
                "employee": d.employee,
                "employee_id": d.employee_id,
                "gross_pay": float(d.gross_pay),
                "net_pay": float(d.net_pay),
                "paye": float(d.paye),
                "pension": float(d.pension),
                "is_paye_exempt": d.is_paye_exempt,
            }
            for d in result.created_details
        ],
        "skipped_details": [
            {
                "employee_id": d.employee_id,
                "employee": d.employee,
                "reason": d.reason,
            }
            for d in result.skipped_details
        ],
    }


# =============================================================================
# PAYMENT AND VOID
# =============================================================================

class MarkPaidPayload(BaseModel):
    payment_reference: Optional[str] = None
    payment_mode: Optional[str] = None


class VoidSlipPayload(BaseModel):
    reason: str


@router.post("/salary-slips/{slip_id}/mark-paid", dependencies=[Depends(Require("hr:write"))])
def mark_salary_slip_paid(
    slip_id: int,
    payload: MarkPaidPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a submitted salary slip as paid with payment metadata."""
    service = PayrollService(db, current_user)

    payment_data = SlipPaymentData(
        payment_reference=payload.payment_reference,
        payment_mode=payload.payment_mode,
    )

    try:
        service.mark_slip_paid(slip_id, payment_data)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip_id, db)


@router.post("/salary-slips/{slip_id}/void", dependencies=[Depends(Require("hr:write"))])
def void_salary_slip(
    slip_id: int,
    payload: VoidSlipPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Void a salary slip with reason. Only submitted slips can be voided."""
    service = PayrollService(db, current_user)

    try:
        service.void_salary_slip(slip_id, payload.reason)
        db.commit()
    except SalarySlipNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Salary slip not found")
    except SlipStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_salary_slip(slip_id, db)


# =============================================================================
# PAYROLL PAYOUTS VIA PAYMENT INTEGRATIONS
# =============================================================================

@router.post(
    "/payroll-entries/{entry_id}/payouts",
    dependencies=[Depends(Require("hr:write"))],
)
async def initiate_payroll_payouts(
    entry_id: int,
    payload: PayrollEntryPayoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Initiate bank transfers for salary slips in a payroll entry.
    """
    if not payload.payouts:
        raise HTTPException(status_code=400, detail="No payouts supplied")

    service = PayrollService(db, current_user)

    # Validate slips using service
    slip_ids = [p.salary_slip_id for p in payload.payouts]
    try:
        slips = service.get_payable_slips(entry_id, slip_ids)
    except PayrollEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    except SalarySlipNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Salary slips not found: {e.slip_id}")
    except SlipStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    slip_map: Dict[int, SalarySlip] = {s.id: s for s in slips}

    # Get payroll entry for reference
    entry = service.get_payroll_entry(entry_id)

    client = get_transfer_client(payload.provider)
    try:
        transfer_requests: List[TransferRequest] = []
        for payout in payload.payouts:
            slip = slip_map[payout.salary_slip_id]
            amount = slip.net_pay or Decimal("0")
            if amount <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Slip {slip.id} has no payable amount",
                )

            currency = payload.currency or slip.currency or "NGN"
            recipient = TransferRecipient(
                account_number=payout.account_number,
                bank_code=payout.bank_code,
                account_name=payout.account_name or slip.employee_name or slip.employee,
                currency=currency,
            )

            transfer_requests.append(
                TransferRequest(
                    amount=amount,
                    currency=currency,
                    recipient=recipient,
                    reference=generate_transfer_reference(),
                    reason=f"Payroll {entry.id} - {slip.employee}",
                    metadata={"salary_slip_id": slip.id, "payroll_entry_id": entry.id},
                )
            )

        # Initiate transfers (bulk when more than one)
        if len(transfer_requests) > 1:
            results = await client.initiate_bulk_transfer(transfer_requests)
        else:
            single_result = await client.initiate_transfer(transfer_requests[0])
            results = [single_result]

        status_map = {
            "success": TransferStatus.SUCCESS,
            "failed": TransferStatus.FAILED,
            "pending": TransferStatus.PENDING,
            "processing": TransferStatus.PROCESSING,
            "reversed": TransferStatus.REVERSED,
        }
        provider_value = (payload.provider or "").lower()
        provider_enum = (
            GatewayProvider.FLUTTERWAVE
            if provider_value == GatewayProvider.FLUTTERWAVE.value
            else GatewayProvider.PAYSTACK
        )

        response_items = []
        for transfer_request, result in zip(transfer_requests, results):
            metadata = transfer_request.metadata or {}
            slip_id = metadata.get("salary_slip_id")
            if slip_id is None or not isinstance(slip_id, int):
                raise HTTPException(status_code=400, detail="Transfer metadata missing salary slip id")
            slip = slip_map[slip_id]

            transfer_record = Transfer(
                reference=result.reference,
                provider=provider_enum,
                provider_reference=result.provider_reference,
                transfer_type=TransferType.PAYROLL,
                amount=transfer_request.amount,
                currency=transfer_request.currency,
                status=status_map.get(result.status.value, TransferStatus.PENDING),
                recipient_account=transfer_request.recipient.account_number,
                recipient_bank_code=transfer_request.recipient.bank_code,
                recipient_name=transfer_request.recipient.account_name,
                recipient_code=result.recipient_code,
                reason=transfer_request.reason,
                fee=result.fee,
                employee_id=slip.employee_id,
                salary_slip_id=slip.id,
                payroll_run_id=entry.id,
                company=slip.company,
                created_by_id=current_user.id if current_user else None,
            )
            db.add(transfer_record)

            # Update slip payment info
            slip.payment_reference = result.reference
            slip.payment_mode = "bank_transfer"
            slip.paid_at = now()
            slip.paid_by_id = current_user.id if current_user else None
            if result.status.value == "success":
                slip.status = SalarySlipStatus.PAID

            response_items.append(
                {
                    "reference": result.reference,
                    "provider_reference": result.provider_reference,
                    "status": result.status.value,
                    "amount": float(result.amount),
                    "salary_slip_id": slip.id,
                }
            )

        db.commit()

        return {
            "count": len(response_items),
            "transfers": response_items,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    finally:
        await client.close()


# =============================================================================
# HANDOFF TO BOOKS
# =============================================================================

@router.post(
    "/payroll-entries/{entry_id}/handoff",
    dependencies=[Depends(Require("hr:write"))],
)
def handoff_payroll_to_books(
    entry_id: int,
    payload: PayrollEntryPayoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Create transfer drafts for a payroll entry without initiating payouts.

    Accounting can pay these from the Books gateway UI.
    """
    if not payload.payouts:
        raise HTTPException(status_code=400, detail="No payouts supplied")

    service = PayrollService(db, current_user)

    # Validate slips using service
    slip_ids = [p.salary_slip_id for p in payload.payouts]
    try:
        slips = service.get_payable_slips(entry_id, slip_ids)
    except PayrollEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    except SalarySlipNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Salary slips not found: {e.slip_id}")
    except SlipStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    slip_map = {s.id: s for s in slips}

    # Get payroll entry for reference
    entry = service.get_payroll_entry(entry_id)

    settings = get_payment_settings()
    provider_value = (payload.provider or settings.default_transfer_provider).lower()
    provider_enum = (
        GatewayProvider.FLUTTERWAVE
        if provider_value == GatewayProvider.FLUTTERWAVE.value
        else GatewayProvider.PAYSTACK
    )

    drafts = []
    for payout in payload.payouts:
        slip = slip_map[payout.salary_slip_id]
        amount = slip.net_pay or Decimal("0")
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Slip {slip.id} has no payable amount",
            )

        reference = generate_transfer_reference()
        transfer = Transfer(
            reference=reference,
            provider=provider_enum,
            transfer_type=TransferType.PAYROLL,
            amount=amount,
            currency=payload.currency or slip.currency or "NGN",
            status=TransferStatus.PENDING,
            recipient_account=payout.account_number,
            recipient_bank_code=payout.bank_code,
            recipient_name=payout.account_name or slip.employee_name or slip.employee,
            reason=f"Payroll {entry.id} - {slip.employee}",
            employee_id=slip.employee_id,
            salary_slip_id=slip.id,
            payroll_run_id=entry.id,
            company=slip.company,
            created_by_id=current_user.id if current_user else None,
        )
        db.add(transfer)
        drafts.append({"reference": reference, "salary_slip_id": slip.id})

        # Mark slip as submitted for payment
        if slip.status == SalarySlipStatus.DRAFT:
            slip.status = SalarySlipStatus.SUBMITTED

    db.commit()

    return {
        "count": len(drafts),
        "drafts": drafts,
    }


# =============================================================================
# PAYROLL REGISTER EXPORT
# =============================================================================

@router.get("/salary-slips/register/export", dependencies=[Depends(Require("hr:read"))])
def export_payroll_register(
    start_date: date,
    end_date: date,
    company: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Any:
    """
    Export payroll register as CSV for a date range.

    Returns a CSV with all salary slip details for the period.
    """
    service = PayrollService(db, current_user)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = SalarySlipStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = SalarySlipFilters(
        from_date=start_date,
        to_date=end_date,
        company=company,
        status=status_enum,
    )
    # Get all for export (no pagination limit)
    result = service.list_salary_slips(filters, PaginationParams(offset=0, limit=10000))
    slips = result.items

    # Build CSV rows
    headers = [
        "Employee ID", "Employee", "Employee Name", "Department", "Designation",
        "Period Start", "Period End", "Gross Pay", "Total Deduction", "Net Pay",
        "Status", "Payment Reference", "Paid At", "Company"
    ]
    rows: List[List[Any]] = [headers]

    for slip in slips:
        rows.append([
            slip.employee_id or "",
            slip.employee,
            slip.employee_name or "",
            slip.department or "",
            slip.designation or "",
            slip.start_date.isoformat() if slip.start_date else "",
            slip.end_date.isoformat() if slip.end_date else "",
            float(slip.gross_pay) if slip.gross_pay else 0,
            float(slip.total_deduction) if slip.total_deduction else 0,
            float(slip.net_pay) if slip.net_pay else 0,
            slip.status.value if slip.status else "",
            slip.payment_reference or "",
            slip.paid_at.isoformat() if slip.paid_at else "",
            slip.company or "",
        ])

    # Log export audit
    audit = AuditLogger(db)
    audit.log_export(
        doctype="salary_slip",
        document_id=0,
        user_id=current_user.id if current_user else None,
        document_name=f"Payroll Register {start_date} to {end_date}",
        remarks=f"Exported {len(slips)} salary slips",
    )

    return csv_response(rows, f"payroll_register_{start_date}_{end_date}.csv")
