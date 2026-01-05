"""Network API shared dependencies.

Service providers and common utilities for Network API routes.
"""
from __future__ import annotations

from typing import NoReturn

from fastapi import Depends, HTTPException

from app.database import get_db
from app.auth import get_current_principal, Principal
from sqlalchemy.orm import Session

from app.services.network import (
    PopService,
    RouterService,
    IPv4NetworkService,
    IPv6NetworkService,
    IPAddressService,
)
from app.services.errors import NotFoundError, ValidationError, ConflictError


# =============================================================================
# Permission dependencies
# =============================================================================

from app.auth import Require

RequireNetworkRead = Depends(Require("network:read"))
RequireNetworkWrite = Depends(Require("network:write"))
RequireExplorerRead = Depends(Require("explorer:read"))
RequireAnalyticsRead = Depends(Require("analytics:read"))


# =============================================================================
# Service providers
# =============================================================================

def get_pop_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> PopService:
    """Provide PopService instance."""
    return PopService(db, principal)


def get_router_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RouterService:
    """Provide RouterService instance."""
    return RouterService(db, principal)


def get_ipv4_network_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> IPv4NetworkService:
    """Provide IPv4NetworkService instance."""
    return IPv4NetworkService(db, principal)


def get_ipv6_network_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> IPv6NetworkService:
    """Provide IPv6NetworkService instance."""
    return IPv6NetworkService(db, principal)


def get_ip_address_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> IPAddressService:
    """Provide IPAddressService instance."""
    return IPAddressService(db, principal)


# =============================================================================
# Error handling
# =============================================================================

def handle_service_error(e: Exception) -> NoReturn:
    """Convert service errors to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=422, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail=str(e))
