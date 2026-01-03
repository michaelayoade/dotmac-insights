"""
Provisioning API

Provisioning logs, status, and router testing endpoints.
"""
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    ProvisioningService,
    ProvisioningLogFilters,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PROVISIONING LOGS
# =============================================================================

@router.get("/logs", dependencies=[Depends(Require("subscriptions:read"))])
async def list_provisioning_logs(
    subscription_id: Optional[int] = Query(None, description="Filter by subscription"),
    router_id: Optional[int] = Query(None, description="Filter by router"),
    action: Optional[str] = Query(None, description="Filter by action (provision, deprovision, disconnect, update)"),
    status: Optional[str] = Query(None, description="Filter by status (pending, success, failed)"),
    access_method: Optional[str] = Query(None, description="Filter by access method"),
    triggered_by: Optional[str] = Query(None, description="Filter by who triggered"),
    failed_only: bool = Query(False, description="Only show failed operations"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List provisioning logs with filters.

    Returns a paginated list of provisioning operations including
    successful, failed, and pending operations.
    """
    service = ProvisioningService(db, principal)

    filters = ProvisioningLogFilters(
        subscription_id=subscription_id,
        router_id=router_id,
        action=action,
        status=status,
        access_method=access_method,
        triggered_by=triggered_by,
        failed_only=failed_only,
        date_from=date_from,
        date_to=date_to,
    )

    result = service.list_logs(
        filters=filters,
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "items": [_serialize_log(log) for log in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
        "pages": (result.total + per_page - 1) // per_page,
    }


@router.get("/logs/{log_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_provisioning_log(
    log_id: int = Path(..., description="Provisioning log ID"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get provisioning log details.

    Returns the full log entry including request/response data
    and error details if applicable.
    """
    service = ProvisioningService(db, principal)

    try:
        log = service.get_log(log_id)
        return _serialize_log(log, include_details=True)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/logs/{log_id}/retry", dependencies=[Depends(Require("subscriptions:update"))])
async def retry_provisioning(
    log_id: int = Path(..., description="Provisioning log ID to retry"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Retry a failed provisioning operation.

    This creates a new provisioning task based on the original
    failed operation. Only failed operations can be retried,
    and there's a maximum retry limit.
    """
    service = ProvisioningService(db, principal)

    try:
        result = service.retry_failed(log_id)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return {
            "success": True,
            "message": result.message,
            "action": result.action,
            "new_log_id": result.log_id,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats", dependencies=[Depends(Require("subscriptions:read"))])
async def get_provisioning_stats(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get provisioning statistics.

    Returns stats including:
    - Today's operations (total, success, failed)
    - Success rate
    - Pending and retryable counts
    - Breakdown by action type
    - Average duration
    """
    service = ProvisioningService(db, principal)
    return service.get_stats()


# =============================================================================
# ROUTER TESTING
# =============================================================================

@router.post("/test-router/{router_id}", dependencies=[Depends(Require("subscriptions:update"))])
async def test_router_connection(
    router_id: int = Path(..., description="Router ID to test"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Test connection to a router.

    This attempts to connect to the router and retrieve basic
    information like RouterOS version and uptime.
    """
    service = ProvisioningService(db, principal)

    try:
        result = service.test_router_connection(router_id)
        return {
            "router_id": result.router_id,
            "router_title": result.router_title,
            "success": result.success,
            "message": result.message,
            "routeros_version": result.routeros_version,
            "uptime": result.uptime,
            "response_time_ms": result.response_time_ms,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# HELPERS
# =============================================================================

def _serialize_log(log, include_details: bool = False) -> Dict[str, Any]:
    """Serialize provisioning log to dict."""
    data = {
        "id": log.id,
        "subscription_id": log.subscription_id,
        "router_id": log.router_id,
        "action": log.action.value if log.action else None,
        "status": log.status.value if log.status else None,
        "access_method": log.access_method,
        "triggered_by": log.triggered_by,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        "duration_ms": log.duration_ms,
        "retry_count": log.retry_count,
    }

    if include_details:
        data["request_data"] = log.request_data
        data["response_data"] = log.response_data
        data["error_message"] = log.error_message
        data["error_details"] = log.error_details
        data["max_retries"] = log.max_retries
        data["can_retry"] = (
            log.status and log.status.value == "failed" and
            log.retry_count < (log.max_retries or 3)
        )

    return data
