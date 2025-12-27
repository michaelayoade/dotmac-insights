"""
WHT Certificate Endpoints

Generate and manage WHT credit certificates for suppliers.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    WHTCertificateCreate,
    WHTCertificateResponse,
    PaginatedResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.post("/wht/generate", response_model=WHTCertificateResponse)
def generate_wht_certificate(
    data: WHTCertificateCreate,
    db: Session = Depends(get_db),
    company: str = Depends(get_single_company),
    _: None = Depends(require_tax_write()),
):
    """
    Generate WHT credit certificate for a supplier.

    Consolidates all uncertified WHT transactions for the supplier
    within the specified period into a single certificate.

    The certificate can be used by the supplier to claim WHT credits
    when filing their own tax returns.
    """
    service = NigerianTaxService(db)

    try:
        certificate = service.generate_wht_certificate(
            company=company,
            supplier_id=data.supplier_id,
            period_start=data.period_start,
            period_end=data.period_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return WHTCertificateResponse.model_validate(certificate)


@router.get("/wht/{certificate_id}", response_model=WHTCertificateResponse)
def get_wht_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
):
    """Get WHT certificate details."""
    from app.models.tax_ng import WHTCertificate

    certificate = db.query(WHTCertificate).filter(
        WHTCertificate.id == certificate_id
    ).first()

    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return WHTCertificateResponse.model_validate(certificate)


@router.get("/wht", response_model=PaginatedResponse)
def list_wht_certificates(
    company: str = Depends(get_single_company),
    supplier_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List WHT certificates with filters."""
    from app.models.tax_ng import WHTCertificate

    query = db.query(WHTCertificate).filter(WHTCertificate.company == company)

    if supplier_id:
        query = query.filter(WHTCertificate.supplier_id == supplier_id)

    total = query.count()
    certificates = query.order_by(WHTCertificate.issue_date.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    return {
        "items": [WHTCertificateResponse.model_validate(c) for c in certificates],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/wht/{certificate_id}/issue", response_model=WHTCertificateResponse)
def issue_wht_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Mark WHT certificate as issued.

    Once issued, the certificate is final and sent to the supplier.
    """
    from datetime import datetime
    from app.models.tax_ng import WHTCertificate

    certificate = db.query(WHTCertificate).filter(
        WHTCertificate.id == certificate_id
    ).first()

    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if certificate.is_issued:
        raise HTTPException(status_code=400, detail="Certificate already issued")

    if certificate.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot issue cancelled certificate")

    certificate.is_issued = True
    certificate.issued_at = datetime.utcnow()

    db.commit()
    db.refresh(certificate)

    return WHTCertificateResponse.model_validate(certificate)


@router.post("/wht/{certificate_id}/cancel", response_model=WHTCertificateResponse)
def cancel_wht_certificate(
    certificate_id: int,
    reason: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Cancel WHT certificate.

    Provide a reason for cancellation.
    Transactions will become available for a new certificate.
    """
    from datetime import datetime
    from app.models.tax_ng import WHTCertificate, WHTTransaction

    certificate = db.query(WHTCertificate).filter(
        WHTCertificate.id == certificate_id
    ).first()

    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if certificate.is_cancelled:
        raise HTTPException(status_code=400, detail="Certificate already cancelled")

    # Unlink transactions
    db.query(WHTTransaction).filter(
        WHTTransaction.certificate_id == certificate_id
    ).update({"certificate_id": None})

    certificate.is_cancelled = True
    certificate.cancelled_at = datetime.utcnow()
    certificate.cancellation_reason = reason

    db.commit()
    db.refresh(certificate)

    return WHTCertificateResponse.model_validate(certificate)
