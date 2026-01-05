"""Channels API - REST endpoints for omnichannel management.

Provides endpoints for:
- Channel CRUD (email, WhatsApp, SMS, etc.)
- Channel activation/deactivation
- Connection testing
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.services.support.channels import ChannelService
from app.services.support.types import ChannelCreate, ChannelUpdate
from app.services.support.errors import (
    ChannelConfigError,
    ChannelNotFoundError,
    ValidationError,
)

router = APIRouter()

# RBAC dependencies
channel_read_dep = Depends(Require("support:channels:read", "support:read"))
channel_write_dep = Depends(Require("support:channels:write", "support:write"))


# ---------------------------------------------------------------------------
# Service Dependency
# ---------------------------------------------------------------------------


def get_channel_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ChannelService:
    """Dependency to get a ChannelService instance."""
    return ChannelService(db, principal)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class ChannelCreateRequest(BaseModel):
    """Request to create a channel."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., description="Channel type: email, whatsapp, sms, chatwoot")
    config: Dict[str, Any] = Field(default_factory=dict)
    webhook_secret: Optional[str] = None
    is_active: bool = True
    chatwoot_inbox_id: Optional[int] = None


class ChannelUpdateRequest(BaseModel):
    """Request to update a channel."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    config: Optional[Dict[str, Any]] = None
    webhook_secret: Optional[str] = None
    is_active: Optional[bool] = None
    chatwoot_inbox_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Response Serializers
# ---------------------------------------------------------------------------


def serialize_channel(channel) -> Dict[str, Any]:
    """Serialize a channel for API response."""
    return {
        "id": channel.id,
        "name": channel.name,
        "type": channel.type,
        "config": channel.config,
        "webhook_secret": "***" if channel.webhook_secret else None,  # Mask secret
        "is_active": channel.is_active,
        "chatwoot_inbox_id": channel.chatwoot_inbox_id,
        "created_at": channel.created_at.isoformat() if channel.created_at else None,
        "updated_at": channel.updated_at.isoformat() if channel.updated_at else None,
    }


def serialize_connection_test(result) -> Dict[str, Any]:
    """Serialize a connection test result."""
    return {
        "success": result.success,
        "message": result.message,
        "latency_ms": result.latency_ms,
        "details": result.details,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    dependencies=[channel_read_dep],
)
def list_channels(
    active_only: bool = True,
    channel_type: Optional[str] = None,
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """List channels with optional filtering.

    Args:
        active_only: Only return active channels.
        channel_type: Filter by channel type.

    Returns:
        List of channels.
    """
    channels = service.list(active_only=active_only, channel_type=channel_type)
    return {
        "count": len(channels),
        "data": [serialize_channel(c) for c in channels],
    }


@router.post(
    "",
    dependencies=[channel_write_dep],
    status_code=201,
)
def create_channel(
    request: ChannelCreateRequest,
    db: Session = Depends(get_db),
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Create a new channel.

    Args:
        request: Channel data.

    Returns:
        Created channel.
    """
    try:
        data = ChannelCreate(
            name=request.name,
            type=request.type,
            config=request.config,
            webhook_secret=request.webhook_secret,
            is_active=request.is_active,
            chatwoot_inbox_id=request.chatwoot_inbox_id,
        )
        channel = service.create(data)
        db.commit()
        return serialize_channel(channel)
    except (ValidationError, ChannelConfigError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/{channel_id}",
    dependencies=[channel_read_dep],
)
def get_channel(
    channel_id: int,
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Get a channel by ID.

    Args:
        channel_id: The channel ID.

    Returns:
        Channel details.
    """
    try:
        channel = service.get(channel_id)
        return serialize_channel(channel)
    except ChannelNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/{channel_id}",
    dependencies=[channel_write_dep],
)
def update_channel(
    channel_id: int,
    request: ChannelUpdateRequest,
    db: Session = Depends(get_db),
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Update a channel.

    Args:
        channel_id: The channel ID.
        request: Update data.

    Returns:
        Updated channel.
    """
    try:
        data = ChannelUpdate(
            name=request.name,
            config=request.config,
            webhook_secret=request.webhook_secret,
            is_active=request.is_active,
            chatwoot_inbox_id=request.chatwoot_inbox_id,
        )
        channel = service.update(channel_id, data)
        db.commit()
        return serialize_channel(channel)
    except ChannelNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except (ValidationError, ChannelConfigError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/{channel_id}",
    dependencies=[channel_write_dep],
)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    service: ChannelService = Depends(get_channel_service),
) -> Response:
    """Delete a channel.

    Args:
        channel_id: The channel ID.

    Returns:
        204 No Content on success.
    """
    try:
        service.delete(channel_id)
        db.commit()
        return Response(status_code=204)
    except ChannelNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{channel_id}/activate",
    dependencies=[channel_write_dep],
)
def activate_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Activate a channel.

    Args:
        channel_id: The channel ID.

    Returns:
        Updated channel.
    """
    try:
        channel = service.activate(channel_id)
        db.commit()
        return serialize_channel(channel)
    except ChannelNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{channel_id}/deactivate",
    dependencies=[channel_write_dep],
)
def deactivate_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Deactivate a channel.

    Args:
        channel_id: The channel ID.

    Returns:
        Updated channel.
    """
    try:
        channel = service.deactivate(channel_id)
        db.commit()
        return serialize_channel(channel)
    except ChannelNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{channel_id}/test",
    dependencies=[channel_write_dep],
)
def test_connection(
    channel_id: int,
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Test channel connection.

    Args:
        channel_id: The channel ID.

    Returns:
        Connection test result.
    """
    try:
        result = service.test_connection(channel_id)
        return serialize_connection_test(result)
    except ChannelNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/by-name/{name}",
    dependencies=[channel_read_dep],
)
def get_channel_by_name(
    name: str,
    service: ChannelService = Depends(get_channel_service),
) -> Dict[str, Any]:
    """Get a channel by name.

    Args:
        name: The channel name.

    Returns:
        Channel details.
    """
    try:
        channel = service.get_by_name(name)
        return serialize_channel(channel)
    except ChannelNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
