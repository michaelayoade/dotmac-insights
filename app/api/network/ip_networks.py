"""IP Network API endpoints.

Thin wrapper around IPv4NetworkService and IPv6NetworkService.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.services.network import (
    IPv4NetworkService,
    IPv6NetworkService,
    IPv4NetworkFilters,
    IPv6NetworkFilters,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

from ._deps import (
    get_ipv4_network_service,
    get_ipv6_network_service,
    get_ip_address_service,
    RequireExplorerRead,
    handle_service_error,
)

router = APIRouter(prefix="/ip-networks", tags=["network"])


# =============================================================================
# IPv4 Networks
# =============================================================================

@router.get("/v4", dependencies=[RequireExplorerRead])
async def list_ipv4_networks(
    search: str | None = None,
    network_type: str | None = None,
    type_of_usage: str | None = None,
    location_id: int | None = None,
    parent_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: IPv4NetworkService = Depends(get_ipv4_network_service),
) -> Dict[str, Any]:
    """List IPv4 networks with optional filtering."""
    filters = IPv4NetworkFilters(
        search=search,
        network_type=network_type,
        type_of_usage=type_of_usage,
        location_id=location_id,
        parent_id=parent_id,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_networks(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": n.id,
                "network": n.network,
                "title": n.title,
                "network_type": n.network_type,
                "type_of_usage": n.type_of_usage,
                "parent_id": n.parent_id,
                "location_id": n.location_id,
                "splynx_id": n.splynx_id,
            }
            for n in result.items
        ],
    }


@router.get("/v4/stats", dependencies=[RequireExplorerRead])
async def get_ipv4_stats(
    service: IPv4NetworkService = Depends(get_ipv4_network_service),
) -> Dict[str, Any]:
    """Get IPv4 network statistics."""
    return service.get_stats()


@router.get("/v4/{network_id}", dependencies=[RequireExplorerRead])
async def get_ipv4_network(
    network_id: int,
    service: IPv4NetworkService = Depends(get_ipv4_network_service),
    ip_service=Depends(get_ip_address_service),
) -> Dict[str, Any]:
    """Get an IPv4 network by ID with address statistics."""
    try:
        network = service.get_network(network_id)
        children = service.get_child_networks(network_id)
        ip_stats = ip_service.get_stats_by_network(network_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": network.id,
        "network": network.network,
        "title": network.title,
        "network_type": network.network_type,
        "type_of_usage": network.type_of_usage,
        "parent_id": network.parent_id,
        "location_id": network.location_id,
        "external_ids": {
            "splynx_id": network.splynx_id,
        },
        "ip_stats": ip_stats,
        "children": [
            {
                "id": c.id,
                "network": c.network,
                "title": c.title,
                "network_type": c.network_type,
            }
            for c in children
        ],
    }


# =============================================================================
# IPv6 Networks
# =============================================================================

@router.get("/v6", dependencies=[RequireExplorerRead])
async def list_ipv6_networks(
    search: str | None = None,
    network_type: str | None = None,
    type_of_usage: str | None = None,
    location_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: IPv6NetworkService = Depends(get_ipv6_network_service),
) -> Dict[str, Any]:
    """List IPv6 networks with optional filtering."""
    filters = IPv6NetworkFilters(
        search=search,
        network_type=network_type,
        type_of_usage=type_of_usage,
        location_id=location_id,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_networks(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": n.id,
                "network": n.network,
                "title": n.title,
                "network_type": n.network_type,
                "type_of_usage": n.type_of_usage,
                "location_id": n.location_id,
                "splynx_id": n.splynx_id,
            }
            for n in result.items
        ],
    }


@router.get("/v6/stats", dependencies=[RequireExplorerRead])
async def get_ipv6_stats(
    service: IPv6NetworkService = Depends(get_ipv6_network_service),
) -> Dict[str, Any]:
    """Get IPv6 network statistics."""
    return service.get_stats()


@router.get("/v6/{network_id}", dependencies=[RequireExplorerRead])
async def get_ipv6_network(
    network_id: int,
    service: IPv6NetworkService = Depends(get_ipv6_network_service),
) -> Dict[str, Any]:
    """Get an IPv6 network by ID."""
    try:
        network = service.get_network(network_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": network.id,
        "network": network.network,
        "title": network.title,
        "network_type": network.network_type,
        "type_of_usage": network.type_of_usage,
        "location_id": network.location_id,
        "external_ids": {
            "splynx_id": network.splynx_id,
        },
    }
