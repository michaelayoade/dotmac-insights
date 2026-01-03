"""IP Address API endpoints.

Thin wrapper around IPAddressService for IPv4 address management.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.services.network import IPAddressService, IPv4AddressFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

from ._deps import (
    get_ip_address_service,
    RequireExplorerRead,
    handle_service_error,
)

router = APIRouter(prefix="/ip-addresses", tags=["network"])


@router.get("", dependencies=[RequireExplorerRead])
async def list_addresses(
    search: str | None = None,
    is_used: bool | None = None,
    status: str | None = None,
    network_id: int | None = None,
    module: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: IPAddressService = Depends(get_ip_address_service),
) -> Dict[str, Any]:
    """List IPv4 addresses with optional filtering."""
    filters = IPv4AddressFilters(
        search=search,
        is_used=is_used,
        status=status,
        network_id=network_id,
        module=module,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_addresses(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": a.id,
                "ip": a.ip,
                "hostname": a.hostname,
                "title": a.title,
                "is_used": a.is_used,
                "status": a.status,
                "module": a.module,
                "ipv4_network_id": a.ipv4_network_id,
                "splynx_id": a.splynx_id,
            }
            for a in result.items
        ],
    }


@router.get("/stats", dependencies=[RequireExplorerRead])
async def get_stats(
    service: IPAddressService = Depends(get_ip_address_service),
) -> Dict[str, Any]:
    """Get IP address statistics."""
    return service.get_stats()


@router.get("/{address_id}", dependencies=[RequireExplorerRead])
async def get_address(
    address_id: int,
    service: IPAddressService = Depends(get_ip_address_service),
) -> Dict[str, Any]:
    """Get an IP address by ID."""
    try:
        addr = service.get_address(address_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": addr.id,
        "ip": addr.ip,
        "hostname": addr.hostname,
        "title": addr.title,
        "is_used": addr.is_used,
        "status": addr.status,
        "module": addr.module,
        "item_id": addr.item_id,
        "ipv4_network_id": addr.ipv4_network_id,
        "external_ids": {
            "splynx_id": addr.splynx_id,
        },
    }


@router.get("/by-network/{network_id}", dependencies=[RequireExplorerRead])
async def get_addresses_for_network(
    network_id: int,
    used_only: bool = False,
    service: IPAddressService = Depends(get_ip_address_service),
) -> Dict[str, Any]:
    """Get all addresses in a specific network."""
    addresses = service.get_addresses_for_network(network_id, used_only=used_only)

    return {
        "network_id": network_id,
        "count": len(addresses),
        "data": [
            {
                "id": a.id,
                "ip": a.ip,
                "hostname": a.hostname,
                "is_used": a.is_used,
                "status": a.status,
            }
            for a in addresses
        ],
    }
