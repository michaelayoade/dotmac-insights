"""
Sessions API

RADIUS/NAS session management endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    SessionService,
    SessionFilters,
    DisconnectRequest,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

router = APIRouter()


class DisconnectSchema(BaseModel):
    """Schema for disconnect request."""
    reason: str = "admin_disconnect"


@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def list_sessions(
    username: Optional[str] = Query(None, description="Filter by username"),
    nas_ip: Optional[str] = Query(None, description="Filter by NAS IP"),
    framed_ip: Optional[str] = Query(None, description="Filter by framed IP"),
    subscription_id: Optional[int] = Query(None, description="Filter by subscription"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    active_only: bool = Query(True, description="Only show active sessions"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List RADIUS sessions.
    """
    service = SessionService(db, principal)

    filters = SessionFilters(
        username=username,
        nas_ip=nas_ip,
        framed_ip=framed_ip,
        subscription_id=subscription_id,
        party_id=party_id,
        active_only=active_only,
    )

    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = service.list_sessions(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_session(s) for s in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/stats", dependencies=[Depends(Require("subscriptions:read"))])
async def get_session_stats(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get session statistics.
    """
    service = SessionService(db, principal)
    stats = service.get_stats()

    return {
        "total_active": stats.total_active,
        "total_today": stats.total_today,
        "total_upload_gb": stats.total_upload_gb,
        "total_download_gb": stats.total_download_gb,
        "avg_session_duration_minutes": stats.avg_session_duration_minutes,
        "unique_users": stats.unique_users,
        "sessions_by_nas": stats.sessions_by_nas,
        "top_users_by_traffic": stats.top_users_by_traffic,
    }


@router.get("/{subscription_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription_sessions(
    subscription_id: int = Path(..., description="Subscription ID"),
    active_only: bool = Query(True, description="Only show active sessions"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get sessions for a subscription.
    """
    service = SessionService(db, principal)

    result = service.list_sessions(
        filters=SessionFilters(
            subscription_id=subscription_id,
            active_only=active_only,
        ),
        pagination=PaginationParams(
            offset=(page - 1) * per_page,
            limit=per_page,
        ),
    )

    return {
        "subscription_id": subscription_id,
        "items": [_serialize_session(s) for s in result.items],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/{session_id}/disconnect", dependencies=[Depends(Require("subscriptions:update"))])
async def disconnect_session(
    session_id: str = Path(..., description="Session ID"),
    data: DisconnectSchema = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Disconnect a session.
    """
    service = SessionService(db, principal)

    try:
        result = service.disconnect(
            DisconnectRequest(
                session_id=session_id,
                reason=data.reason if data else "admin_disconnect",
            )
        )
        db.commit()

        return {
            "success": result.success,
            "session_id": result.session_id,
            "message": result.message,
            "error_code": result.error_code,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/disconnect-by-username", dependencies=[Depends(Require("subscriptions:update"))])
async def disconnect_by_username(
    username: str = Query(..., description="Username to disconnect"),
    reason: str = Query("admin_disconnect", description="Disconnect reason"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Disconnect all sessions for a username.
    """
    service = SessionService(db, principal)

    result = service.disconnect(
        DisconnectRequest(
            username=username,
            reason=reason,
        )
    )
    db.commit()

    return {
        "success": result.success,
        "username": result.username,
        "message": result.message,
    }


def _serialize_session(session) -> Dict[str, Any]:
    """Serialize session record."""
    return {
        "session_id": session.session_id,
        "username": session.username,
        "nas_ip": session.nas_ip,
        "nas_port_id": session.nas_port_id,
        "framed_ip": session.framed_ip,
        "calling_station_id": session.calling_station_id,
        "called_station_id": session.called_station_id,
        "session_start": session.session_start.isoformat() if session.session_start else None,
        "session_duration_seconds": session.session_duration_seconds,
        "input_octets": session.input_octets,
        "output_octets": session.output_octets,
        "subscription_id": session.subscription_id,
        "party_id": session.party_id,
        "plan_name": session.plan_name,
    }
