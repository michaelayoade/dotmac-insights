"""
E-Invoice Endpoints

FIRS BIS 3.0 UBL format e-invoicing preparation.
Structure only - no direct FIRS API integration yet.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tax_ng import EInvoice, EInvoiceStatus
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    EInvoiceCreate,
    EInvoiceResponse,
    EInvoiceValidationResult,
    EInvoiceUBLResponse,
    PaginatedResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/einvoice", tags=["E-Invoice"])


@router.post("/create", response_model=EInvoiceResponse)
def create_einvoice(
    data: EInvoiceCreate,
    db: Session = Depends(get_db),
    company: str = Depends(get_single_company),
    _: None = Depends(require_tax_write()),
):
    """
    Create e-invoice for FIRS BIS 3.0 compliance.

    Creates an e-invoice in DRAFT status with all mandatory fields
    for FIRS e-invoicing requirements.

    The invoice includes:
    - UBL 2.1 version and FIRS customization
    - Supplier details (name, TIN, VAT number, address)
    - Customer details (name, TIN, address)
    - Line items with tax calculations
    - Totals (line extension, tax, payable)
    """
    service = NigerianTaxService(db)

    # Convert lines to dict format
    lines = [line.model_dump() for line in data.lines]

    einvoice = service.create_einvoice(
        company=company,
        source_doctype=data.source_doctype,
        source_docname=data.source_docname,
        issue_date=data.issue_date,
        due_date=data.due_date,
        supplier_name=data.supplier_name,
        supplier_tin=data.supplier_tin,
        supplier_vat_number=data.supplier_vat_number,
        supplier_street=data.supplier_street,
        supplier_city=data.supplier_city,
        supplier_state=data.supplier_state,
        supplier_phone=data.supplier_phone,
        supplier_email=data.supplier_email,
        customer_name=data.customer_name,
        customer_tin=data.customer_tin,
        customer_street=data.customer_street,
        customer_city=data.customer_city,
        customer_state=data.customer_state,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        payment_means_code=data.payment_means_code,
        payment_terms=data.payment_terms,
        lines=lines,
        note=data.note,
    )

    return EInvoiceResponse.model_validate(einvoice)


@router.post("/{einvoice_id}/validate", response_model=EInvoiceValidationResult)
def validate_einvoice(
    einvoice_id: int,
    db: Session = Depends(get_db),
):
    """
    Validate e-invoice against BIS 3.0 requirements.

    Checks:
    - Required fields (invoice number, issue date, parties)
    - TIN format validation
    - Line item requirements
    - Amount calculations

    Returns validation errors and warnings.
    """
    service = NigerianTaxService(db)

    try:
        result = service.validate_einvoice(einvoice_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return EInvoiceValidationResult(**result)


@router.get("/{einvoice_id}/ubl", response_model=EInvoiceUBLResponse)
def get_einvoice_ubl(
    einvoice_id: int,
    db: Session = Depends(get_db),
):
    """
    Get e-invoice in UBL XML format.

    Returns the UBL 2.1 XML structure compliant with FIRS BIS 3.0.
    The XML can be submitted to FIRS when integration is available.
    """
    service = NigerianTaxService(db)

    try:
        result = service.get_einvoice_ubl(einvoice_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return EInvoiceUBLResponse(**result)


@router.get("/{einvoice_id}", response_model=EInvoiceResponse)
def get_einvoice(
    einvoice_id: int,
    db: Session = Depends(get_db),
):
    """Get e-invoice details."""
    einvoice = db.query(EInvoice).filter(EInvoice.id == einvoice_id).first()

    if not einvoice:
        raise HTTPException(status_code=404, detail="E-invoice not found")

    return EInvoiceResponse.model_validate(einvoice)


@router.get("", response_model=PaginatedResponse)
def list_einvoices(
    company: str = Depends(get_single_company),
    status: Optional[EInvoiceStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List e-invoices with filters."""
    query = db.query(EInvoice).filter(EInvoice.company == company)

    if status:
        query = query.filter(EInvoice.status == status)

    total = query.count()
    einvoices = query.order_by(EInvoice.issue_date.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    return {
        "items": [EInvoiceResponse.model_validate(e) for e in einvoices],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.delete("/{einvoice_id}")
def delete_einvoice(
    einvoice_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Delete draft e-invoice.

    Only DRAFT invoices can be deleted.
    """
    einvoice = db.query(EInvoice).filter(EInvoice.id == einvoice_id).first()

    if not einvoice:
        raise HTTPException(status_code=404, detail="E-invoice not found")

    if einvoice.status != EInvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail="Only draft invoices can be deleted"
        )

    db.delete(einvoice)
    db.commit()

    return {"message": "E-invoice deleted successfully"}
