"""POP API endpoints.

Thin wrapper around PopService for Points of Presence management.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.network import PopService, PopFilters, PopCreateData, PopUpdateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

from ._deps import (
    get_pop_service,
    get_router_service,
    RequireExplorerRead,
    RequireNetworkWrite,
    handle_service_error,
)

router = APIRouter(prefix="/pops", tags=["network"])


@router.get("", dependencies=[RequireExplorerRead])
async def list_pops(
    search: str | None = None,
    city: str | None = None,
    state: str | None = None,
    is_active: bool | None = None,
    has_routers: bool | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: PopService = Depends(get_pop_service),
) -> Dict[str, Any]:
    """List POPs with optional filtering."""
    filters = PopFilters(
        search=search,
        city=city,
        state=state,
        is_active=is_active,
        has_routers=has_routers,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_pops(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "city": p.city,
                "state": p.state,
                "is_active": p.is_active,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "splynx_id": p.splynx_id,
            }
            for p in result.items
        ],
    }


@router.get("/cities", dependencies=[RequireExplorerRead])
async def list_cities(
    service: PopService = Depends(get_pop_service),
) -> Dict[str, Any]:
    """Get unique cities for filter dropdown."""
    cities = service.get_cities()
    return {"cities": cities}


@router.get("/states", dependencies=[RequireExplorerRead])
async def list_states(
    service: PopService = Depends(get_pop_service),
) -> Dict[str, Any]:
    """Get unique states for filter dropdown."""
    states = service.get_states()
    return {"states": states}


@router.get("/overview", dependencies=[RequireExplorerRead])
async def get_overview(
    service: PopService = Depends(get_pop_service),
) -> Dict[str, Any]:
    """Get POP overview statistics."""
    return service.get_overview_stats()


@router.get("/{pop_id}", dependencies=[RequireExplorerRead])
async def get_pop(
    pop_id: int,
    service: PopService = Depends(get_pop_service),
) -> Dict[str, Any]:
    """Get a POP by ID with statistics."""
    try:
        pop = service.get_pop(pop_id)
        stats = service.get_pop_stats(pop_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": pop.id,
        "name": pop.name,
        "code": pop.code,
        "address": pop.address,
        "city": pop.city,
        "state": pop.state,
        "latitude": pop.latitude,
        "longitude": pop.longitude,
        "is_active": pop.is_active,
        "external_ids": {
            "splynx_id": pop.splynx_id,
        },
        "metrics": {
            "customer_count": stats.customer_count,
            "active_subscriptions": stats.active_subscriptions,
            "router_count": stats.router_count,
            "mrr": str(stats.mrr),
        },
    }


@router.get("/{pop_id}/routers", dependencies=[RequireExplorerRead])
async def get_pop_routers(
    pop_id: int,
    pop_service: PopService = Depends(get_pop_service),
    router_service=Depends(get_router_service),
) -> Dict[str, Any]:
    """Get routers at a specific POP."""
    try:
        # Verify POP exists
        pop_service.get_pop(pop_id)
        routers = router_service.get_routers_for_pop(pop_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "pop_id": pop_id,
        "routers": [
            {
                "id": r.id,
                "title": r.title,
                "ip": r.ip,
                "nas_ip": r.nas_ip,
                "status": r.status,
                "model": r.model,
            }
            for r in routers
        ],
    }


@router.post("", dependencies=[RequireNetworkWrite])
async def create_pop(
    name: str,
    code: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    is_active: bool = True,
    service: PopService = Depends(get_pop_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new POP."""
    try:
        data = PopCreateData(
            name=name,
            code=code,
            address=address,
            city=city,
            state=state,
            latitude=latitude,
            longitude=longitude,
            is_active=is_active,
        )
        pop = service.create_pop(data)
        db.commit()
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": pop.id, "name": pop.name}


@router.patch("/{pop_id}", dependencies=[RequireNetworkWrite])
async def update_pop(
    pop_id: int,
    name: str | None = None,
    code: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    is_active: bool | None = None,
    service: PopService = Depends(get_pop_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a POP."""
    try:
        data = PopUpdateData(
            name=name,
            code=code,
            address=address,
            city=city,
            state=state,
            latitude=latitude,
            longitude=longitude,
            is_active=is_active,
        )
        pop = service.update_pop(pop_id, data)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": pop.id, "name": pop.name}


@router.delete("/{pop_id}", dependencies=[RequireNetworkWrite])
async def delete_pop(
    pop_id: int,
    service: PopService = Depends(get_pop_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivate a POP (soft delete)."""
    try:
        service.delete_pop(pop_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "pop_id": pop_id}
