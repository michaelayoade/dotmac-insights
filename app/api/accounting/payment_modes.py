"""Payment modes CRUD for ERPNext-synced payment methods."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.models.accounting import PaymentModeType
from app.services.accounting import PaymentModeService
from app.services.accounting.payment_modes_types import (
    PaymentModeFilters,
    PaymentModeCreateData,
    PaymentModeUpdateData,
)
from app.services.errors import NotFoundError, ValidationError as ServiceValidationError
from app.services.types import PaginationParams

router = APIRouter()


def get_payment_mode_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> PaymentModeService:
    """Dependency to get a PaymentModeService instance."""
    return PaymentModeService(db, principal)


class ModeOfPaymentCreateRequest(BaseModel):
    mode_of_payment: str
    type: Optional[str] = None
    enabled: bool = True


class ModeOfPaymentUpdateRequest(BaseModel):
    mode_of_payment: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None


def _parse_mode_type(type_str: Optional[str], service: PaymentModeService) -> Optional[PaymentModeType]:
    """Parse mode type string to enum."""
    if not type_str:
        return None
    return service.validate_mode_type(type_str)


@router.get("/modes-of-payment", dependencies=[Depends(Require("accounting:read"))])
def list_modes_of_payment(
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: PaymentModeService = Depends(get_payment_mode_service),
) -> Dict[str, Any]:
    """List payment modes."""
    filters = PaymentModeFilters(include_disabled=include_disabled, search=search)
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_payment_modes(filters, pagination)

    return {
        "total": result.total,
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
            for mode in result.items
        ],
    }


@router.get("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:read"))])
def get_mode_of_payment(
    mode_id: int,
    service: PaymentModeService = Depends(get_payment_mode_service),
) -> Dict[str, Any]:
    """Get a payment mode by id."""
    try:
        mode = service.get_payment_mode(mode_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
    service: PaymentModeService = Depends(get_payment_mode_service),
) -> Dict[str, Any]:
    """Create a payment mode locally."""
    try:
        mode_type = _parse_mode_type(payload.type, service)
        create_data = PaymentModeCreateData(
            mode_of_payment=payload.mode_of_payment,
            mode_type=mode_type,
            enabled=payload.enabled,
        )
        mode = service.create_payment_mode(create_data)
        db.commit()
        db.refresh(mode)
        return {"id": mode.id}
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


@router.patch("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:write"))])
def update_mode_of_payment(
    mode_id: int,
    payload: ModeOfPaymentUpdateRequest,
    db: Session = Depends(get_db),
    service: PaymentModeService = Depends(get_payment_mode_service),
) -> Dict[str, Any]:
    """Update a payment mode locally."""
    try:
        mode_type = _parse_mode_type(payload.type, service) if payload.type is not None else None
        update_data = PaymentModeUpdateData(
            mode_of_payment=payload.mode_of_payment,
            mode_type=mode_type,
            enabled=payload.enabled,
        )
        mode = service.update_payment_mode(mode_id, update_data)
        db.commit()
        db.refresh(mode)
        return {"id": mode.id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceValidationError as e:
        db.rollback()
        raise HTTPException(status_code=e.http_code, detail=e.message)


@router.delete("/modes-of-payment/{mode_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_mode_of_payment(
    mode_id: int,
    db: Session = Depends(get_db),
    service: PaymentModeService = Depends(get_payment_mode_service),
) -> Dict[str, Any]:
    """Disable a payment mode."""
    try:
        service.disable_payment_mode(mode_id)
        db.commit()
        return {"status": "disabled", "mode_of_payment_id": mode_id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
