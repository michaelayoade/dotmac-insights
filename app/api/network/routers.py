"""Router API endpoints.

Thin wrapper around RouterService for router/NAS management.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.network import (
    RouterService,
    RouterFilters,
    RouterCreateData,
    RouterUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

from ._deps import (
    get_router_service,
    get_pop_service,
    RequireExplorerRead,
    RequireNetworkWrite,
    handle_service_error,
)

router = APIRouter(prefix="/routers", tags=["network"])


@router.get("", dependencies=[RequireExplorerRead])
async def list_routers(
    search: str | None = None,
    pop_id: int | None = None,
    status: str | None = None,
    nas_type: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: RouterService = Depends(get_router_service),
) -> Dict[str, Any]:
    """List routers with optional filtering."""
    filters = RouterFilters(
        search=search,
        pop_id=pop_id,
        status=status,
        nas_type=nas_type,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_routers(filters, pagination, include_pop=True)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "title": r.title,
                "model": r.model,
                "ip": r.ip,
                "nas_ip": r.nas_ip,
                "nas_type": r.nas_type,
                "pop_id": r.pop_id,
                "pop_name": r.pop.name if r.pop else None,
                "status": r.status,
                "splynx_id": r.splynx_id,
            }
            for r in result.items
        ],
    }


@router.get("/overview", dependencies=[RequireExplorerRead])
async def get_overview(
    service: RouterService = Depends(get_router_service),
) -> Dict[str, Any]:
    """Get router overview statistics."""
    return service.get_overview_stats()


@router.get("/{router_id}", dependencies=[RequireExplorerRead])
async def get_router(
    router_id: int,
    service: RouterService = Depends(get_router_service),
) -> Dict[str, Any]:
    """Get a router by ID with statistics."""
    try:
        router_obj = service.get_router(router_id, include_pop=True)
        stats = service.get_router_stats(router_id)
    except NotFoundError as e:
        handle_service_error(e)

    pop = None
    if router_obj.pop:
        pop = {"id": router_obj.pop.id, "name": router_obj.pop.name}

    return {
        "id": router_obj.id,
        "title": router_obj.title,
        "model": router_obj.model,
        "ip": router_obj.ip,
        "nas_ip": router_obj.nas_ip,
        "nas_type": router_obj.nas_type,
        "address": router_obj.address,
        "gps": router_obj.gps,
        "status": router_obj.status,
        "configuration": {
            "authorization_method": router_obj.authorization_method,
            "accounting_method": router_obj.accounting_method,
            "radius_coa_port": router_obj.radius_coa_port,
            "radius_accounting_interval": router_obj.radius_accounting_interval,
            "api_port": router_obj.api_port,
            "ssh_port": router_obj.ssh_port,
        },
        "external_ids": {
            "splynx_id": router_obj.splynx_id,
            "location_id": router_obj.location_id,
        },
        "pop": pop,
        "metrics": {
            "active_subscriptions": stats.active_subscriptions,
            "total_subscriptions": stats.total_subscriptions,
        },
    }


@router.post("", dependencies=[RequireNetworkWrite])
async def create_router(
    title: str,
    ip: str | None = None,
    nas_ip: str | None = None,
    nas_type: int | None = None,
    model: str | None = None,
    pop_id: int | None = None,
    status: str | None = None,
    service: RouterService = Depends(get_router_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new router."""
    try:
        data = RouterCreateData(
            title=title,
            ip=ip,
            nas_ip=nas_ip,
            nas_type=nas_type,
            model=model,
            pop_id=pop_id,
            status=status,
        )
        router_obj = service.create_router(data)
        db.commit()
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": router_obj.id, "title": router_obj.title}


@router.patch("/{router_id}", dependencies=[RequireNetworkWrite])
async def update_router(
    router_id: int,
    title: str | None = None,
    ip: str | None = None,
    nas_ip: str | None = None,
    nas_type: int | None = None,
    model: str | None = None,
    pop_id: int | None = None,
    status: str | None = None,
    service: RouterService = Depends(get_router_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a router."""
    try:
        data = RouterUpdateData(
            title=title,
            ip=ip,
            nas_ip=nas_ip,
            nas_type=nas_type,
            model=model,
            pop_id=pop_id,
            status=status,
        )
        router_obj = service.update_router(router_id, data)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": router_obj.id, "title": router_obj.title}
