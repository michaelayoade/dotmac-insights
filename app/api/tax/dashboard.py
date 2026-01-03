"""
Tax Dashboard Endpoints

Overview of all tax obligations and status.
"""

from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.nigerian_tax_service import NigerianTaxService
from app.api.tax.schemas import TaxDashboardSummary
from app.api.tax.deps import get_single_company

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=TaxDashboardSummary)
def get_tax_dashboard(
    company: str = Depends(get_single_company),
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    """
    Get tax dashboard overview.

    Returns summary of all tax obligations:
    - VAT: Output, Input, Net payable
    - WHT: Deducted, Remitted, Pending, Overdue
    - PAYE: Calculated, Remitted, Pending
    - CIT: Liability, Paid, Status
    - Upcoming deadlines
    """
    if period is None:
        today = date.today()
        period = today.strftime("%Y-%m")

    service = NigerianTaxService(db)
    summary = service.get_dashboard_summary(company, period)

    return TaxDashboardSummary(**summary)
