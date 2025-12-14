"""Payment Terms: CRUD endpoints for payment terms management."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.payment_terms import PaymentTermsTemplate, PaymentTermsSchedule
from app.services.due_date_calculator import DueDateCalculator
from .helpers import paginate

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class PaymentScheduleCreate(BaseModel):
    """Schema for creating a payment schedule line."""
    credit_days: int = 0
    credit_months: int = 0
    day_of_month: Optional[int] = None
    payment_percentage: float = 100
    discount_percentage: float = 0
    discount_days: int = 0
    description: Optional[str] = None


class PaymentTermsCreate(BaseModel):
    """Schema for creating payment terms."""
    template_name: str
    description: Optional[str] = None
    company: Optional[str] = None
    schedules: List[PaymentScheduleCreate] = []


class PaymentTermsUpdate(BaseModel):
    """Schema for updating payment terms."""
    template_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    schedules: Optional[List[PaymentScheduleCreate]] = None


class DueDateCalculateRequest(BaseModel):
    """Schema for due date calculation request."""
    document_date: str
    payment_terms_id: Optional[int] = None
    credit_days: int = 0


class PaymentScheduleRequest(BaseModel):
    """Schema for payment schedule calculation request."""
    document_date: str
    total_amount: float
    payment_terms_id: int


# =============================================================================
# PAYMENT TERMS LIST & DETAIL
# =============================================================================

@router.get("/payment-terms", dependencies=[Depends(Require("accounting:read"))])
def list_payment_terms(
    is_active: Optional[bool] = None,
    company: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payment terms templates."""
    query = db.query(PaymentTermsTemplate)

    if is_active is not None:
        query = query.filter(PaymentTermsTemplate.is_active == is_active)

    if company:
        query = query.filter(PaymentTermsTemplate.company == company)

    query = query.order_by(PaymentTermsTemplate.template_name)
    total, terms = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "payment_terms": [
            {
                "id": t.id,
                "template_name": t.template_name,
                "description": t.description,
                "is_active": t.is_active,
                "schedule_count": len(t.schedules) if t.schedules else 0,
            }
            for t in terms
        ],
    }


@router.get("/payment-terms/{terms_id}", dependencies=[Depends(Require("accounting:read"))])
def get_payment_terms(
    terms_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payment terms detail with schedules."""
    terms = db.query(PaymentTermsTemplate).filter(
        PaymentTermsTemplate.id == terms_id
    ).first()
    if not terms:
        raise HTTPException(status_code=404, detail="Payment terms not found")

    return {
        "id": terms.id,
        "template_name": terms.template_name,
        "description": terms.description,
        "is_active": terms.is_active,
        "company": terms.company,
        "created_at": terms.created_at.isoformat() if terms.created_at else None,
        "schedules": [
            {
                "id": s.id,
                "credit_days": s.credit_days,
                "credit_months": s.credit_months,
                "day_of_month": s.day_of_month,
                "payment_percentage": float(s.payment_percentage),
                "discount_percentage": float(s.discount_percentage),
                "discount_days": s.discount_days,
                "description": s.description,
                "idx": s.idx,
            }
            for s in sorted(terms.schedules, key=lambda x: x.idx)
        ],
    }


# =============================================================================
# PAYMENT TERMS CRUD
# =============================================================================

@router.post("/payment-terms", dependencies=[Depends(Require("books:write"))])
def create_payment_terms(
    data: PaymentTermsCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create new payment terms."""
    # Check for duplicate
    existing = db.query(PaymentTermsTemplate).filter(
        PaymentTermsTemplate.template_name == data.template_name
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Payment terms '{data.template_name}' already exists"
        )

    # Validate schedules sum to 100%
    if data.schedules:
        total_pct = sum(s.payment_percentage for s in data.schedules)
        if abs(total_pct - 100) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Payment percentages must sum to 100%, got {total_pct}%"
            )

    terms = PaymentTermsTemplate(
        template_name=data.template_name,
        description=data.description,
        company=data.company,
        created_by_id=user.id,
    )
    db.add(terms)
    db.flush()

    # Add schedules
    for idx, sched in enumerate(data.schedules):
        schedule = PaymentTermsSchedule(
            template_id=terms.id,
            credit_days=sched.credit_days,
            credit_months=sched.credit_months,
            day_of_month=sched.day_of_month,
            payment_percentage=Decimal(str(sched.payment_percentage)),
            discount_percentage=Decimal(str(sched.discount_percentage)),
            discount_days=sched.discount_days,
            description=sched.description,
            idx=idx,
        )
        db.add(schedule)

    db.commit()
    db.refresh(terms)

    return {
        "message": "Payment terms created",
        "id": terms.id,
        "template_name": terms.template_name,
    }


@router.patch("/payment-terms/{terms_id}", dependencies=[Depends(Require("books:write"))])
def update_payment_terms(
    terms_id: int,
    data: PaymentTermsUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update payment terms."""
    terms = db.query(PaymentTermsTemplate).filter(
        PaymentTermsTemplate.id == terms_id
    ).first()
    if not terms:
        raise HTTPException(status_code=404, detail="Payment terms not found")

    if data.template_name is not None:
        # Check for duplicate
        existing = db.query(PaymentTermsTemplate).filter(
            PaymentTermsTemplate.template_name == data.template_name,
            PaymentTermsTemplate.id != terms_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Payment terms '{data.template_name}' already exists"
            )
        terms.template_name = data.template_name

    if data.description is not None:
        terms.description = data.description

    if data.is_active is not None:
        terms.is_active = data.is_active

    if data.schedules is not None:
        # Validate schedules sum to 100%
        if data.schedules:
            total_pct = sum(s.payment_percentage for s in data.schedules)
            if abs(total_pct - 100) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment percentages must sum to 100%, got {total_pct}%"
                )

        # Remove existing schedules
        db.query(PaymentTermsSchedule).filter(
            PaymentTermsSchedule.template_id == terms_id
        ).delete()

        # Add new schedules
        for idx, sched in enumerate(data.schedules):
            schedule = PaymentTermsSchedule(
                template_id=terms.id,
                credit_days=sched.credit_days,
                credit_months=sched.credit_months,
                day_of_month=sched.day_of_month,
                payment_percentage=Decimal(str(sched.payment_percentage)),
                discount_percentage=Decimal(str(sched.discount_percentage)),
                discount_days=sched.discount_days,
                description=sched.description,
                idx=idx,
            )
            db.add(schedule)

    db.commit()

    return {
        "message": "Payment terms updated",
        "id": terms.id,
    }


# =============================================================================
# DUE DATE CALCULATION
# =============================================================================

@router.post("/payment-terms/calculate-due-date", dependencies=[Depends(Require("accounting:read"))])
def calculate_due_date(
    data: DueDateCalculateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate due date from document date and payment terms."""
    calculator = DueDateCalculator(db)

    doc_date = date.fromisoformat(data.document_date)
    result = calculator.calculate_due_date(
        doc_date=doc_date,
        payment_terms_id=data.payment_terms_id,
        credit_days=data.credit_days,
    )

    return {
        "due_date": result.due_date.isoformat(),
        "payment_terms_name": result.payment_terms_name,
    }


@router.post("/payment-terms/calculate-schedule", dependencies=[Depends(Require("accounting:read"))])
def calculate_payment_schedule(
    data: PaymentScheduleRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate full payment schedule from document date and payment terms."""
    calculator = DueDateCalculator(db)

    doc_date = date.fromisoformat(data.document_date)
    schedule = calculator.calculate_payment_schedule(
        doc_date=doc_date,
        total_amount=Decimal(str(data.total_amount)),
        payment_terms_id=data.payment_terms_id,
    )

    return {
        "schedule": [
            {
                "due_date": item.due_date.isoformat(),
                "percentage": float(item.percentage),
                "amount": float(item.amount),
                "discount_percentage": float(item.discount_percentage),
                "discount_amount": float(item.discount_amount),
                "discount_deadline": item.discount_deadline.isoformat() if item.discount_deadline else None,
            }
            for item in schedule
        ],
    }
