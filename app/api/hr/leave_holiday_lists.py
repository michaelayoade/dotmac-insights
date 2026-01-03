"""
Holiday Lists Endpoints

Uses LeaveService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import HolidayListCreateData, HolidayData
from app.services.hr.errors import ValidationError as HRValidationError
from app.models.hr_leave import Holiday

router = APIRouter()

# =============================================================================
# HOLIDAY LIST
# =============================================================================


class HolidayPayload(BaseModel):
    holiday_date: date
    description: Optional[str] = None
    weekly_off: Optional[bool] = False
    idx: Optional[int] = 0


class HolidayListCreate(BaseModel):
    holiday_list_name: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    weekly_off: Optional[str] = None
    holidays: Optional[List[HolidayPayload]] = Field(default=None)


class HolidayListUpdate(BaseModel):
    holiday_list_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    weekly_off: Optional[str] = None
    holidays: Optional[List[HolidayPayload]] = Field(default=None)


def _serialize_holiday_list(h, include_holidays: bool = False) -> Dict[str, Any]:
    """Serialize a HolidayList model to dict."""
    result = {
        "id": h.id,
        "erpnext_id": h.erpnext_id,
        "holiday_list_name": h.holiday_list_name,
        "from_date": h.from_date.isoformat() if h.from_date else None,
        "to_date": h.to_date.isoformat() if h.to_date else None,
        "total_holidays": h.total_holidays,
        "company": h.company,
        "weekly_off": h.weekly_off,
        "holiday_count": len(h.holidays) if h.holidays else 0,
    }
    if include_holidays:
        result["holidays"] = [
            {
                "id": hd.id,
                "holiday_date": hd.holiday_date.isoformat() if hd.holiday_date else None,
                "description": hd.description,
                "weekly_off": hd.weekly_off,
                "idx": hd.idx,
            }
            for hd in sorted(h.holidays, key=lambda x: x.idx)
        ]
        result["created_at"] = h.created_at.isoformat() if h.created_at else None
        result["updated_at"] = h.updated_at.isoformat() if h.updated_at else None
    return result


@router.get("/holiday-lists", dependencies=[Depends(Require("hr:read"))])
def list_holiday_lists(
    company: Optional[str] = None,
    year: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List holiday lists with filtering."""
    service = LeaveService(db)
    lists = service.list_holiday_lists(year=year)

    # Apply additional filters
    if company:
        company_lower = company.lower()
        lists = [h for h in lists if h.company and company_lower in h.company.lower()]
    if search:
        search_lower = search.lower()
        lists = [h for h in lists if search_lower in h.holiday_list_name.lower()]

    # Sort by from_date descending
    lists = sorted(lists, key=lambda x: x.from_date or date.min, reverse=True)

    total = len(lists)
    lists = lists[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_holiday_list(h) for h in lists],
    }


@router.get("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:read"))])
def get_holiday_list(
    list_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get holiday list detail with holidays."""
    service = LeaveService(db)
    try:
        h = service.get_holiday_list(list_id)
    except HRValidationError:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    return _serialize_holiday_list(h, include_holidays=True)


@router.post("/holiday-lists", dependencies=[Depends(Require("hr:write"))])
def create_holiday_list(
    payload: HolidayListCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new holiday list with holidays."""
    service = LeaveService(db)

    # Require from_date and to_date for service
    if not payload.from_date or not payload.to_date:
        raise HTTPException(status_code=400, detail="from_date and to_date are required")

    create_data = HolidayListCreateData(
        holiday_list_name=payload.holiday_list_name,
        from_date=payload.from_date,
        to_date=payload.to_date,
        company=payload.company,
        weekly_off=payload.weekly_off,
    )

    try:
        holiday_list = service.create_holiday_list(create_data)

        # Add holidays if provided
        if payload.holidays:
            for idx, h in enumerate(payload.holidays):
                holiday = Holiday(
                    holiday_list_id=holiday_list.id,
                    holiday_date=h.holiday_date,
                    description=h.description or "",
                    weekly_off=h.weekly_off or False,
                    idx=h.idx if h.idx is not None else idx,
                )
                db.add(holiday)
            holiday_list.total_holidays = len(payload.holidays)

        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_holiday_list(holiday_list.id, db)


@router.patch("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:write"))])
def update_holiday_list(
    list_id: int,
    payload: HolidayListUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a holiday list and optionally replace holidays."""
    service = LeaveService(db)

    try:
        holiday_list = service.get_holiday_list(list_id)
    except HRValidationError:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    # Update fields
    if payload.holiday_list_name is not None:
        holiday_list.holiday_list_name = payload.holiday_list_name
    if payload.from_date is not None:
        holiday_list.from_date = payload.from_date
    if payload.to_date is not None:
        holiday_list.to_date = payload.to_date
    if payload.company is not None:
        holiday_list.company = payload.company
    if payload.weekly_off is not None:
        holiday_list.weekly_off = payload.weekly_off

    # Replace holidays if provided
    if payload.holidays is not None:
        # Remove existing holidays
        for existing in list(holiday_list.holidays):
            db.delete(existing)
        db.flush()

        # Add new holidays
        for idx, h in enumerate(payload.holidays):
            holiday = Holiday(
                holiday_list_id=holiday_list.id,
                holiday_date=h.holiday_date,
                description=h.description or "",
                weekly_off=h.weekly_off or False,
                idx=h.idx if h.idx is not None else idx,
            )
            db.add(holiday)
        holiday_list.total_holidays = len(payload.holidays)

    db.commit()
    return get_holiday_list(holiday_list.id, db)


@router.delete("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:write"))])
def delete_holiday_list(
    list_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a holiday list and its holidays."""
    service = LeaveService(db)
    try:
        holiday_list = service.get_holiday_list(list_id)
        db.delete(holiday_list)
        db.commit()
    except HRValidationError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Holiday list not found")

    return {"message": "Holiday list deleted", "id": list_id}


