"""
PAYE (Pay As You Earn) Endpoints

Nigerian personal income tax with progressive bands (7-24%).
Includes Consolidated Relief Allowance (CRA) calculation.
Monthly filing by 10th of following month.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import (
    PAYECalculationCreate,
    PAYECalculationResponse,
    PAYESummaryResponse,
    PaginatedResponse,
)
from app.api.tax.deps import get_single_company, require_tax_write

router = APIRouter(prefix="/paye", tags=["PAYE"])


@router.get("/calculations", response_model=PaginatedResponse)
def get_paye_calculations(
    company: str = Depends(get_single_company),
    period: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    employee_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get PAYE calculations with filters."""
    service = NigerianTaxService(db)
    calculations, total = service.get_paye_calculations(
        company=company,
        period=period,
        employee_id=employee_id,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [PAYECalculationResponse.model_validate(c) for c in calculations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/calculate", response_model=PAYECalculationResponse)
def calculate_paye(
    data: PAYECalculationCreate,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
    _: None = Depends(require_tax_write()),
):
    """
    Calculate PAYE for an employee.

    Nigerian PAYE uses progressive tax bands:
    - First N300,000: 7%
    - Next N300,000: 11%
    - Next N500,000: 15%
    - Next N500,000: 19%
    - Next N1,600,000: 21%
    - Over N3,200,000: 24%

    Consolidated Relief Allowance (CRA):
    - Higher of N200,000 or 1% of gross income
    - Plus 20% of gross income

    Other reliefs:
    - Pension contribution (8% of basic + housing + transport)
    - National Housing Fund (2.5% of basic)
    - Life assurance premiums
    """
    service = NigerianTaxService(db)
    calculation = service.calculate_employee_paye_full(
        company=company,
        employee_id=data.employee_id,
        employee_name=data.employee_name,
        payroll_period=data.payroll_period,
        period_start=data.period_start,
        period_end=data.period_end,
        basic_salary=data.basic_salary,
        housing_allowance=data.housing_allowance,
        transport_allowance=data.transport_allowance,
        other_allowances=data.other_allowances,
        bonus=data.bonus,
        pension_contribution=data.pension_contribution,
        nhf_contribution=data.nhf_contribution,
        life_assurance=data.life_assurance,
        other_reliefs=data.other_reliefs,
        employee_tin=data.employee_tin,
        state_of_residence=data.state_of_residence,
    )

    return PAYECalculationResponse.model_validate(calculation)


@router.get("/summary/{period}", response_model=PAYESummaryResponse)
def get_paye_summary(
    period: str,
    company: str = Depends(get_single_company),
    db: Session = Depends(get_db),
):
    """
    Get PAYE summary for a period.

    Returns:
    - Employee count
    - Total gross income
    - Total tax calculated
    - Filing status
    - Due date (10th of following month)
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
    summary = service.get_paye_summary(company, period)

    return PAYESummaryResponse(**summary)


@router.get("/employee/{employee_id}/history", response_model=PaginatedResponse)
def get_employee_paye_history(
    employee_id: int,
    company: str = Depends(get_single_company),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Get PAYE calculation history for an employee."""
    service = NigerianTaxService(db)
    calculations, total = service.get_paye_calculations(
        company=company,
        employee_id=employee_id,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [PAYECalculationResponse.model_validate(c) for c in calculations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
