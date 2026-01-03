"""
Leave Types Endpoints

Uses LeaveService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import LeaveTypeCreateData, LeaveTypeUpdateData
from app.services.hr.errors import LeaveTypeNotFoundError, ValidationError as HRValidationError

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


def _serialize_leave_type(lt, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a LeaveType model to dict."""
    result = {
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
    if include_timestamps:
        result["created_at"] = lt.created_at.isoformat() if lt.created_at else None
        result["updated_at"] = lt.updated_at.isoformat() if lt.updated_at else None
    return result


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
    service = LeaveService(db)
    leave_types = service.list_leave_types()

    # Apply filters (service returns all, we filter here for flexibility)
    if search:
        search_lower = search.lower()
        leave_types = [lt for lt in leave_types if search_lower in lt.leave_type_name.lower()]
    if is_lwp is not None:
        leave_types = [lt for lt in leave_types if lt.is_lwp == is_lwp]
    if is_carry_forward is not None:
        leave_types = [lt for lt in leave_types if lt.is_carry_forward == is_carry_forward]

    total = len(leave_types)
    leave_types = leave_types[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_leave_type(lt) for lt in leave_types],
    }


@router.get("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave type detail."""
    service = LeaveService(db)
    try:
        lt = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Leave type not found")

    return _serialize_leave_type(lt, include_timestamps=True)


@router.post("/leave-types", dependencies=[Depends(Require("hr:write"))])
def create_leave_type(
    payload: LeaveTypeCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave type."""
    service = LeaveService(db)

    create_data = LeaveTypeCreateData(
        leave_type_name=payload.leave_type_name,
        max_leaves_allowed=payload.max_leaves_allowed or 0,
        max_continuous_days_allowed=payload.max_continuous_days_allowed,
        is_carry_forward=payload.is_carry_forward or False,
        is_lwp=payload.is_lwp or False,
        is_optional_leave=payload.is_optional_leave or False,
        is_compensatory=payload.is_compensatory or False,
        allow_encashment=payload.allow_encashment or False,
        include_holiday=payload.include_holiday or False,
        is_earned_leave=payload.is_earned_leave or False,
        earned_leave_frequency=payload.earned_leave_frequency,
        rounding=payload.rounding or Decimal("0.5"),
    )

    try:
        lt = service.create_leave_type(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_type(lt.id, db)


@router.patch("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave type."""
    service = LeaveService(db)

    update_data = LeaveTypeUpdateData(
        leave_type_name=payload.leave_type_name,
        max_leaves_allowed=payload.max_leaves_allowed,
        max_continuous_days_allowed=payload.max_continuous_days_allowed,
        is_carry_forward=payload.is_carry_forward,
        is_lwp=payload.is_lwp,
        is_optional_leave=payload.is_optional_leave,
        is_compensatory=payload.is_compensatory,
        allow_encashment=payload.allow_encashment,
        include_holiday=payload.include_holiday,
        is_earned_leave=payload.is_earned_leave,
        earned_leave_frequency=payload.earned_leave_frequency,
        rounding=payload.rounding,
    )

    try:
        service.update_leave_type(leave_type_id, update_data)
        db.commit()
    except LeaveTypeNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave type not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_type(leave_type_id, db)


@router.delete("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave type."""
    service = LeaveService(db)
    try:
        lt = service.get_leave_type(leave_type_id)
        db.delete(lt)
        db.commit()
    except LeaveTypeNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave type not found")

    return {"message": "Leave type deleted", "id": leave_type_id}


