"""
Holiday Lists Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.models.hr_leave import HolidayList, Holiday

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
    query = db.query(HolidayList)

    if company:
        query = query.filter(HolidayList.company.ilike(f"%{company}%"))
    if year:
        query = query.filter(func.extract("year", HolidayList.from_date) == year)
    if search:
        query = query.filter(HolidayList.holiday_list_name.ilike(f"%{search}%"))

    total = query.count()
    lists = query.order_by(HolidayList.from_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": h.id,
                "erpnext_id": h.erpnext_id,
                "holiday_list_name": h.holiday_list_name,
                "from_date": h.from_date.isoformat() if h.from_date else None,
                "to_date": h.to_date.isoformat() if h.to_date else None,
                "total_holidays": h.total_holidays,
                "company": h.company,
                "weekly_off": h.weekly_off,
                "holiday_count": len(h.holidays),
            }
            for h in lists
        ],
    }


@router.get("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:read"))])
def get_holiday_list(
    list_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get holiday list detail with holidays."""
    h = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    holidays = [
        {
            "id": hd.id,
            "holiday_date": hd.holiday_date.isoformat() if hd.holiday_date else None,
            "description": hd.description,
            "weekly_off": hd.weekly_off,
            "idx": hd.idx,
        }
        for hd in sorted(h.holidays, key=lambda x: x.idx)
    ]

    return {
        "id": h.id,
        "erpnext_id": h.erpnext_id,
        "holiday_list_name": h.holiday_list_name,
        "from_date": h.from_date.isoformat() if h.from_date else None,
        "to_date": h.to_date.isoformat() if h.to_date else None,
        "total_holidays": h.total_holidays,
        "company": h.company,
        "weekly_off": h.weekly_off,
        "holidays": holidays,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


@router.post("/holiday-lists", dependencies=[Depends(Require("hr:write"))])
def create_holiday_list(
    payload: HolidayListCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new holiday list with holidays."""
    holiday_list = HolidayList(
        holiday_list_name=payload.holiday_list_name,
        from_date=payload.from_date,
        to_date=payload.to_date,
        company=payload.company,
        weekly_off=payload.weekly_off,
        total_holidays=len(payload.holidays) if payload.holidays else 0,
    )
    db.add(holiday_list)
    db.flush()

    if payload.holidays:
        for idx, h in enumerate(payload.holidays):
            holiday = Holiday(
                holiday_list_id=holiday_list.id,
                holiday_date=h.holiday_date,
                description=h.description,
                weekly_off=h.weekly_off or False,
                idx=h.idx if h.idx is not None else idx,
            )
            db.add(holiday)

    db.commit()
    return get_holiday_list(holiday_list.id, db)


@router.patch("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:write"))])
def update_holiday_list(
    list_id: int,
    payload: HolidayListUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a holiday list and optionally replace holidays."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

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

    if payload.holidays is not None:
        db.query(Holiday).filter(Holiday.holiday_list_id == holiday_list.id).delete(synchronize_session=False)
        for idx, h in enumerate(payload.holidays):
            holiday = Holiday(
                holiday_list_id=holiday_list.id,
                holiday_date=h.holiday_date,
                description=h.description,
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
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    db.delete(holiday_list)
    db.commit()
    return {"message": "Holiday list deleted", "id": list_id}


