"""Tax: Tax categories, templates, withholding, rules, and tax filing."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting_ext import AuditAction

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# TAX CATEGORIES
# =============================================================================

@router.get("/tax-categories", dependencies=[Depends(Require("accounting:read"))])
def get_tax_categories(
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax categories list.

    Args:
        include_disabled: Include disabled categories

    Returns:
        List of tax categories
    """
    from app.models.tax import TaxCategory

    query = db.query(TaxCategory)
    if not include_disabled:
        query = query.filter(TaxCategory.disabled == False)

    categories = query.order_by(TaxCategory.category_name).all()

    return {
        "total": len(categories),
        "categories": [
            {
                "id": cat.id,
                "erpnext_id": cat.erpnext_id,
                "name": cat.category_name,
                "title": cat.title,
                "is_inter_state": cat.is_inter_state,
                "is_reverse_charge": cat.is_reverse_charge,
                "disabled": cat.disabled,
            }
            for cat in categories
        ],
    }


# =============================================================================
# SALES TAX TEMPLATES
# =============================================================================

@router.get("/sales-tax-templates", dependencies=[Depends(Require("accounting:read"))])
def get_sales_tax_templates(
    company: Optional[str] = None,
    tax_category: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get sales tax templates list.

    Args:
        company: Filter by company
        tax_category: Filter by tax category
        include_disabled: Include disabled templates

    Returns:
        List of sales tax templates
    """
    from app.models.tax import SalesTaxTemplate

    query = db.query(SalesTaxTemplate)
    if company:
        query = query.filter(SalesTaxTemplate.company == company)
    if tax_category:
        query = query.filter(SalesTaxTemplate.tax_category == tax_category)
    if not include_disabled:
        query = query.filter(SalesTaxTemplate.disabled == False)

    templates = query.order_by(SalesTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "tax_category": t.tax_category,
                "is_default": t.is_default,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/sales-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
def get_sales_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get sales tax template with all tax line details.

    Args:
        template_id: Template ID

    Returns:
        Template details with tax lines
    """
    from app.models.tax import SalesTaxTemplate, SalesTaxTemplateDetail

    template = db.query(SalesTaxTemplate).filter(SalesTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Sales tax template not found")

    details = db.query(SalesTaxTemplateDetail).filter(
        SalesTaxTemplateDetail.template_id == template_id
    ).order_by(SalesTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "tax_category": template.tax_category,
        "is_default": template.is_default,
        "disabled": template.disabled,
        "taxes": [
            {
                "charge_type": d.charge_type,
                "account_head": d.account_head,
                "description": d.description,
                "rate": float(d.rate),
                "tax_amount": float(d.tax_amount),
                "cost_center": d.cost_center,
                "included_in_print_rate": d.included_in_print_rate,
            }
            for d in details
        ],
    }


# =============================================================================
# PURCHASE TAX TEMPLATES
# =============================================================================

@router.get("/purchase-tax-templates", dependencies=[Depends(Require("accounting:read"))])
def get_purchase_tax_templates(
    company: Optional[str] = None,
    tax_category: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase tax templates list.

    Args:
        company: Filter by company
        tax_category: Filter by tax category
        include_disabled: Include disabled templates

    Returns:
        List of purchase tax templates
    """
    from app.models.tax import PurchaseTaxTemplate

    query = db.query(PurchaseTaxTemplate)
    if company:
        query = query.filter(PurchaseTaxTemplate.company == company)
    if tax_category:
        query = query.filter(PurchaseTaxTemplate.tax_category == tax_category)
    if not include_disabled:
        query = query.filter(PurchaseTaxTemplate.disabled == False)

    templates = query.order_by(PurchaseTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "tax_category": t.tax_category,
                "is_default": t.is_default,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/purchase-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
def get_purchase_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase tax template with all tax line details.

    Args:
        template_id: Template ID

    Returns:
        Template details with tax lines
    """
    from app.models.tax import PurchaseTaxTemplate, PurchaseTaxTemplateDetail

    template = db.query(PurchaseTaxTemplate).filter(PurchaseTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Purchase tax template not found")

    details = db.query(PurchaseTaxTemplateDetail).filter(
        PurchaseTaxTemplateDetail.template_id == template_id
    ).order_by(PurchaseTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "tax_category": template.tax_category,
        "is_default": template.is_default,
        "disabled": template.disabled,
        "taxes": [
            {
                "charge_type": d.charge_type,
                "account_head": d.account_head,
                "description": d.description,
                "rate": float(d.rate),
                "tax_amount": float(d.tax_amount),
                "cost_center": d.cost_center,
                "add_deduct_tax": d.add_deduct_tax,
                "included_in_print_rate": d.included_in_print_rate,
            }
            for d in details
        ],
    }


# =============================================================================
# ITEM TAX TEMPLATES
# =============================================================================

@router.get("/item-tax-templates", dependencies=[Depends(Require("accounting:read"))])
def get_item_tax_templates(
    company: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get item tax templates list.

    Args:
        company: Filter by company
        include_disabled: Include disabled templates

    Returns:
        List of item tax templates
    """
    from app.models.tax import ItemTaxTemplate

    query = db.query(ItemTaxTemplate)
    if company:
        query = query.filter(ItemTaxTemplate.company == company)
    if not include_disabled:
        query = query.filter(ItemTaxTemplate.disabled == False)

    templates = query.order_by(ItemTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/item-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
def get_item_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get item tax template with all tax rate details.

    Args:
        template_id: Template ID

    Returns:
        Template details with tax rates
    """
    from app.models.tax import ItemTaxTemplate, ItemTaxTemplateDetail

    template = db.query(ItemTaxTemplate).filter(ItemTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Item tax template not found")

    details = db.query(ItemTaxTemplateDetail).filter(
        ItemTaxTemplateDetail.template_id == template_id
    ).order_by(ItemTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "disabled": template.disabled,
        "taxes": [
            {
                "tax_type": d.tax_type,
                "tax_rate": float(d.tax_rate),
            }
            for d in details
        ],
    }


# =============================================================================
# TAX WITHHOLDING CATEGORIES
# =============================================================================

@router.get("/tax-withholding-categories", dependencies=[Depends(Require("accounting:read"))])
def get_tax_withholding_categories(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax withholding categories list.

    Returns:
        List of tax withholding categories
    """
    from app.models.tax import TaxWithholdingCategory

    categories = db.query(TaxWithholdingCategory).order_by(TaxWithholdingCategory.category_name).all()

    return {
        "total": len(categories),
        "categories": [
            {
                "id": cat.id,
                "erpnext_id": cat.erpnext_id,
                "name": cat.category_name,
                "company": cat.company,
                "account": cat.account,
                "round_off_tax_amount": cat.round_off_tax_amount,
                "consider_party_ledger_amount": cat.consider_party_ledger_amount,
            }
            for cat in categories
        ],
    }


# =============================================================================
# TAX RULES
# =============================================================================

@router.get("/tax-rules", dependencies=[Depends(Require("accounting:read"))])
def get_tax_rules(
    tax_type: Optional[str] = None,
    tax_category: Optional[str] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax rules list.

    Args:
        tax_type: Filter by tax type
        tax_category: Filter by tax category
        company: Filter by company

    Returns:
        List of tax rules ordered by priority
    """
    from app.models.tax import TaxRule

    query = db.query(TaxRule)
    if tax_type:
        query = query.filter(TaxRule.tax_type == tax_type)
    if tax_category:
        query = query.filter(TaxRule.tax_category == tax_category)
    if company:
        query = query.filter(TaxRule.company == company)

    rules = query.order_by(TaxRule.priority.desc()).all()

    return {
        "total": len(rules),
        "rules": [
            {
                "id": r.id,
                "erpnext_id": r.erpnext_id,
                "name": r.rule_name,
                "tax_type": r.tax_type,
                "sales_tax_template": r.sales_tax_template,
                "purchase_tax_template": r.purchase_tax_template,
                "tax_category": r.tax_category,
                "customer": r.customer,
                "supplier": r.supplier,
                "customer_group": r.customer_group,
                "supplier_group": r.supplier_group,
                "billing_country": r.billing_country,
                "billing_state": r.billing_state,
                "shipping_country": r.shipping_country,
                "shipping_state": r.shipping_state,
                "item": r.item,
                "item_group": r.item_group,
                "company": r.company,
                "priority": r.priority,
                "from_date": r.from_date.isoformat() if r.from_date else None,
                "to_date": r.to_date.isoformat() if r.to_date else None,
            }
            for r in rules
        ],
    }


# =============================================================================
# TAX FILING PERIODS
# =============================================================================

@router.get("/tax/filing-periods", dependencies=[Depends(Require("accounting:read"))])
def list_tax_filing_periods(
    tax_type: Optional[str] = Query(None, description="Filter by tax type (vat, wht, cit, paye)"),
    status: Optional[str] = Query(None, description="Filter by status (open, filed, paid, closed)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax filing periods with optional filters.

    Args:
        tax_type: Filter by tax type
        status: Filter by filing status
        year: Filter by year
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated tax filing periods
    """
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    query = db.query(TaxFilingPeriod)

    if tax_type:
        try:
            tax_type_enum = TaxFilingType(tax_type.lower())
            query = query.filter(TaxFilingPeriod.tax_type == tax_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tax type: {tax_type}")

    if status:
        try:
            status_enum = TaxFilingStatus(status.lower())
            query = query.filter(TaxFilingPeriod.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if year:
        query = query.filter(func.extract('year', TaxFilingPeriod.period_start) == year)

    query = query.order_by(TaxFilingPeriod.due_date.desc())
    total, periods = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "periods": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "period_start": p.period_start.isoformat(),
                "period_end": p.period_end.isoformat(),
                "due_date": p.due_date.isoformat(),
                "status": p.status.value,
                "tax_base": float(p.tax_base),
                "tax_amount": float(p.tax_amount),
                "amount_paid": float(p.amount_paid),
                "outstanding": float(p.outstanding_amount),
                "is_overdue": p.is_overdue,
            }
            for p in periods
        ],
    }


@router.post("/tax/filing-periods", dependencies=[Depends(Require("books:admin"))])
def create_tax_filing_period(
    tax_type: str = Query(..., description="Tax type: vat, wht, cit, paye, other"),
    period_name: str = Query(..., description="Period name (e.g., 2024-Q1, 2024-01)"),
    period_start: str = Query(..., description="Period start date (YYYY-MM-DD)"),
    period_end: str = Query(..., description="Period end date (YYYY-MM-DD)"),
    due_date: str = Query(..., description="Filing due date (YYYY-MM-DD)"),
    tax_base: float = Query(0, description="Tax base amount"),
    tax_amount: float = Query(0, description="Tax amount due"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new tax filing period.

    Args:
        tax_type: Type of tax (vat, wht, cit, paye, other)
        period_name: Name of the period
        period_start: Period start date
        period_end: Period end date
        due_date: Filing due date
        tax_base: Tax base amount
        tax_amount: Tax amount due

    Returns:
        Created tax filing period info
    """
    from app.models.tax import TaxFilingPeriod, TaxFilingType
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        tax_type_enum = TaxFilingType(tax_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tax type: {tax_type}")

    period = TaxFilingPeriod(
        tax_type=tax_type_enum,
        period_name=period_name,
        period_start=parse_date(period_start, "period_start"),
        period_end=parse_date(period_end, "period_end"),
        due_date=parse_date(due_date, "due_date"),
        tax_base=Decimal(str(tax_base)),
        tax_amount=Decimal(str(tax_amount)),
        created_by_id=user.id,
    )
    db.add(period)
    db.flush()

    audit = AuditLogger(db)
    audit.log_create(
        doctype="tax_filing_period",
        document_id=period.id,
        user_id=user.id,
        document_name=f"{tax_type} {period_name}",
        new_values=serialize_for_audit(period),
    )
    db.commit()

    return {
        "message": "Tax filing period created",
        "id": period.id,
        "tax_type": period.tax_type.value,
        "period_name": period.period_name,
        "due_date": period.due_date.isoformat(),
    }


@router.get("/tax/filing-periods/{period_id}", dependencies=[Depends(Require("accounting:read"))])
def get_tax_filing_period(
    period_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax filing period details with payments.

    Args:
        period_id: Filing period ID

    Returns:
        Filing period details with payments
    """
    from app.models.tax import TaxFilingPeriod, TaxPayment

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    payments = db.query(TaxPayment).filter(
        TaxPayment.filing_period_id == period_id
    ).order_by(TaxPayment.payment_date.desc()).all()

    return {
        "id": period.id,
        "tax_type": period.tax_type.value,
        "period_name": period.period_name,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "due_date": period.due_date.isoformat(),
        "status": period.status.value,
        "tax_base": float(period.tax_base),
        "tax_amount": float(period.tax_amount),
        "amount_paid": float(period.amount_paid),
        "outstanding": float(period.outstanding_amount),
        "is_overdue": period.is_overdue,
        "filed_at": period.filed_at.isoformat() if period.filed_at else None,
        "filing_reference": period.filing_reference,
        "payments": [
            {
                "id": p.id,
                "payment_date": p.payment_date.isoformat(),
                "amount": float(p.amount),
                "payment_reference": p.payment_reference,
                "payment_method": p.payment_method,
            }
            for p in payments
        ],
    }


@router.post("/tax/filing-periods/{period_id}/file", dependencies=[Depends(Require("books:write"))])
def file_tax_period(
    period_id: int,
    filing_reference: Optional[str] = Query(None, description="Filing reference number"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Mark a tax filing period as filed.

    Args:
        period_id: Filing period ID
        filing_reference: Reference number from filing

    Returns:
        Filing status
    """
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus
    from app.services.audit_logger import AuditLogger

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    if period.status != TaxFilingStatus.OPEN:
        raise HTTPException(status_code=400, detail=f"Period is already {period.status.value}")

    old_status = period.status.value
    period.status = TaxFilingStatus.FILED
    period.filed_at = datetime.utcnow()
    period.filed_by_id = user.id
    period.filing_reference = filing_reference

    audit = AuditLogger(db)
    audit.log(
        doctype="tax_filing_period",
        document_id=period.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        document_name=f"{period.tax_type.value} {period.period_name}",
        old_values={"status": old_status},
        new_values={"status": "filed", "filing_reference": filing_reference},
    )
    db.commit()

    return {
        "message": "Tax period marked as filed",
        "id": period.id,
        "status": period.status.value,
        "filed_at": period.filed_at.isoformat(),
    }


@router.post("/tax/filing-periods/{period_id}/pay", dependencies=[Depends(Require("books:write"))])
def record_tax_payment(
    period_id: int,
    payment_date: str = Query(..., description="Payment date (YYYY-MM-DD)"),
    amount: float = Query(..., gt=0, description="Payment amount"),
    payment_reference: Optional[str] = Query(None, description="Payment reference"),
    payment_method: Optional[str] = Query(None, description="Payment method"),
    bank_account: Optional[str] = Query(None, description="Bank account used"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Record a tax payment for a filing period.

    Args:
        period_id: Filing period ID
        payment_date: Date of payment
        amount: Payment amount
        payment_reference: Reference number
        payment_method: Payment method used
        bank_account: Bank account used

    Returns:
        Payment confirmation
    """
    from app.models.tax import TaxFilingPeriod, TaxPayment, TaxFilingStatus
    from app.services.audit_logger import AuditLogger

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    payment = TaxPayment(
        filing_period_id=period_id,
        payment_date=parse_date(payment_date, "payment_date"),
        amount=Decimal(str(amount)),
        payment_reference=payment_reference,
        payment_method=payment_method,
        bank_account=bank_account,
        created_by_id=user.id,
    )
    db.add(payment)

    # Update period totals
    period.amount_paid += Decimal(str(amount))
    if period.amount_paid >= period.tax_amount:
        period.status = TaxFilingStatus.PAID

    audit = AuditLogger(db)
    audit.log(
        doctype="tax_payment",
        document_id=payment.id,
        action=AuditAction.CREATE,
        user_id=user.id,
        document_name=f"{period.tax_type.value} {period.period_name}",
        new_values={"amount": amount, "payment_reference": payment_reference},
        remarks=f"Payment for {period.period_name}",
    )
    db.commit()

    return {
        "message": "Tax payment recorded",
        "payment_id": payment.id,
        "amount": float(payment.amount),
        "period_status": period.status.value,
        "outstanding": float(period.outstanding_amount),
    }


# =============================================================================
# TAX DASHBOARD
# =============================================================================

@router.get("/tax/dashboard", dependencies=[Depends(Require("accounting:read"))])
def get_tax_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax obligations dashboard summary.

    Returns:
        Summary of tax obligations by type with upcoming and overdue filings
    """
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    today = date.today()

    # Get summary by tax type
    summary_by_type = {}
    for tax_type in TaxFilingType:
        open_periods = db.query(TaxFilingPeriod).filter(
            and_(
                TaxFilingPeriod.tax_type == tax_type,
                TaxFilingPeriod.status.in_([TaxFilingStatus.OPEN, TaxFilingStatus.FILED]),
            )
        ).all()

        total_outstanding = sum(p.outstanding_amount for p in open_periods)
        overdue_count = sum(1 for p in open_periods if p.is_overdue)

        if open_periods or total_outstanding > 0:
            summary_by_type[tax_type.value] = {
                "open_periods": len(open_periods),
                "total_outstanding": float(total_outstanding),
                "overdue_count": overdue_count,
            }

    # Get upcoming due dates
    upcoming = db.query(TaxFilingPeriod).filter(
        and_(
            TaxFilingPeriod.status == TaxFilingStatus.OPEN,
            TaxFilingPeriod.due_date >= today,
        )
    ).order_by(TaxFilingPeriod.due_date).limit(5).all()

    # Get overdue filings
    overdue = db.query(TaxFilingPeriod).filter(
        and_(
            TaxFilingPeriod.status == TaxFilingStatus.OPEN,
            TaxFilingPeriod.due_date < today,
        )
    ).order_by(TaxFilingPeriod.due_date).all()

    return {
        "as_of_date": today.isoformat(),
        "summary_by_type": summary_by_type,
        "total_outstanding": sum(s["total_outstanding"] for s in summary_by_type.values()),
        "total_overdue_count": sum(s["overdue_count"] for s in summary_by_type.values()),
        "upcoming_due": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "outstanding": float(p.outstanding_amount),
            }
            for p in upcoming
        ],
        "overdue": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "days_overdue": (today - p.due_date).days,
                "outstanding": float(p.outstanding_amount),
            }
            for p in overdue
        ],
    }
