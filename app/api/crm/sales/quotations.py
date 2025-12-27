"""
Quotations API

Manages quotations/proposals within the CRM module.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.sales import Quotation, QuotationStatus
from app.models.contact import Contact

router = APIRouter(prefix="/quotations", tags=["crm-sales-quotations"])


# =============================================================================
# SCHEMAS
# =============================================================================

class QuotationBase(BaseModel):
    """Base schema for quotations."""
    contact_id: Optional[int] = None
    customer_name: Optional[str] = None
    quotation_date: Optional[date] = None
    valid_till: Optional[date] = None
    currency: str = "NGN"
    total_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    notes: Optional[str] = None


class QuotationCreate(QuotationBase):
    """Schema for creating a quotation."""
    pass


class QuotationUpdate(BaseModel):
    """Schema for updating a quotation."""
    contact_id: Optional[int] = None
    customer_name: Optional[str] = None
    quotation_date: Optional[date] = None
    valid_till: Optional[date] = None
    status: Optional[str] = None
    total_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None
    notes: Optional[str] = None


class QuotationResponse(BaseModel):
    """Schema for quotation response."""
    id: int
    erpnext_id: Optional[str]
    contact_id: Optional[int]
    customer_name: Optional[str]
    status: str
    quotation_date: Optional[date]
    valid_till: Optional[date]
    currency: str
    total_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_status(status: Optional[str]) -> Optional[QuotationStatus]:
    """Parse status string to enum."""
    if status is None:
        return None
    try:
        return QuotationStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status}. Allowed: {', '.join(s.value for s in QuotationStatus)}",
        )


def _serialize_quotation(quote: Quotation) -> Dict[str, Any]:
    """Serialize a quotation to dict."""
    return {
        "id": quote.id,
        "erpnext_id": quote.erpnext_id,
        "contact_id": quote.contact_id,
        "customer_name": quote.customer_name,
        "status": quote.status.value if quote.status else None,
        "quotation_date": quote.transaction_date.isoformat() if quote.transaction_date else None,
        "valid_till": quote.valid_till.isoformat() if quote.valid_till else None,
        "currency": quote.currency,
        "total_amount": float(quote.total or 0),
        "tax_amount": float(quote.total_taxes_and_charges or 0),
        "grand_total": float(quote.grand_total or 0),
        "notes": None,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
async def list_quotations(
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    customer_name: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List quotations with filtering."""
    query = db.query(Quotation).filter(Quotation.is_deleted == False)

    if status:
        status_enum = _parse_status(status)
        if status_enum:
            query = query.filter(Quotation.status == status_enum)

    if contact_id:
        query = query.filter(Quotation.contact_id == contact_id)

    if customer_name:
        query = query.filter(Quotation.customer_name.ilike(f"%{customer_name}%"))

    total = query.count()
    quotes = query.order_by(Quotation.id.desc()).offset(offset).limit(limit).all()

    return {
        "data": [_serialize_quotation(quote) for quote in quotes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{quotation_id}", dependencies=[Depends(Require("crm:read"))])
async def get_quotation(quotation_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a quotation by ID."""
    quote = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    return _serialize_quotation(quote)


@router.post("", dependencies=[Depends(Require("crm:write"))], status_code=201)
async def create_quotation(
    payload: QuotationCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new quotation."""
    # Validate contact if provided
    if payload.contact_id:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    quote = Quotation(
        contact_id=payload.contact_id,
        customer_name=payload.customer_name,
        transaction_date=payload.quotation_date,
        valid_till=payload.valid_till,
        currency=payload.currency,
        total=payload.total_amount,
        total_taxes_and_charges=payload.tax_amount,
        grand_total=payload.grand_total,
        status=QuotationStatus.DRAFT,
    )

    db.add(quote)
    db.commit()
    db.refresh(quote)

    return _serialize_quotation(quote)


@router.patch("/{quotation_id}", dependencies=[Depends(Require("crm:write"))])
async def update_quotation(
    quotation_id: int,
    payload: QuotationUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a quotation."""
    quote = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle status conversion
    if "status" in update_data and update_data["status"]:
        update_data["status"] = _parse_status(update_data["status"])

    # Map field names
    field_mapping = {
        "quotation_date": "transaction_date",
        "total_amount": "total",
        "tax_amount": "total_taxes_and_charges",
    }

    for key, value in update_data.items():
        mapped_key = field_mapping.get(key, key)
        if hasattr(quote, mapped_key):
            setattr(quote, mapped_key, value)

    db.commit()
    db.refresh(quote)

    return _serialize_quotation(quote)


@router.delete("/{quotation_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_quotation(quotation_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Soft-delete a quotation."""
    quote = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    quote.is_deleted = True
    quote.status = QuotationStatus.CANCELLED
    db.commit()

    return {"success": True, "message": "Quotation deleted"}


@router.post("/{quotation_id}/submit", dependencies=[Depends(Require("crm:write"))])
async def submit_quotation(quotation_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Submit a quotation (move from draft to submitted)."""
    quote = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    if quote.status != QuotationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft quotations can be submitted")

    quote.status = QuotationStatus.SUBMITTED
    quote.docstatus = 1
    db.commit()
    db.refresh(quote)

    return _serialize_quotation(quote)


@router.post("/{quotation_id}/convert-to-order", dependencies=[Depends(Require("crm:write"))])
async def convert_to_order(quotation_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Convert a quotation to a sales order."""
    from app.models.sales import SalesOrder, SalesOrderStatus

    quote = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    if quote.status == QuotationStatus.ORDERED:
        raise HTTPException(status_code=400, detail="Quotation already converted to order")

    # Create sales order from quotation
    order = SalesOrder(
        contact_id=quote.contact_id,
        customer_id=quote.customer_id,
        customer_name=quote.customer_name,
        transaction_date=datetime.utcnow(),
        currency=quote.currency,
        total=quote.total,
        total_taxes_and_charges=quote.total_taxes_and_charges,
        grand_total=quote.grand_total,
        status=SalesOrderStatus.DRAFT,
    )

    db.add(order)

    # Mark quotation as ordered
    quote.status = QuotationStatus.ORDERED

    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "message": "Quotation converted to sales order",
        "order_id": order.id,
    }
