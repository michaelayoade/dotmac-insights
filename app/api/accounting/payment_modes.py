"""Payment modes CRUD for ERPNext-synced payment methods."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import ModeOfPayment, PaymentModeType

router = APIRouter()


class ModeOfPaymentCreateRequest(BaseModel):
    mode_of_payment: str
    type: Optional[str] = None
    enabled: bool = True


class ModeOfPaymentUpdateRequest(BaseModel):
    mode_of_payment: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/modes-of-payment", dependencies=[Depends(Require("accounting:read"))])
def list_modes_of_payment(
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payment modes."""
    query = db.query(ModeOfPayment)
    if not include_disabled:
        query = query.filter(ModeOfPayment.enabled == True)
    if search:
        query = query.filter(ModeOfPayment.mode_of_payment.ilike(f"%{search}%"))

    total = query.count()
    modes = query.order_by(ModeOfPayment.mode_of_payment).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "modes_of_payment": [
            {
                "id": mode.id,
                "erpnext_id": mode.erpnext_id,
                "mode_of_payment": mode.mode_of_payment,
                "type": mode.type.value if mode.type else None,
                "enabled": mode.enabled,
            }
            for mode in modes
        ],
    }


@router.get("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:read"))])
def get_mode_of_payment(
    mode_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a payment mode by id."""
    mode = db.query(ModeOfPayment).filter(ModeOfPayment.id == mode_id).first()
    if not mode:
        raise HTTPException(status_code=404, detail="Mode of payment not found")

    return {
        "id": mode.id,
        "erpnext_id": mode.erpnext_id,
        "mode_of_payment": mode.mode_of_payment,
        "type": mode.type.value if mode.type else None,
        "enabled": mode.enabled,
    }


@router.post("/modes-of-payment", dependencies=[Depends(Require("accounting:write"))])
def create_mode_of_payment(
    payload: ModeOfPaymentCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a payment mode locally."""
    mode_type = None
    if payload.type:
        try:
            mode_type = PaymentModeType(payload.type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment mode type: {payload.type}")

    mode = ModeOfPayment(
        mode_of_payment=payload.mode_of_payment,
        type=mode_type,
        enabled=payload.enabled,
    )
    db.add(mode)
    db.commit()
    db.refresh(mode)
    return {"id": mode.id}


@router.patch("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:write"))])
def update_mode_of_payment(
    mode_id: int,
    payload: ModeOfPaymentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payment mode locally."""
    mode = db.query(ModeOfPayment).filter(ModeOfPayment.id == mode_id).first()
    if not mode:
        raise HTTPException(status_code=404, detail="Mode of payment not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "type" in update_data and update_data["type"]:
        try:
            update_data["type"] = PaymentModeType(update_data["type"].lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment mode type: {update_data['type']}")

    for key, value in update_data.items():
        setattr(mode, key, value)

    db.commit()
    db.refresh(mode)
    return {"id": mode.id}


@router.delete("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_mode_of_payment(
    mode_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a payment mode."""
    mode = db.query(ModeOfPayment).filter(ModeOfPayment.id == mode_id).first()
    if not mode:
        raise HTTPException(status_code=404, detail="Mode of payment not found")

    mode.enabled = False
    db.commit()
    return {"status": "disabled", "mode_of_payment_id": mode_id}
