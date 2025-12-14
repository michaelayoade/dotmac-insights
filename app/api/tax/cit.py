"""
CIT (Company Income Tax) Endpoints

Nigerian CIT with progressive rates based on turnover:
- Small companies (<=N25M): 0%
- Medium companies (N25M-N100M): 20%
- Large companies (>N100M): 30%

Plus TET (Tertiary Education Tax) at 3% of assessable profit.
"""

from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    CITAssessmentCreate,
    CITAssessmentResponse,
    CITComputationResponse,
    PaginatedResponse,
)
from app.api.tax.helpers import get_cit_rate, TET_RATE, MINIMUM_TAX_RATE
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/cit", tags=["CIT"])


@router.get("/assessments", response_model=PaginatedResponse)
def get_cit_assessments(
    company: str = Depends(get_single_company),
    fiscal_year: Optional[str] = Query(None, pattern=r"^\d{4}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get CIT assessments with filters."""
    service = NigerianTaxService(db)
    assessments, total = service.get_cit_assessments(
        company=company,
        fiscal_year=fiscal_year,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [CITAssessmentResponse.model_validate(a) for a in assessments],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/create-assessment", response_model=CITAssessmentResponse)
def create_cit_assessment(
    data: CITAssessmentCreate,
    db: Session = Depends(get_db),
    company: str = Depends(get_single_company),
    _: None = Depends(require_tax_write()),
):
    """
    Create CIT assessment for a fiscal year.

    Tax computation:
    1. Start with gross profit
    2. Add back disallowed expenses
    3. Deduct capital allowances
    4. Deduct investment allowances
    5. Deduct losses brought forward
    6. Apply CIT rate based on turnover
    7. Add TET (3% of assessable profit)

    Company size thresholds:
    - Small: Turnover <= N25 million (0% CIT)
    - Medium: N25M < Turnover <= N100 million (20% CIT)
    - Large: Turnover > N100 million (30% CIT)
    """
    service = NigerianTaxService(db)
    assessment = service.create_cit_assessment(
        company=company,
        fiscal_year=data.fiscal_year,
        period_start=data.period_start,
        period_end=data.period_end,
        gross_turnover=data.gross_turnover,
        gross_profit=data.gross_profit,
        disallowed_expenses=data.disallowed_expenses,
        capital_allowances=data.capital_allowances,
        loss_brought_forward=data.loss_brought_forward,
        investment_allowances=data.investment_allowances,
        company_tin=data.company_tin,
    )

    return CITAssessmentResponse.model_validate(assessment)


@router.get("/{fiscal_year}/computation", response_model=CITComputationResponse)
def get_cit_computation(
    fiscal_year: str,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get detailed CIT computation breakdown for a fiscal year.

    Returns:
    - Company size classification
    - Profit adjustments
    - CIT calculation details
    - TET calculation
    - Minimum tax comparison
    - Payment status
    """
    service = NigerianTaxService(db)
    assessments, total = service.get_cit_assessments(
        company=company,
        fiscal_year=fiscal_year,
        page=1,
        page_size=1,
    )

    if not assessments:
        raise HTTPException(
            status_code=404,
            detail=f"No CIT assessment found for fiscal year {fiscal_year}"
        )

    assessment = assessments[0]

    return CITComputationResponse(
        fiscal_year=assessment.fiscal_year,
        company_size=assessment.company_size,
        gross_turnover=assessment.gross_turnover,
        gross_profit=assessment.gross_profit,
        adjustments={
            "disallowed_expenses": assessment.disallowed_expenses,
            "capital_allowances": assessment.capital_allowances,
            "investment_allowances": assessment.investment_allowances,
            "loss_brought_forward": assessment.loss_brought_forward,
        },
        adjusted_profit=assessment.adjusted_profit,
        assessable_profit=assessment.assessable_profit,
        cit_computation={
            "rate": assessment.cit_rate,
            "assessable_profit": assessment.assessable_profit,
            "cit_amount": assessment.cit_amount,
        },
        tet_computation={
            "rate": assessment.tet_rate,
            "assessable_profit": assessment.assessable_profit,
            "tet_amount": assessment.tet_amount,
        },
        minimum_tax_computation={
            "rate": MINIMUM_TAX_RATE,
            "gross_turnover": assessment.gross_turnover,
            "minimum_tax": assessment.minimum_tax,
            "is_applicable": assessment.is_minimum_tax_applicable,
        },
        total_tax_liability=assessment.total_tax_liability,
        payment_status={
            "amount_paid": assessment.amount_paid,
            "balance_due": assessment.balance_due,
            "due_date": assessment.due_date,
            "is_filed": assessment.is_filed,
        },
    )


@router.get("/rate-calculator")
def calculate_cit_rate(
    annual_turnover: Decimal = Query(..., gt=0),
):
    """
    Calculate applicable CIT rate based on annual turnover.

    Returns company size classification and applicable rate.
    """
    rate, size = get_cit_rate(annual_turnover)

    return {
        "annual_turnover": annual_turnover,
        "company_size": size.value,
        "cit_rate": rate,
        "cit_rate_percent": float(rate * 100),
        "tet_rate": TET_RATE,
        "tet_rate_percent": float(TET_RATE * 100),
        "thresholds": {
            "small": {"max_turnover": 25000000, "rate": 0},
            "medium": {"min_turnover": 25000000, "max_turnover": 100000000, "rate": 20},
            "large": {"min_turnover": 100000000, "rate": 30},
        }
    }
