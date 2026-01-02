from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import Response
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.models.party import Party, PartyRole
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.identity import PartyService
from app.services.identity.party_types import (
    PartyFilters,
    PartyCreateData,
    PartyUpdateData,
    PartyRoleCreateData,
    PartyRoleUpdateData,
)
from app.services.types import PaginationParams

from .party_schemas import (
    PartyCreate,
    PartyUpdate,
    PartyResponse,
    PartyListResponse,
    PartyRoleCreate,
    PartyRoleResponse,
)

router = APIRouter()


def get_party_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> PartyService:
    """Create a PartyService instance for dependency injection."""
    return PartyService(db, principal)


@router.get(
    "/",
    response_model=PartyListResponse,
    dependencies=[Depends(Require("crm:read"))],
)
def list_parties(
    type: Optional[str] = Query(default=None, pattern="^(person|organization)$"),
    status: Optional[str] = Query(default=None, pattern="^(active|inactive|blocked)$"),
    search: Optional[str] = None,
    include_roles: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> PartyListResponse:
    """List parties with optional filters."""
    filters = PartyFilters(
        party_type=type,
        status=status,
        search=search,
    )
    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_parties(filters, pagination, include_roles=include_roles)
    return PartyListResponse(
        data=result.items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.post(
    "/",
    response_model=PartyResponse,
    status_code=201,
    dependencies=[Depends(Require("crm:write"))],
)
def create_party(
    payload: PartyCreate,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> PartyResponse:
    """Create a new party."""
    try:
        data = PartyCreateData(
            type=payload.type,
            name=payload.name,
            status=payload.status,
            first_name=payload.first_name,
            last_name=payload.last_name,
            legal_name=payload.legal_name,
            trading_name=payload.trading_name,
            emails=[e.model_dump() for e in payload.emails],
            phones=[p.model_dump() for p in payload.phones],
            addresses=[a.model_dump() for a in payload.addresses],
            external_ids=payload.external_ids,
            avatar_url=payload.avatar_url,
            timezone=payload.timezone,
            locale=payload.locale,
            tax_id=payload.tax_id,
            tags=payload.tags,
            custom_fields=payload.custom_fields,
            notes=payload.notes,
        )
        party = service.create_party(data)
        db.commit()
        db.refresh(party)
        return party
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/{party_id}",
    response_model=PartyResponse,
    dependencies=[Depends(Require("crm:read"))],
)
def get_party(
    party_id: int,
    include_roles: bool = False,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> PartyResponse:
    """Get a party by ID."""
    try:
        return service.get_party(party_id, include_roles=include_roles)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/{party_id}",
    response_model=PartyResponse,
    dependencies=[Depends(Require("crm:write"))],
)
def update_party(
    party_id: int,
    payload: PartyUpdate,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> PartyResponse:
    """Update a party."""
    try:
        data = PartyUpdateData(
            status=payload.status,
            name=payload.name,
            first_name=payload.first_name,
            last_name=payload.last_name,
            legal_name=payload.legal_name,
            trading_name=payload.trading_name,
            emails=[e.model_dump() for e in payload.emails] if payload.emails else None,
            phones=[p.model_dump() for p in payload.phones] if payload.phones else None,
            addresses=[a.model_dump() for a in payload.addresses] if payload.addresses else None,
            external_ids=payload.external_ids,
            avatar_url=payload.avatar_url,
            timezone=payload.timezone,
            locale=payload.locale,
            tax_id=payload.tax_id,
            tags=payload.tags,
            custom_fields=payload.custom_fields,
            notes=payload.notes,
        )
        party = service.update_party(party_id, data)
        db.commit()
        db.refresh(party)
        return party
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/{party_id}",
    status_code=204,
    dependencies=[Depends(Require("crm:write"))],
)
def delete_party(
    party_id: int,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> Response:
    """Delete a party (soft delete)."""
    try:
        service.delete_party(party_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# PARTY ROLES
# =============================================================================

@router.get(
    "/{party_id}/roles",
    response_model=list[PartyRoleResponse],
    dependencies=[Depends(Require("crm:read"))],
)
def list_party_roles(
    party_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> list[PartyRoleResponse]:
    """List roles for a party."""
    try:
        return list(service.list_roles(party_id, active_only=active_only))
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{party_id}/roles",
    response_model=PartyRoleResponse,
    status_code=201,
    dependencies=[Depends(Require("crm:write"))],
)
def add_party_role(
    party_id: int,
    payload: PartyRoleCreate,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> PartyRoleResponse:
    """Add a role to a party."""
    try:
        data = PartyRoleCreateData(
            role=payload.role,
            status=payload.status,
            scope_party_id=payload.scope_party_id,
            owner_party_id=payload.owner_party_id,
        )
        role = service.add_role(party_id, data)
        db.commit()
        db.refresh(role)
        return role
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/{party_id}/roles/{role_id}",
    status_code=204,
    dependencies=[Depends(Require("crm:write"))],
)
def remove_party_role(
    party_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    service: PartyService = Depends(get_party_service),
) -> Response:
    """Remove a role from a party."""
    try:
        service.remove_role(party_id, role_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
