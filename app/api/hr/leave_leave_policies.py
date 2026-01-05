"""
Leave Policies Endpoints

Uses LeaveService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import (
    LeavePolicyCreateData,
    LeavePolicyUpdateData,
    LeavePolicyDetailData,
)
from app.services.hr.errors import ValidationError as HRValidationError

router = APIRouter()

# =============================================================================
# LEAVE POLICY
# =============================================================================


class LeavePolicyDetailPayload(BaseModel):
    leave_type: str
    leave_type_id: Optional[int] = None
    annual_allocation: Optional[Decimal] = Decimal("0")
    idx: Optional[int] = 0


class LeavePolicyCreate(BaseModel):
    leave_policy_name: str
    details: Optional[List[LeavePolicyDetailPayload]] = Field(default=None)


class LeavePolicyUpdate(BaseModel):
    leave_policy_name: Optional[str] = None
    details: Optional[List[LeavePolicyDetailPayload]] = Field(default=None)


def _serialize_policy(p, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a LeavePolicy model to dict."""
    result = {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "leave_policy_name": p.leave_policy_name,
        "detail_count": len(p.details) if p.details else 0,
    }
    if include_details:
        result["details"] = [
            {
                "id": d.id,
                "leave_type": d.leave_type,
                "leave_type_id": d.leave_type_id,
                "annual_allocation": float(d.annual_allocation) if d.annual_allocation else 0,
                "idx": d.idx,
            }
            for d in sorted(p.details, key=lambda x: x.idx)
        ]
        result["created_at"] = p.created_at.isoformat() if p.created_at else None
        result["updated_at"] = p.updated_at.isoformat() if p.updated_at else None
    return result


@router.get("/leave-policies", dependencies=[Depends(Require("hr:read"))])
def list_leave_policies(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave policies with filtering."""
    service = LeaveService(db)
    policies = service.list_leave_policies()

    # Apply search filter
    if search:
        search_lower = search.lower()
        policies = [p for p in policies if search_lower in p.leave_policy_name.lower()]

    total = len(policies)
    policies = policies[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_policy(p) for p in policies],
    }


@router.get("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave policy detail with details."""
    service = LeaveService(db)
    try:
        p = service.get_leave_policy(policy_id)
    except HRValidationError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    return _serialize_policy(p, include_details=True)


@router.post("/leave-policies", dependencies=[Depends(Require("hr:write"))])
def create_leave_policy(
    payload: LeavePolicyCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave policy with details."""
    service = LeaveService(db)

    details = []
    if payload.details:
        for d in payload.details:
            details.append(
                LeavePolicyDetailData(
                    leave_type=d.leave_type,
                    leave_type_id=d.leave_type_id,
                    annual_allocation=d.annual_allocation or Decimal("0"),
                )
            )

    create_data = LeavePolicyCreateData(
        leave_policy_name=payload.leave_policy_name,
        details=details,
    )

    try:
        policy = service.create_leave_policy(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_policy(policy.id, db)


@router.patch("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_policy(
    policy_id: int,
    payload: LeavePolicyUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave policy and optionally replace details."""
    service = LeaveService(db)

    details = None
    if payload.details is not None:
        details = []
        for d in payload.details:
            details.append(
                LeavePolicyDetailData(
                    leave_type=d.leave_type,
                    leave_type_id=d.leave_type_id,
                    annual_allocation=d.annual_allocation or Decimal("0"),
                )
            )

    update_data = LeavePolicyUpdateData(
        leave_policy_name=payload.leave_policy_name,
        details=details,
    )

    try:
        service.update_leave_policy(policy_id, update_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Leave policy not found")
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_policy(policy_id, db)


@router.delete("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave policy and its details."""
    service = LeaveService(db)
    try:
        policy = service.get_leave_policy(policy_id)
        db.delete(policy)
        db.commit()
    except HRValidationError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave policy not found")

    return {"message": "Leave policy deleted", "id": policy_id}
