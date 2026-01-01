"""
Leave Policies Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require
from app.models.hr_leave import LeavePolicy, LeavePolicyDetail
from .helpers import decimal_or_default

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


@router.get("/leave-policies", dependencies=[Depends(Require("hr:read"))])
def list_leave_policies(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave policies with filtering."""
    query = db.query(LeavePolicy)

    if search:
        query = query.filter(LeavePolicy.leave_policy_name.ilike(f"%{search}%"))

    total = query.count()
    policies = query.order_by(LeavePolicy.leave_policy_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "leave_policy_name": p.leave_policy_name,
                "detail_count": len(p.details),
            }
            for p in policies
        ],
    }


@router.get("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave policy detail with details."""
    p = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    details = [
        {
            "id": d.id,
            "leave_type": d.leave_type,
            "leave_type_id": d.leave_type_id,
            "annual_allocation": float(d.annual_allocation) if d.annual_allocation else 0,
            "idx": d.idx,
        }
        for d in sorted(p.details, key=lambda x: x.idx)
    ]

    return {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "leave_policy_name": p.leave_policy_name,
        "details": details,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/leave-policies", dependencies=[Depends(Require("hr:write"))])
def create_leave_policy(
    payload: LeavePolicyCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave policy with details."""
    policy = LeavePolicy(
        leave_policy_name=payload.leave_policy_name,
    )
    db.add(policy)
    db.flush()

    if payload.details:
        for idx, d in enumerate(payload.details):
            detail = LeavePolicyDetail(
                leave_policy_id=policy.id,
                leave_type=d.leave_type,
                leave_type_id=d.leave_type_id,
                annual_allocation=decimal_or_default(d.annual_allocation),
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return get_leave_policy(policy.id, db)


@router.patch("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_policy(
    policy_id: int,
    payload: LeavePolicyUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave policy and optionally replace details."""
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    if payload.leave_policy_name is not None:
        policy.leave_policy_name = payload.leave_policy_name

    if payload.details is not None:
        db.query(LeavePolicyDetail).filter(LeavePolicyDetail.leave_policy_id == policy.id).delete(synchronize_session=False)
        for idx, d in enumerate(payload.details):
            detail = LeavePolicyDetail(
                leave_policy_id=policy.id,
                leave_type=d.leave_type,
                leave_type_id=d.leave_type_id,
                annual_allocation=decimal_or_default(d.annual_allocation),
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return get_leave_policy(policy.id, db)


@router.delete("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave policy and its details."""
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    db.delete(policy)
    db.commit()
    return {"message": "Leave policy deleted", "id": policy_id}
