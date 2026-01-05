"""Payment Terms: CRUD endpoints for payment terms management."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.services.accounting import PaymentTermsService
from app.services.accounting.payment_terms_types import (
    PaymentTermsFilters,
    PaymentTermsCreateData,
    PaymentTermsUpdateData,
    ScheduleData,
)
from app.services.due_date_calculator import DueDateCalculator
from app.services.errors import NotFoundError, ValidationError as ServiceValidationError
from app.services.types import PaginationParams

router = APIRouter()


def get_payment_terms_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> PaymentTermsService:
    """Dependency to get a PaymentTermsService instance."""
    return PaymentTermsService(db, principal)


# PYDANTIC SCHEMAS

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


# PAYMENT TERMS LIST & DETAIL

@router.get("/payment-terms", dependencies=[Depends(Require("accounting:read"))])
def list_payment_terms(
    is_active: Optional[bool] = None,
    company: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: PaymentTermsService = Depends(get_payment_terms_service),
) -> Dict[str, Any]:
    """List payment terms templates."""
    filters = PaymentTermsFilters(is_active=is_active, company=company)
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_payment_terms(filters, pagination)

    return {
        "total": result.total,
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
            for t in result.items
        ],
    }


@router.get("/payment-terms/{terms_id}", dependencies=[Depends(Require("accounting:read"))])
def get_payment_terms(
    terms_id: int,
    service: PaymentTermsService = Depends(get_payment_terms_service),
) -> Dict[str, Any]:
    """Get payment terms detail with schedules."""
    try:
        terms = service.get_payment_terms(terms_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

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


# PAYMENT TERMS CRUD

def _convert_schedule(sched: PaymentScheduleCreate) -> ScheduleData:
    """Convert Pydantic schedule to service dataclass."""
    return ScheduleData(
        credit_days=sched.credit_days,
        credit_months=sched.credit_months,
        day_of_month=sched.day_of_month,
        payment_percentage=Decimal(str(sched.payment_percentage)),
        discount_percentage=Decimal(str(sched.discount_percentage)),
        discount_days=sched.discount_days,
        description=sched.description,
    )


@router.post("/payment-terms", dependencies=[Depends(Require("books:write"))])
def create_payment_terms(
    data: PaymentTermsCreate,
    db: Session = Depends(get_db),
    service: PaymentTermsService = Depends(get_payment_terms_service),
) -> Dict[str, Any]:
    """Create new payment terms."""
    try:
        create_data = PaymentTermsCreateData(
            template_name=data.template_name,
            description=data.description,
            company=data.company,
            schedules=[_convert_schedule(s) for s in data.schedules],
        )
        terms = service.create_payment_terms(create_data)
        db.commit()
        db.refresh(terms)

        return {
            "message": "Payment terms created",
            "id": terms.id,
            "template_name": terms.template_name,
        }
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


@router.patch("/payment-terms/{terms_id}", dependencies=[Depends(Require("books:write"))])
def update_payment_terms(
    terms_id: int,
    data: PaymentTermsUpdate,
    db: Session = Depends(get_db),
    service: PaymentTermsService = Depends(get_payment_terms_service),
) -> Dict[str, Any]:
    """Update payment terms."""
    try:
        update_data = PaymentTermsUpdateData(
            template_name=data.template_name,
            description=data.description,
            is_active=data.is_active,
            schedules=[_convert_schedule(s) for s in data.schedules] if data.schedules is not None else None,
        )
        terms = service.update_payment_terms(terms_id, update_data)
        db.commit()

        return {
            "message": "Payment terms updated",
            "id": terms.id,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


# DUE DATE CALCULATION

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
