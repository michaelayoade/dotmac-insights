"""Purchasing API endpoints for vendor management, bills, and expenses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, extract
from typing import Dict, Any, Optional, List, TypedDict, cast
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.models.accounting import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
    GLEntry,
    Account,
    AccountType,
)
from app.models.expense import Expense, ExpenseStatus
from app.models.document_lines import BillLine
from app.utils.company_context import get_company_context

router = APIRouter()


class AgingBucket(TypedDict):
    count: int
    total: float | Decimal
    invoices: List[Dict[str, Any]]


class PurchaseInvoiceCreateRequest(BaseModel):
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    company: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    posting_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    grand_total: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    currency: str = "NGN"
    status: Optional[str] = PurchaseInvoiceStatus.DRAFT.value
    docstatus: int = 0
    is_return: bool = False
    workflow_status: Optional[str] = None
    fiscal_period_id: Optional[int] = None
    journal_entry_id: Optional[int] = None

    @validator("grand_total", "outstanding_amount", "paid_amount", "tax_amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class PurchaseInvoiceUpdateRequest(BaseModel):
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    company: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    posting_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    grand_total: Optional[Decimal] = None
    outstanding_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    docstatus: Optional[int] = None
    is_return: Optional[bool] = None
    workflow_status: Optional[str] = None
    fiscal_period_id: Optional[int] = None
    journal_entry_id: Optional[int] = None

    @validator("grand_total", "outstanding_amount", "paid_amount", "tax_amount", pre=True)
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


class ExpenseCreateRequest(BaseModel):
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    erpnext_employee: Optional[str] = None
    project_id: Optional[int] = None
    erpnext_project: Optional[str] = None
    ticket_id: Optional[int] = None
    task_id: Optional[int] = None
    erpnext_task: Optional[str] = None
    expense_type: Optional[str] = None
    description: Optional[str] = None
    remark: Optional[str] = None
    total_claimed_amount: Decimal = Decimal("0")
    total_sanctioned_amount: Decimal = Decimal("0")
    total_amount_reimbursed: Decimal = Decimal("0")
    total_advance_amount: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    currency: str = "NGN"
    total_taxes_and_charges: Decimal = Decimal("0")
    category: Optional[str] = None
    cost_center: Optional[str] = None
    pop_id: Optional[int] = None
    company: Optional[str] = None
    payable_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    clearance_date: Optional[datetime] = None
    approval_status: Optional[str] = None
    expense_approver: Optional[str] = None
    status: Optional[str] = ExpenseStatus.DRAFT.value
    is_paid: bool = False
    docstatus: int = 0
    expense_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None

    @validator(
        "total_claimed_amount",
        "total_sanctioned_amount",
        "total_amount_reimbursed",
        "total_advance_amount",
        "amount",
        "total_taxes_and_charges",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class ExpenseUpdateRequest(BaseModel):
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    erpnext_employee: Optional[str] = None
    project_id: Optional[int] = None
    erpnext_project: Optional[str] = None
    ticket_id: Optional[int] = None
    task_id: Optional[int] = None
    erpnext_task: Optional[str] = None
    expense_type: Optional[str] = None
    description: Optional[str] = None
    remark: Optional[str] = None
    total_claimed_amount: Optional[Decimal] = None
    total_sanctioned_amount: Optional[Decimal] = None
    total_amount_reimbursed: Optional[Decimal] = None
    total_advance_amount: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    total_taxes_and_charges: Optional[Decimal] = None
    category: Optional[str] = None
    cost_center: Optional[str] = None
    pop_id: Optional[int] = None
    company: Optional[str] = None
    payable_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    clearance_date: Optional[datetime] = None
    approval_status: Optional[str] = None
    expense_approver: Optional[str] = None
    status: Optional[str] = None
    is_paid: Optional[bool] = None
    docstatus: Optional[int] = None
    expense_date: Optional[datetime] = None
    posting_date: Optional[datetime] = None

    @validator(
        "total_claimed_amount",
        "total_sanctioned_amount",
        "total_amount_reimbursed",
        "total_advance_amount",
        "amount",
        "total_taxes_and_charges",
        pre=True,
    )
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")


# ============= DASHBOARD =============

@router.get("/dashboard", dependencies=[Depends(Require("purchasing:read"))])
async def get_purchasing_dashboard(
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchasing/AP overview dashboard with key metrics.

    Returns:
        - Total AP outstanding
        - Bills pending payment
        - Top suppliers by spend
        - Overdue amounts
        - Payment trends
    """
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()

    # Total outstanding AP
    outstanding_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    total_outstanding = outstanding_query.scalar() or Decimal("0")

    # Bills count by status
    bills_by_status = db.query(
        PurchaseInvoice.status,
        func.count(PurchaseInvoice.id).label("count"),
        func.sum(PurchaseInvoice.grand_total).label("total"),
    ).group_by(PurchaseInvoice.status).all()

    status_breakdown = {
        row.status.value if row.status else "unknown": {
            "count": row.count,
            "total": float(row.total or 0),
        }
        for row in bills_by_status
    }

    # Overdue amounts
    overdue_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date < cutoff,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    total_overdue = overdue_query.scalar() or Decimal("0")

    # Top 5 suppliers by outstanding amount
    top_suppliers = db.query(
        PurchaseInvoice.supplier_name,
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        func.count(PurchaseInvoice.id).label("bill_count"),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
    ).group_by(
        PurchaseInvoice.supplier_name
    ).order_by(
        func.sum(PurchaseInvoice.outstanding_amount).desc()
    ).limit(5).all()

    # Bills due this week
    week_end = cutoff + timedelta(days=7)
    due_this_week = db.query(
        func.count(PurchaseInvoice.id),
        func.sum(PurchaseInvoice.outstanding_amount),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date >= cutoff,
        PurchaseInvoice.due_date <= week_end,
    ).first()

    # Supplier count
    supplier_count = db.query(func.count(Supplier.id)).filter(
        Supplier.disabled == False
    ).scalar() or 0

    due_count = 0
    due_total = Decimal("0")
    if due_this_week is not None:
        due_count = int(due_this_week[0] or 0)
        due_total = Decimal(due_this_week[1] or 0)

    return {
        "as_of_date": cutoff.isoformat(),
        "total_outstanding": float(total_outstanding),
        "total_overdue": float(total_overdue),
        "overdue_percentage": round(float(total_overdue / total_outstanding * 100), 1) if total_outstanding > 0 else 0,
        "supplier_count": supplier_count,
        "status_breakdown": status_breakdown,
        "due_this_week": {
            "count": due_count,
            "total": float(due_total),
        },
        "top_suppliers": [
            {
                "name": row.supplier_name,
                "outstanding": float(row.outstanding),
                "bill_count": row.bill_count,
            }
            for row in top_suppliers
        ],
    }


# ============= BILLS =============

@router.get("/bills", dependencies=[Depends(Require("purchasing:read"))])
async def get_bills(
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    overdue_only: bool = False,
    sort_by: str = Query(default="posting_date", regex="^(posting_date|due_date|grand_total|supplier_name)$"),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$"),
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get vendor bills (purchase invoices) with filtering and pagination."""
    query = db.query(PurchaseInvoice)

    if status:
        try:
            status_enum = PurchaseInvoiceStatus(status.lower())
            query = query.filter(PurchaseInvoice.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if supplier:
        query = query.filter(
            or_(
                PurchaseInvoice.supplier.ilike(f"%{supplier}%"),
                PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"),
            )
        )

    if start_date:
        query = query.filter(PurchaseInvoice.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(PurchaseInvoice.posting_date <= _parse_date(end_date, "end_date"))

    if min_amount is not None:
        query = query.filter(PurchaseInvoice.grand_total >= min_amount)

    if max_amount is not None:
        query = query.filter(PurchaseInvoice.grand_total <= max_amount)

    if overdue_only:
        query = query.filter(
            PurchaseInvoice.due_date < date.today(),
            PurchaseInvoice.outstanding_amount > 0,
        )

    total = query.count()

    # Sorting
    sort_column = getattr(PurchaseInvoice, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()

    bills = query.order_by(sort_column).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "bills": [
            {
                "id": b.id,
                "erpnext_id": b.erpnext_id,
                "supplier": b.supplier,
                "supplier_name": b.supplier_name,
                "posting_date": b.posting_date.isoformat() if b.posting_date else None,
                "due_date": b.due_date.isoformat() if b.due_date else None,
                "grand_total": float(b.grand_total),
                "outstanding_amount": float(b.outstanding_amount),
                "status": b.status.value if b.status else None,
                "currency": b.currency,
                "is_overdue": b.due_date.date() < date.today() if b.due_date else False,
                "days_overdue": (date.today() - b.due_date.date()).days if b.due_date and b.due_date.date() < date.today() else 0,
            }
            for b in bills
        ],
    }


@router.get("/bills/{bill_id}", dependencies=[Depends(Require("purchasing:read"))])
async def get_bill_detail(
    bill_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed information for a specific bill with line items and GL entries."""
    bill = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == bill_id).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Get bill line items
    bill_lines = db.query(BillLine).filter(
        BillLine.purchase_invoice_id == bill.id
    ).order_by(BillLine.idx).all()

    # Get related GL entries
    gl_entries = db.query(GLEntry).filter(
        GLEntry.voucher_no == bill.erpnext_id,
        GLEntry.voucher_type == "Purchase Invoice",
    ).all()

    return {
        "id": bill.id,
        "erpnext_id": bill.erpnext_id,
        "supplier": bill.supplier,
        "supplier_name": bill.supplier_name,
        "posting_date": bill.posting_date.isoformat() if bill.posting_date else None,
        "due_date": bill.due_date.isoformat() if bill.due_date else None,
        "grand_total": float(bill.grand_total),
        "net_total": float(bill.grand_total - bill.tax_amount) if bill.tax_amount else float(bill.grand_total),
        "total_taxes_and_charges": float(bill.tax_amount or 0),
        "outstanding_amount": float(bill.outstanding_amount),
        "status": bill.status.value if bill.status else None,
        "currency": bill.currency,
        "company": bill.company,
        "cost_center": getattr(bill, "cost_center", None),
        "remarks": getattr(bill, "remarks", None),
        "is_overdue": bill.due_date.date() < date.today() if bill.due_date else False,
        "items": [
            {
                "id": line.id,
                "idx": line.idx,
                "item_code": line.item_code,
                "item_name": line.item_name,
                "description": line.description,
                "quantity": float(line.quantity),
                "rate": float(line.rate),
                "uom": line.uom,
                "amount": float(line.amount),
                "discount_percentage": float(line.discount_percentage),
                "discount_amount": float(line.discount_amount),
                "net_amount": float(line.net_amount),
                "tax_rate": float(line.tax_rate),
                "tax_amount": float(line.tax_amount),
                "account": line.account,
                "cost_center": line.cost_center,
                "expense_type": line.expense_type,
                "purchase_order_id": line.purchase_order_id,
            }
            for line in bill_lines
        ],
        "gl_entries": [
            {
                "id": e.id,
                "account": e.account,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "cost_center": e.cost_center,
            }
            for e in gl_entries
        ],
    }


@router.post("/bills", dependencies=[Depends(Require("purchasing:write"))])
async def create_bill(
    payload: PurchaseInvoiceCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a purchase invoice locally."""
    if payload.supplier_id:
        supplier_exists = db.query(Supplier.id).filter(Supplier.id == payload.supplier_id).first()
        if not supplier_exists:
            raise HTTPException(status_code=400, detail=f"Supplier {payload.supplier_id} not found")

    status_enum = None
    if payload.status:
        try:
            status_enum = PurchaseInvoiceStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    bill = PurchaseInvoice(
        bill_number=payload.bill_number,
        supplier=payload.supplier,
        supplier_name=payload.supplier_name,
        supplier_id=payload.supplier_id,
        company=payload.company or get_company_context(allow_null=True),
        supplier_tax_id=payload.supplier_tax_id,
        supplier_address=payload.supplier_address,
        posting_date=payload.posting_date,
        due_date=payload.due_date,
        grand_total=payload.grand_total,
        outstanding_amount=payload.outstanding_amount,
        paid_amount=payload.paid_amount,
        tax_amount=payload.tax_amount,
        currency=payload.currency,
        status=status_enum or PurchaseInvoiceStatus.DRAFT,
        docstatus=payload.docstatus,
        is_return=payload.is_return,
        workflow_status=payload.workflow_status,
        fiscal_period_id=payload.fiscal_period_id,
        journal_entry_id=payload.journal_entry_id,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return {"id": bill.id}


@router.patch("/bills/{bill_id}", dependencies=[Depends(Require("purchasing:write"))])
async def update_bill(
    bill_id: int,
    payload: PurchaseInvoiceUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a purchase invoice locally."""
    bill = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "supplier_id" in update_data and update_data["supplier_id"]:
        supplier_exists = db.query(Supplier.id).filter(Supplier.id == update_data["supplier_id"]).first()
        if not supplier_exists:
            raise HTTPException(status_code=400, detail=f"Supplier {update_data['supplier_id']} not found")
    if "status" in update_data and update_data["status"]:
        try:
            update_data["status"] = PurchaseInvoiceStatus(update_data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    for key, value in update_data.items():
        setattr(bill, key, value)

    db.commit()
    db.refresh(bill)
    return {"id": bill.id}


@router.delete("/bills/{bill_id}", dependencies=[Depends(Require("purchasing:write"))])
async def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a purchase invoice."""
    bill = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    db.delete(bill)
    db.commit()
    return {"status": "deleted", "bill_id": bill_id}


# ============= PAYMENTS =============

@router.get("/payments", dependencies=[Depends(Require("purchasing:read"))])
async def get_vendor_payments(
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get vendor payments from GL entries (Payment Entry voucher type)."""
    query = db.query(GLEntry).filter(
        GLEntry.voucher_type == "Payment Entry",
        GLEntry.party_type == "Supplier",
        GLEntry.is_cancelled == False,
    )

    if supplier:
        query = query.filter(GLEntry.party.ilike(f"%{supplier}%"))

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    total = query.count()
    payments = query.order_by(GLEntry.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "payments": [
            {
                "id": p.id,
                "posting_date": p.posting_date.isoformat() if p.posting_date else None,
                "supplier": p.party,
                "account": p.account,
                "debit": float(p.debit),
                "credit": float(p.credit),
                "amount": float(p.credit - p.debit),
                "voucher_no": p.voucher_no,
                "cost_center": p.cost_center,
            }
            for p in payments
        ],
    }


# ============= PURCHASE ORDERS =============

@router.get("/orders", dependencies=[Depends(Require("purchasing:read"))])
async def get_purchase_orders(
    supplier: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase orders.

    Note: This endpoint returns data from GL entries tagged as Purchase Order
    since the full PO model may not be synced.
    """
    # Get unique POs from GL entries
    query = db.query(
        GLEntry.voucher_no,
        GLEntry.party,
        func.min(GLEntry.posting_date).label("date"),
        func.sum(GLEntry.debit).label("total_debit"),
        func.sum(GLEntry.credit).label("total_credit"),
    ).filter(
        GLEntry.voucher_type == "Purchase Order",
        GLEntry.is_cancelled == False,
    )

    if supplier:
        query = query.filter(GLEntry.party.ilike(f"%{supplier}%"))

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    query = query.group_by(GLEntry.voucher_no, GLEntry.party)

    total = query.count()
    orders = query.order_by(func.min(GLEntry.posting_date).desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "orders": [
            {
                "order_no": o.voucher_no,
                "supplier": o.party,
                "date": o.date.isoformat() if o.date else None,
                "total": float(o.total_debit or 0),
            }
            for o in orders
        ],
    }


@router.get("/orders/{order_no}", dependencies=[Depends(Require("purchasing:read"))])
async def get_purchase_order_detail(
    order_no: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase order details with linked bills."""
    # Get GL entries for this PO
    gl_entries = db.query(GLEntry).filter(
        GLEntry.voucher_no == order_no,
        GLEntry.voucher_type == "Purchase Order",
        GLEntry.is_cancelled == False,
    ).all()

    if not gl_entries:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Get linked bills (Purchase Invoices referencing this PO)
    # This is a simplified approach - actual linking may vary
    supplier = gl_entries[0].party if gl_entries else None
    linked_bills = []

    if supplier:
        bills = db.query(PurchaseInvoice).filter(
            PurchaseInvoice.supplier == supplier,
        ).limit(10).all()
        linked_bills = [
            {
                "id": b.id,
                "bill_no": b.erpnext_id,
                "date": b.posting_date.isoformat() if b.posting_date else None,
                "amount": float(b.grand_total),
                "status": b.status.value if b.status else None,
            }
            for b in bills
        ]

    return {
        "order_no": order_no,
        "supplier": supplier,
        "date": gl_entries[0].posting_date.isoformat() if gl_entries and gl_entries[0].posting_date else None,
        "gl_entries": [
            {
                "account": e.account,
                "debit": float(e.debit),
                "credit": float(e.credit),
            }
            for e in gl_entries
        ],
        "linked_bills": linked_bills,
    }


# ============= DEBIT NOTES =============

@router.get("/debit-notes", dependencies=[Depends(Require("purchasing:read"))])
async def get_debit_notes(
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get debit notes (returns/credits from suppliers)."""
    query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.status == PurchaseInvoiceStatus.RETURN,
    )

    if supplier:
        query = query.filter(
            or_(
                PurchaseInvoice.supplier.ilike(f"%{supplier}%"),
                PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"),
            )
        )

    if start_date:
        query = query.filter(PurchaseInvoice.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(PurchaseInvoice.posting_date <= _parse_date(end_date, "end_date"))

    total = query.count()
    notes = query.order_by(PurchaseInvoice.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "debit_notes": [
            {
                "id": n.id,
                "erpnext_id": n.erpnext_id,
                "supplier": n.supplier_name or n.supplier,
                "posting_date": n.posting_date.isoformat() if n.posting_date else None,
                "grand_total": float(n.grand_total),
                "status": n.status.value if n.status else None,
        "return_against": getattr(n, "return_against", None),
            }
            for n in notes
        ],
    }


@router.get("/debit-notes/{note_id}", dependencies=[Depends(Require("purchasing:read"))])
async def get_debit_note_detail(
    note_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get debit note details."""
    note = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.id == note_id,
        PurchaseInvoice.status == PurchaseInvoiceStatus.RETURN,
    ).first()

    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")

    # Get original invoice if this is a return
    original_invoice = None
    if getattr(note, "return_against", None):
        original = db.query(PurchaseInvoice).filter(
            PurchaseInvoice.erpnext_id == getattr(note, "return_against", None)
        ).first()
        if original:
            original_invoice = {
                "id": original.id,
                "erpnext_id": original.erpnext_id,
                "grand_total": float(original.grand_total),
                "posting_date": original.posting_date.isoformat() if original.posting_date else None,
            }

    return {
        "id": note.id,
        "erpnext_id": note.erpnext_id,
        "supplier": note.supplier_name or note.supplier,
        "posting_date": note.posting_date.isoformat() if note.posting_date else None,
        "grand_total": float(note.grand_total),
        "status": note.status.value if note.status else None,
        "return_against": getattr(note, "return_against", None),
        "original_invoice": original_invoice,
        "remarks": getattr(note, "remarks", None),
    }


# ============= SUPPLIERS =============

@router.get("/suppliers", dependencies=[Depends(Require("purchasing:read"))])
async def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    country: Optional[str] = None,
    with_outstanding: bool = False,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get suppliers list with optional outstanding balance filter."""
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if search:
        query = query.filter(
            or_(
                Supplier.supplier_name.ilike(f"%{search}%"),
                Supplier.email_id.ilike(f"%{search}%"),
            )
        )

    if supplier_group:
        query = query.filter(Supplier.supplier_group == supplier_group)

    if country:
        query = query.filter(Supplier.country == country)

    total = query.count()
    suppliers = query.order_by(Supplier.supplier_name).offset(offset).limit(limit).all()

    # Calculate outstanding amounts for each supplier
    supplier_outstanding = {}
    if with_outstanding or True:  # Always include outstanding
        outstanding_query = db.query(
            PurchaseInvoice.supplier,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
        ).group_by(PurchaseInvoice.supplier).all()

        supplier_outstanding = {row.supplier: float(row.outstanding) for row in outstanding_query}

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "suppliers": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "name": s.supplier_name,
                "group": s.supplier_group,
                "type": s.supplier_type,
                "country": s.country,
                "currency": s.default_currency,
                "email": s.email_id,
                "mobile": s.mobile_no,
                "outstanding": supplier_outstanding.get(s.erpnext_id, 0),
            }
            for s in suppliers
        ],
    }


@router.get("/suppliers/groups", dependencies=[Depends(Require("purchasing:read"))])
async def get_supplier_groups(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get supplier group breakdown with counts and totals."""
    groups = db.query(
        Supplier.supplier_group,
        func.count(Supplier.id).label("count"),
    ).filter(
        Supplier.disabled == False,
    ).group_by(
        Supplier.supplier_group
    ).all()

    # Get outstanding by group
    outstanding_by_group = {}
    for group_name, _ in groups:
        if group_name:
            suppliers_in_group = db.query(Supplier.erpnext_id).filter(
                Supplier.supplier_group == group_name
            ).all()
            supplier_ids = [s[0] for s in suppliers_in_group]

            if supplier_ids:
                outstanding = db.query(
                    func.sum(PurchaseInvoice.outstanding_amount)
                ).filter(
                    PurchaseInvoice.supplier.in_(supplier_ids),
                    PurchaseInvoice.outstanding_amount > 0,
                ).scalar() or 0
                outstanding_by_group[group_name] = float(outstanding)

    return {
        "total_groups": len(groups),
        "groups": [
            {
                "name": g.supplier_group or "Ungrouped",
                "count": g.count,
                "outstanding": outstanding_by_group.get(g.supplier_group, 0),
            }
            for g in groups
        ],
    }


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(Require("purchasing:read"))])
async def get_supplier_detail(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get supplier details with bills and transaction history."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Get supplier's bills
    bills = db.query(PurchaseInvoice).filter(
        or_(
            PurchaseInvoice.supplier == supplier.erpnext_id,
            PurchaseInvoice.supplier_name == supplier.supplier_name,
        )
    ).order_by(PurchaseInvoice.posting_date.desc()).limit(20).all()

    # Calculate totals
    total_purchases = sum(float(b.grand_total) for b in bills)
    total_outstanding = sum(float(b.outstanding_amount) for b in bills if b.outstanding_amount > 0)

    return {
        "id": supplier.id,
        "erpnext_id": supplier.erpnext_id,
        "name": supplier.supplier_name,
        "group": supplier.supplier_group,
        "type": supplier.supplier_type,
        "country": supplier.country,
        "currency": supplier.default_currency,
        "email": supplier.email_id,
        "mobile": supplier.mobile_no,
        "tax_id": supplier.tax_id,
        "pan": getattr(supplier, "pan", None),
        "total_purchases": total_purchases,
        "total_outstanding": total_outstanding,
        "bill_count": len(bills),
        "recent_bills": [
            {
                "id": b.id,
                "bill_no": b.erpnext_id,
                "date": b.posting_date.isoformat() if b.posting_date else None,
                "amount": float(b.grand_total),
                "outstanding": float(b.outstanding_amount),
                "status": b.status.value if b.status else None,
            }
            for b in bills[:10]
        ],
    }


# ============= EXPENSES =============

@router.get("/expenses", dependencies=[Depends(Require("purchasing:read"))])
async def get_expenses(
    account: Optional[str] = None,
    cost_center: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense entries from GL (expense accounts)."""
    # Get expense account IDs
    expense_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EXPENSE,
        Account.disabled == False,
    ).all()
    expense_account_ids = [a[0] for a in expense_accounts]

    query = db.query(GLEntry).filter(
        GLEntry.account.in_(expense_account_ids),
        GLEntry.is_cancelled == False,
        GLEntry.debit > 0,
    )

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if cost_center:
        query = query.filter(GLEntry.cost_center == cost_center)

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    if min_amount is not None:
        query = query.filter(GLEntry.debit >= min_amount)

    total = query.count()
    expenses = query.order_by(GLEntry.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
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
            for e in expenses
        ],
    }


@router.get("/expenses/types", dependencies=[Depends(Require("purchasing:read"))])
async def get_expense_types(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense breakdown by account type."""
    # Get expense accounts
    expense_accounts = db.query(Account).filter(
        Account.root_type == AccountType.EXPENSE,
        Account.disabled == False,
    ).all()
    expense_account_map: Dict[Optional[str], Account] = {a.erpnext_id: a for a in expense_accounts}
    expense_account_ids = list(expense_account_map.keys())

    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("total_debit"),
        func.count(GLEntry.id).label("entry_count"),
    ).filter(
        GLEntry.account.in_(expense_account_ids),
        GLEntry.is_cancelled == False,
        GLEntry.debit > 0,
    )

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    query = query.group_by(GLEntry.account)
    results = query.order_by(func.sum(GLEntry.debit).desc()).all()

    total_expenses = sum(float(r.total_debit) for r in results)

    return {
        "total_expenses": total_expenses,
        "expense_types": [
            {
                "account": r.account,
                "account_name": (expense_account.account_name if expense_account else r.account),
                "total": float(r.total_debit),
                "entry_count": r.entry_count,
                "percentage": round(float(r.total_debit) / total_expenses * 100, 1) if total_expenses > 0 else 0,
            }
            for r in results
            for expense_account in [expense_account_map.get(r.account)]
        ],
    }


@router.get("/expenses/{expense_id}", dependencies=[Depends(Require("purchasing:read"))])
async def get_expense_detail(
    expense_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense entry details."""
    expense = db.query(GLEntry).filter(GLEntry.id == expense_id).first()

    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Get account details
    account = db.query(Account).filter(Account.erpnext_id == expense.account).first()

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


# ============= ERPNext EXPENSE CLAIMS =============

@router.get("/erpnext-expenses", dependencies=[Depends(Require("purchasing:read"))])
async def list_erpnext_expenses(
    employee_id: Optional[int] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List ERPNext expense claims stored locally."""
    query = db.query(Expense)
    if employee_id:
        query = query.filter(Expense.employee_id == employee_id)
    if project_id:
        query = query.filter(Expense.project_id == project_id)
    if status:
        try:
            status_enum = ExpenseStatus(status)
            query = query.filter(Expense.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    expenses = query.order_by(Expense.posting_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "expenses": [
            {
                "id": exp.id,
                "erpnext_id": exp.erpnext_id,
                "employee_id": exp.employee_id,
                "employee_name": exp.employee_name,
                "project_id": exp.project_id,
                "expense_type": exp.expense_type,
                "total_claimed_amount": float(exp.total_claimed_amount),
                "total_sanctioned_amount": float(exp.total_sanctioned_amount),
                "status": exp.status.value if exp.status else None,
                "currency": exp.currency,
                "posting_date": exp.posting_date.isoformat() if exp.posting_date else None,
            }
            for exp in expenses
        ],
    }


@router.get("/erpnext-expenses/{expense_id}", dependencies=[Depends(Require("purchasing:read"))])
async def get_erpnext_expense(
    expense_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an ERPNext expense claim by id."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {
        "id": expense.id,
        "erpnext_id": expense.erpnext_id,
        "employee_id": expense.employee_id,
        "employee_name": expense.employee_name,
        "project_id": expense.project_id,
        "expense_type": expense.expense_type,
        "description": expense.description,
        "remark": expense.remark,
        "total_claimed_amount": float(expense.total_claimed_amount),
        "total_sanctioned_amount": float(expense.total_sanctioned_amount),
        "total_amount_reimbursed": float(expense.total_amount_reimbursed),
        "total_advance_amount": float(expense.total_advance_amount),
        "amount": float(expense.amount),
        "currency": expense.currency,
        "status": expense.status.value if expense.status else None,
        "is_paid": expense.is_paid,
        "posting_date": expense.posting_date.isoformat() if expense.posting_date else None,
    }


@router.post("/erpnext-expenses", dependencies=[Depends(Require("purchasing:write"))])
async def create_erpnext_expense(
    payload: ExpenseCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an ERPNext expense claim locally."""
    status_enum = None
    if payload.status:
        try:
            status_enum = ExpenseStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    expense = Expense(
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        erpnext_employee=payload.erpnext_employee,
        project_id=payload.project_id,
        erpnext_project=payload.erpnext_project,
        ticket_id=payload.ticket_id,
        task_id=payload.task_id,
        erpnext_task=payload.erpnext_task,
        expense_type=payload.expense_type,
        description=payload.description,
        remark=payload.remark,
        total_claimed_amount=payload.total_claimed_amount,
        total_sanctioned_amount=payload.total_sanctioned_amount,
        total_amount_reimbursed=payload.total_amount_reimbursed,
        total_advance_amount=payload.total_advance_amount,
        amount=payload.amount,
        currency=payload.currency,
        total_taxes_and_charges=payload.total_taxes_and_charges,
        category=payload.category,
        cost_center=payload.cost_center,
        pop_id=payload.pop_id,
        company=payload.company,
        payable_account=payload.payable_account,
        mode_of_payment=payload.mode_of_payment,
        clearance_date=payload.clearance_date,
        approval_status=payload.approval_status,
        expense_approver=payload.expense_approver,
        status=status_enum or ExpenseStatus.DRAFT,
        is_paid=payload.is_paid,
        docstatus=payload.docstatus,
        expense_date=payload.expense_date,
        posting_date=payload.posting_date,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return {"id": expense.id}


@router.patch("/erpnext-expenses/{expense_id}", dependencies=[Depends(Require("purchasing:write"))])
async def update_erpnext_expense(
    expense_id: int,
    payload: ExpenseUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an ERPNext expense claim locally."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"]:
        try:
            update_data["status"] = ExpenseStatus(update_data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    for key, value in update_data.items():
        setattr(expense, key, value)

    db.commit()
    db.refresh(expense)
    return {"id": expense.id}


@router.delete("/erpnext-expenses/{expense_id}", dependencies=[Depends(Require("purchasing:write"))])
async def delete_erpnext_expense(
    expense_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an ERPNext expense claim."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()
    return {"status": "deleted", "expense_id": expense_id}


# ============= AP AGING =============

@router.get("/aging", dependencies=[Depends(Require("purchasing:read"))])
async def get_ap_aging(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts payable aging buckets."""
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()

    query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )

    if supplier:
        query = query.filter(
            or_(
                PurchaseInvoice.supplier.ilike(f"%{supplier}%"),
                PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"),
            )
        )

    if currency:
        query = query.filter(PurchaseInvoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets: Dict[str, AgingBucket] = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else cutoff)
        days_overdue = (cutoff - due).days if cutoff > due else 0

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        bucket_data = buckets[bucket]
        bucket_data["count"] += 1
        bucket_total = cast(Decimal, bucket_data["total"])
        bucket_data["total"] = bucket_total + (inv.outstanding_amount or Decimal("0"))
        bucket_data["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.erpnext_id,
            "supplier": inv.supplier_name or inv.supplier,
            "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "grand_total": float(inv.grand_total),
            "outstanding": float(inv.outstanding_amount),
            "days_overdue": days_overdue,
        })

    # Convert totals to float
    for bucket_data in buckets.values():
        bucket_data["total"] = float(bucket_data["total"])

    total_payable = sum(b["total"] for b in buckets.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_payable": total_payable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets,
    }


# ============= ANALYTICS =============

@router.get("/analytics/by-supplier", dependencies=[Depends(Require("purchasing:read"))])
async def get_purchases_by_supplier(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchases breakdown by supplier."""
    query = db.query(
        PurchaseInvoice.supplier_name,
        func.count(PurchaseInvoice.id).label("bill_count"),
        func.sum(PurchaseInvoice.grand_total).label("total_purchases"),
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
    ).filter(
        PurchaseInvoice.status != PurchaseInvoiceStatus.RETURN,
    )

    if start_date:
        query = query.filter(PurchaseInvoice.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(PurchaseInvoice.posting_date <= _parse_date(end_date, "end_date"))

    query = query.group_by(PurchaseInvoice.supplier_name)
    results = query.order_by(func.sum(PurchaseInvoice.grand_total).desc()).limit(limit).all()

    total = sum(float(r.total_purchases or 0) for r in results)

    return {
        "total": total,
        "suppliers": [
            {
                "name": r.supplier_name,
                "bill_count": r.bill_count,
                "total_purchases": float(r.total_purchases or 0),
                "outstanding": float(r.outstanding or 0),
                "percentage": round(float(r.total_purchases or 0) / total * 100, 1) if total > 0 else 0,
            }
            for r in results
        ],
    }


@router.get("/analytics/by-cost-center", dependencies=[Depends(Require("purchasing:read"))])
async def get_expenses_by_cost_center(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expenses breakdown by cost center."""
    # Get expense account IDs
    expense_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EXPENSE,
    ).all()
    expense_account_ids = [a[0] for a in expense_accounts]

    query = db.query(
        GLEntry.cost_center,
        func.sum(GLEntry.debit).label("total"),
        func.count(GLEntry.id).label("entry_count"),
    ).filter(
        GLEntry.account.in_(expense_account_ids),
        GLEntry.is_cancelled == False,
        GLEntry.debit > 0,
        GLEntry.cost_center.isnot(None),
    )

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    query = query.group_by(GLEntry.cost_center)
    results = query.order_by(func.sum(GLEntry.debit).desc()).all()

    total = sum(float(r.total or 0) for r in results)

    return {
        "total": total,
        "cost_centers": [
            {
                "name": r.cost_center or "Unassigned",
                "total": float(r.total or 0),
                "entry_count": r.entry_count,
                "percentage": round(float(r.total or 0) / total * 100, 1) if total > 0 else 0,
            }
            for r in results
        ],
    }


@router.get("/analytics/expense-trend", dependencies=[Depends(Require("purchasing:read"))])
async def get_expense_trend(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = Query(default="month", regex="^(day|week|month)$"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense trend over time."""
    # Get expense account IDs
    expense_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EXPENSE,
    ).all()
    expense_account_ids = [a[0] for a in expense_accounts]

    # Determine date grouping
    if granularity == "day":
        date_trunc = func.date(GLEntry.posting_date)
    elif granularity == "week":
        date_trunc = func.date(func.date_trunc('week', GLEntry.posting_date))
    else:  # month
        date_trunc = func.date(func.date_trunc('month', GLEntry.posting_date))

    query = db.query(
        date_trunc.label("period"),
        func.sum(GLEntry.debit).label("total"),
        func.count(GLEntry.id).label("entry_count"),
    ).filter(
        GLEntry.account.in_(expense_account_ids),
        GLEntry.is_cancelled == False,
        GLEntry.debit > 0,
    )

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    query = query.group_by(date_trunc).order_by(date_trunc)
    results = query.all()

    return {
        "granularity": granularity,
        "trend": [
            {
                "period": r.period.isoformat() if r.period else None,
                "total": float(r.total or 0),
                "entry_count": r.entry_count,
            }
            for r in results
        ],
    }
