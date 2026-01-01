"""
Leave Types Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.hr_leave import LeaveType
from .helpers import decimal_or_default

router = APIRouter()

# LEAVE TYPE
# =============================================================================

class LeaveTypeCreate(BaseModel):
    leave_type_name: str
    max_leaves_allowed: Optional[int] = 0
    max_continuous_days_allowed: Optional[int] = 0
    is_carry_forward: Optional[bool] = False
    is_lwp: Optional[bool] = False
    is_optional_leave: Optional[bool] = False
    is_compensatory: Optional[bool] = False
    allow_encashment: Optional[bool] = False
    include_holiday: Optional[bool] = False
    is_earned_leave: Optional[bool] = False
    earned_leave_frequency: Optional[str] = None
    rounding: Optional[Decimal] = None


class LeaveTypeUpdate(BaseModel):
    leave_type_name: Optional[str] = None
    max_leaves_allowed: Optional[int] = None
    max_continuous_days_allowed: Optional[int] = None
    is_carry_forward: Optional[bool] = None
    is_lwp: Optional[bool] = None
    is_optional_leave: Optional[bool] = None
    is_compensatory: Optional[bool] = None
    allow_encashment: Optional[bool] = None
    include_holiday: Optional[bool] = None
    is_earned_leave: Optional[bool] = None
    earned_leave_frequency: Optional[str] = None
    rounding: Optional[Decimal] = None


@router.get("/leave-types", dependencies=[Depends(Require("hr:read"))])
def list_leave_types(
    search: Optional[str] = None,
    is_lwp: Optional[bool] = None,
    is_carry_forward: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave types."""
    query = db.query(LeaveType)

    if search:
        query = query.filter(LeaveType.leave_type_name.ilike(f"%{search}%"))
    if is_lwp is not None:
        query = query.filter(LeaveType.is_lwp == is_lwp)
    if is_carry_forward is not None:
        query = query.filter(LeaveType.is_carry_forward == is_carry_forward)

    total = query.count()
    leave_types = query.order_by(LeaveType.leave_type_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": lt.id,
                "erpnext_id": lt.erpnext_id,
                "leave_type_name": lt.leave_type_name,
                "max_leaves_allowed": lt.max_leaves_allowed,
                "max_continuous_days_allowed": lt.max_continuous_days_allowed,
                "is_carry_forward": lt.is_carry_forward,
                "is_lwp": lt.is_lwp,
                "is_optional_leave": lt.is_optional_leave,
                "is_compensatory": lt.is_compensatory,
                "allow_encashment": lt.allow_encashment,
                "include_holiday": lt.include_holiday,
                "is_earned_leave": lt.is_earned_leave,
                "earned_leave_frequency": lt.earned_leave_frequency,
                "rounding": float(lt.rounding) if lt.rounding else 0.5,
            }
            for lt in leave_types
        ],
    }


@router.get("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave type detail."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    return {
        "id": lt.id,
        "erpnext_id": lt.erpnext_id,
        "leave_type_name": lt.leave_type_name,
        "max_leaves_allowed": lt.max_leaves_allowed,
        "max_continuous_days_allowed": lt.max_continuous_days_allowed,
        "is_carry_forward": lt.is_carry_forward,
        "is_lwp": lt.is_lwp,
        "is_optional_leave": lt.is_optional_leave,
        "is_compensatory": lt.is_compensatory,
        "allow_encashment": lt.allow_encashment,
        "include_holiday": lt.include_holiday,
        "is_earned_leave": lt.is_earned_leave,
        "earned_leave_frequency": lt.earned_leave_frequency,
        "rounding": float(lt.rounding) if lt.rounding else 0.5,
        "created_at": lt.created_at.isoformat() if lt.created_at else None,
        "updated_at": lt.updated_at.isoformat() if lt.updated_at else None,
    }


@router.post("/leave-types", dependencies=[Depends(Require("hr:write"))])
def create_leave_type(
    payload: LeaveTypeCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave type."""
    lt = LeaveType(
        leave_type_name=payload.leave_type_name,
        max_leaves_allowed=payload.max_leaves_allowed or 0,
        max_continuous_days_allowed=payload.max_continuous_days_allowed or 0,
        is_carry_forward=payload.is_carry_forward or False,
        is_lwp=payload.is_lwp or False,
        is_optional_leave=payload.is_optional_leave or False,
        is_compensatory=payload.is_compensatory or False,
        allow_encashment=payload.allow_encashment or False,
        include_holiday=payload.include_holiday or False,
        is_earned_leave=payload.is_earned_leave or False,
        earned_leave_frequency=payload.earned_leave_frequency,
        rounding=decimal_or_default(payload.rounding, Decimal("0.5")),
    )
    db.add(lt)
    db.commit()
    return get_leave_type(lt.id, db)


@router.patch("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave type."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "rounding" and value is not None:
            setattr(lt, field, decimal_or_default(value))
        elif value is not None:
            setattr(lt, field, value)

    db.commit()
    return get_leave_type(leave_type_id, db)


@router.delete("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave type."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")
    db.delete(lt)
    db.commit()
    return {"message": "Leave type deleted", "id": leave_type_id}


