"""
Tax Filing Calendar and Management Endpoints

Manage tax filing deadlines and calendar for all Nigerian taxes.
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tax_ng import NigerianTaxType
from app.api.tax.helpers import get_tax_filing_calendar
from app.api.tax.schemas import (
    FilingCalendarEntry,
    FilingCalendarResponse,
    UpcomingFilingsResponse,
)

router = APIRouter(prefix="/filing", tags=["Filing"])


@router.get("/calendar", response_model=FilingCalendarResponse)
def get_filing_calendar(
    year: int = Query(default=None, ge=2020, le=2100),
    tax_types: Optional[List[NigerianTaxType]] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get tax filing calendar for a year.

    Returns all filing deadlines for the specified year.
    Filter by tax types if needed.
    """
    if year is None:
        year = date.today().year

    # Convert enum list if provided
    types = None
    if tax_types:
        types = tax_types

    calendar = get_tax_filing_calendar(year, types)
    today = date.today()

    entries = []
    overdue_count = 0
    upcoming_count = 0

    for entry in calendar:
        is_overdue = entry["due_date"] < today
        if is_overdue:
            overdue_count += 1
        else:
            upcoming_count += 1

        entries.append(FilingCalendarEntry(
            tax_type=entry["tax_type"],
            period=entry["period"],
            period_start=entry["period_start"],
            period_end=entry["period_end"],
            due_date=entry["due_date"],
            description=entry["description"],
            is_overdue=is_overdue,
            is_filed=False,  # Would check against filing records
        ))

    return FilingCalendarResponse(
        year=year,
        entries=entries,
        upcoming_count=upcoming_count,
        overdue_count=overdue_count,
    )


@router.get("/upcoming", response_model=UpcomingFilingsResponse)
def get_upcoming_filings(
    days: int = Query(30, ge=1, le=365),
    tax_types: Optional[List[NigerianTaxType]] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get upcoming tax filings within specified days.

    Default is next 30 days.
    """
    today = date.today()
    end_date = date(today.year, today.month, today.day)
    end_date = today + __import__('datetime').timedelta(days=days)

    # Get current year calendar
    calendar = get_tax_filing_calendar(today.year, tax_types)

    # Also get next year if end_date crosses year boundary
    if end_date.year > today.year:
        calendar.extend(get_tax_filing_calendar(end_date.year, tax_types))

    upcoming = []
    for entry in calendar:
        if today <= entry["due_date"] <= end_date:
            upcoming.append(FilingCalendarEntry(
                tax_type=entry["tax_type"],
                period=entry["period"],
                period_start=entry["period_start"],
                period_end=entry["period_end"],
                due_date=entry["due_date"],
                description=entry["description"],
                is_overdue=False,
                is_filed=False,
            ))

    # Sort by due date
    upcoming.sort(key=lambda x: x.due_date)

    next_deadline = upcoming[0].due_date if upcoming else None

    return UpcomingFilingsResponse(
        filings=upcoming,
        total=len(upcoming),
        next_deadline=next_deadline,
    )


@router.get("/overdue", response_model=UpcomingFilingsResponse)
def get_overdue_filings(
    tax_types: Optional[List[NigerianTaxType]] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get overdue tax filings.

    Returns all filings past their due date that haven't been filed.
    """
    today = date.today()
    year = today.year

    # Check current and previous year
    calendar = get_tax_filing_calendar(year - 1, tax_types)
    calendar.extend(get_tax_filing_calendar(year, tax_types))

    overdue = []
    for entry in calendar:
        if entry["due_date"] < today:
            overdue.append(FilingCalendarEntry(
                tax_type=entry["tax_type"],
                period=entry["period"],
                period_start=entry["period_start"],
                period_end=entry["period_end"],
                due_date=entry["due_date"],
                description=entry["description"],
                is_overdue=True,
                is_filed=False,  # Would check against filing records
            ))

    # Sort by due date (most recent first)
    overdue.sort(key=lambda x: x.due_date, reverse=True)

    return UpcomingFilingsResponse(
        filings=overdue,
        total=len(overdue),
        next_deadline=None,
    )
