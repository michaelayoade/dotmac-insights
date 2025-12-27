"""
WHT (Withholding Tax) Endpoints

Nigerian WHT with variable rates by payment type.
Federal: 21 days remittance, State: 30 days.
2x penalty rate for suppliers without valid TIN.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    WHTTransactionCreate,
    WHTTransactionResponse,
    WHTSupplierSummaryResponse,
    WHTRemittanceDueResponse,
    PaginatedResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/wht", tags=["WHT"])


@router.get("/transactions", response_model=PaginatedResponse)
def get_wht_transactions(
    company: str = Depends(get_single_company),
    supplier_id: Optional[int] = None,
    is_remitted: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get WHT transactions with filters."""
    service = NigerianTaxService(db)
    transactions, total = service.get_wht_transactions(
        company=company,
        supplier_id=supplier_id,
        is_remitted=is_remitted,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [WHTTransactionResponse.model_validate(t) for t in transactions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/deduct", response_model=WHTTransactionResponse)
def record_wht_deduction(
    data: WHTTransactionCreate,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Record WHT deduction from supplier payment.

    WHT rates vary by payment type:
    - 10%: Dividend, Interest, Rent, Royalty, Commission, Consultancy
    - 5%: Contract, Supply (corporate), Construction, Professional fees
    - 2.5%: All-aspects contracts

    If supplier has no valid TIN, rate is doubled (2x penalty).
    """
    service = NigerianTaxService(db)
    transaction = service.record_wht_deduction(
        company=company,
        transaction_date=data.transaction_date,
        payment_type=data.payment_type,
        supplier_name=data.supplier_name,
        gross_amount=data.gross_amount,
        source_doctype=data.source_doctype,
        source_docname=data.source_docname,
        supplier_id=data.supplier_id,
        supplier_tin=data.supplier_tin,
        supplier_is_corporate=data.supplier_is_corporate,
        jurisdiction=data.jurisdiction,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
    )

    return WHTTransactionResponse.model_validate(transaction)


@router.get("/supplier/{supplier_id}/summary", response_model=WHTSupplierSummaryResponse)
def get_supplier_wht_summary(
    supplier_id: int,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get WHT summary for a specific supplier.

    Returns:
    - Total gross payments
    - Total WHT deducted
    - Total net paid
    - Certificates issued
    - Pending certificate amount
    """
    service = NigerianTaxService(db)
    summary = service.get_supplier_wht_summary(company, supplier_id)

    if summary["transaction_count"] == 0:
        raise HTTPException(
            status_code=404,
            detail="No WHT transactions found for this supplier"
        )

    return WHTSupplierSummaryResponse(**summary)


@router.get("/remittance-due", response_model=WHTRemittanceDueResponse)
def get_wht_remittance_due(
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get pending WHT remittances.

    Returns:
    - All unremitted transactions
    - Overdue count and amount
    - Due this week count and amount

    Remittance deadlines:
    - Federal: 21 days after deduction
    - State: 30 days after deduction
    """
    service = NigerianTaxService(db)
    result = service.get_wht_remittance_due(company)

    return WHTRemittanceDueResponse(
        transactions=[WHTTransactionResponse.model_validate(t) for t in result["transactions"]],
        total_amount=result["total_amount"],
        overdue_count=result["overdue_count"],
        overdue_amount=result["overdue_amount"],
        due_this_week=result["due_this_week"],
        due_this_week_amount=result["due_this_week_amount"],
    )
