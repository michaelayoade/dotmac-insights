"""
VAT (Value Added Tax) Endpoints

Nigerian VAT at 7.5% standard rate.
Monthly filing by 21st of following month.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tax_ng import VATTransactionType
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    VATTransactionCreate,
    VATTransactionResponse,
    VATSummaryResponse,
    VATFilingPrepResponse,
    PaginatedResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/vat", tags=["VAT"])


@router.get("/transactions", response_model=PaginatedResponse)
def get_vat_transactions(
    company: str = Depends(get_single_company),
    period: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    transaction_type: Optional[VATTransactionType] = None,
    is_filed: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get VAT transactions with filters."""
    service = NigerianTaxService(db)
    transactions, total = service.get_vat_transactions(
        company=company,
        period=period,
        transaction_type=transaction_type,
        is_filed=is_filed,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [VATTransactionResponse.model_validate(t) for t in transactions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/record-output", response_model=VATTransactionResponse)
def record_output_vat(
    data: VATTransactionCreate,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Record output VAT (VAT collected on sales).

    Output VAT is the VAT charged to customers on sales.
    This creates a liability to be remitted to FIRS.
    """
    if data.transaction_type != VATTransactionType.OUTPUT:
        raise HTTPException(
            status_code=400,
            detail="Use /record-input for input VAT transactions"
        )

    service = NigerianTaxService(db)
    transaction = service.record_output_vat(
        company=company,
        transaction_date=data.transaction_date,
        party_name=data.party_name,
        party_tin=data.party_tin,
        source_doctype=data.source_doctype,
        source_docname=data.source_docname,
        taxable_amount=data.taxable_amount,
        vat_rate=data.vat_rate,
        party_id=data.party_id,
        party_vat_number=data.party_vat_number,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        is_exempt=data.is_exempt,
        is_zero_rated=data.is_zero_rated,
        exemption_reason=data.exemption_reason,
    )

    return VATTransactionResponse.model_validate(transaction)


@router.post("/record-input", response_model=VATTransactionResponse)
def record_input_vat(
    data: VATTransactionCreate,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Record input VAT (VAT paid on purchases).

    Input VAT is the VAT paid to suppliers on purchases.
    This is claimable as credit against output VAT.
    """
    if data.transaction_type != VATTransactionType.INPUT:
        raise HTTPException(
            status_code=400,
            detail="Use /record-output for output VAT transactions"
        )

    service = NigerianTaxService(db)
    transaction = service.record_input_vat(
        company=company,
        transaction_date=data.transaction_date,
        party_name=data.party_name,
        party_tin=data.party_tin,
        source_doctype=data.source_doctype,
        source_docname=data.source_docname,
        taxable_amount=data.taxable_amount,
        vat_rate=data.vat_rate,
        party_id=data.party_id,
        party_vat_number=data.party_vat_number,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        is_exempt=data.is_exempt,
        exemption_reason=data.exemption_reason,
    )

    return VATTransactionResponse.model_validate(transaction)


@router.get("/summary/{period}", response_model=VATSummaryResponse)
def get_vat_summary(
    period: str,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get VAT summary for a period.

    Returns:
    - Output VAT (collected on sales)
    - Input VAT (paid on purchases)
    - Net VAT payable (output - input)
    - Filing status
    """
    # Validate period format
    try:
        year, month = map(int, period.split("-"))
        if month < 1 or month > 12:
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid period format. Use YYYY-MM (e.g., 2024-01)"
        )

    service = NigerianTaxService(db)
    summary = service.get_vat_summary(company, period)

    return VATSummaryResponse(**summary)


@router.get("/filing-prep/{period}", response_model=VATFilingPrepResponse)
def get_vat_filing_prep(
    period: str,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get VAT filing preparation data.

    Returns all data needed to prepare VAT return:
    - Summary totals
    - Output transactions (sales)
    - Input transactions (purchases)
    - Filing deadline
    """
    # Validate period
    try:
        year, month = map(int, period.split("-"))
        if month < 1 or month > 12:
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid period format. Use YYYY-MM (e.g., 2024-01)"
        )

    service = NigerianTaxService(db)

    # Get summary
    summary = service.get_vat_summary(company, period)

    # Get transactions
    output_txns, _ = service.get_vat_transactions(
        company=company,
        period=period,
        transaction_type=VATTransactionType.OUTPUT,
        page_size=1000,
    )

    input_txns, _ = service.get_vat_transactions(
        company=company,
        period=period,
        transaction_type=VATTransactionType.INPUT,
        page_size=1000,
    )

    # Calculate days until deadline
    from app.api.tax.helpers import get_vat_filing_deadline
    deadline = get_vat_filing_deadline(period)
    days_until = (deadline - date.today()).days

    return VATFilingPrepResponse(
        period=period,
        summary=VATSummaryResponse(**summary),
        output_transactions=[VATTransactionResponse.model_validate(t) for t in output_txns],
        input_transactions=[VATTransactionResponse.model_validate(t) for t in input_txns],
        filing_deadline=deadline,
        days_until_deadline=days_until,
    )
