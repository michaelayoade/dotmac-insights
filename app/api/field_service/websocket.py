"""
Field Service WebSocket API

Real-time updates for dispatch board and technician tracking.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from typing import Dict, List, Any, Optional, Set
import json
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
import structlog

from app.auth import (
    AUTH_COOKIE_NAME,
    Principal,
    get_or_create_user,
    get_origin_from_websocket,
    is_token_denylisted,
    validate_origin,
    verify_jwt,
    verify_service_token,
)
from app.config import settings
from app.database import get_db

ws_logger = structlog.get_logger("field_service.websocket")

router = APIRouter()


class FieldServiceConnectionManager:
    """Manages WebSocket connections for field service real-time updates."""

    def __init__(self) -> None:
        # Connections grouped by channel
        self.active_connections: Dict[str, List[WebSocket]] = {
            "dispatch": [],  # Dispatch board updates
            "orders": [],    # Order status changes
            "tracking": [],  # Technician location tracking
        }
        # User-specific connections (by user_id)
        self.user_connections: Dict[str, WebSocket] = {}
        # Team-specific connections (by team_id)
        self.team_connections: Dict[int, List[WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channel: str,
        user_id: Optional[str] = None,
        team_id: Optional[int] = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        # Add to channel
        if channel in self.active_connections:
            self.active_connections[channel].append(websocket)

        # Track user-specific connection
        if user_id:
            self.user_connections[user_id] = websocket

        # Track team-specific connection
        if team_id:
            if team_id not in self.team_connections:
                self.team_connections[team_id] = []
            self.team_connections[team_id].append(websocket)

    def disconnect(
        self,
        websocket: WebSocket,
        channel: str,
        user_id: Optional[str] = None,
        team_id: Optional[int] = None,
    ) -> None:
        """Remove a WebSocket connection."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)

        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]

        if team_id and team_id in self.team_connections:
            if websocket in self.team_connections[team_id]:
                self.team_connections[team_id].remove(websocket)

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]) -> None:
        """Broadcast message to all connections in a channel."""
        if channel not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.active_connections[channel].remove(conn)

    async def broadcast_to_team(self, team_id: int, message: Dict[str, Any]) -> None:
        """Broadcast message to all connections for a specific team."""
        if team_id not in self.team_connections:
            return

        disconnected = []
        for connection in self.team_connections[team_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.team_connections[team_id].remove(conn)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific user."""
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except Exception:
                del self.user_connections[user_id]

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "channels": {
                channel: len(conns)
                for channel, conns in self.active_connections.items()
            },
            "users_connected": len(self.user_connections),
            "teams_with_connections": len(self.team_connections),
        }


# Global connection manager
manager = FieldServiceConnectionManager()


# Event types for field service
class FieldServiceEvent:
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ORDER_DISPATCHED = "order_dispatched"
    ORDER_STATUS_CHANGED = "order_status_changed"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    TECHNICIAN_EN_ROUTE = "technician_en_route"
    TECHNICIAN_ARRIVED = "technician_arrived"
    TECHNICIAN_LOCATION_UPDATE = "technician_location_update"
    SCHEDULE_CONFLICT = "schedule_conflict"


async def broadcast_order_event(
    event_type: str,
    order_data: Dict[str, Any],
    team_id: Optional[int] = None,
    technician_id: Optional[int] = None,
):
    """Broadcast an order event to relevant channels."""
    message = {
        "event": event_type,
        "data": order_data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Broadcast to dispatch channel
    await manager.broadcast_to_channel("dispatch", message)

    # Broadcast to orders channel
    await manager.broadcast_to_channel("orders", message)

    # If team-specific, also broadcast to team
    if team_id:
        await manager.broadcast_to_team(team_id, message)

    # If technician-specific, send to technician
    if technician_id:
        await manager.send_to_user(f"tech_{technician_id}", message)


async def broadcast_location_update(
    technician_id: int,
    location: Dict[str, Any],
    order_id: Optional[int] = None,
):
    """Broadcast technician location update."""
    message = {
        "event": FieldServiceEvent.TECHNICIAN_LOCATION_UPDATE,
        "data": {
            "technician_id": technician_id,
            "location": location,
            "order_id": order_id,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    await manager.broadcast_to_channel("tracking", message)


# =============================================================================
# WEBSOCKET AUTHENTICATION
# =============================================================================


async def authenticate_field_service_websocket(
    websocket: WebSocket,
    db: Session,
) -> Optional[Principal]:
    """Authenticate WebSocket via bearer token or cookie.

    Returns Principal if authenticated, None otherwise.
    """
    token: Optional[str] = None

    # Try Authorization header first
    auth_header = websocket.headers.get("authorization")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()

    # Fall back to cookie
    if not token:
        token = websocket.cookies.get(AUTH_COOKIE_NAME)

    if not token:
        return None

    try:
        # Service token (no dots)
        if "." not in token:
            service_token = await verify_service_token(token, db)
            return Principal(
                type="service_token",
                id=service_token.id,
                external_id=None,
                email=None,
                name=service_token.name,
                is_superuser=False,
                scopes=set(service_token.scope_list),
            )

        # JWT
        claims = await verify_jwt(token)

        if claims.jti and await is_token_denylisted(claims.jti, db):
            return None

        user = await get_or_create_user(claims, db)
        if not user.is_active:
            return None

        principal_scopes = user.all_permissions
        is_superuser = user.is_superuser
        if settings.e2e_jwt_secret and settings.e2e_auth_enabled and claims.scopes is not None:
            principal_scopes = set(claims.scopes or [])
            is_superuser = False

        return Principal(
            type="user",
            id=user.id,
            external_id=user.external_id,
            email=user.email,
            name=user.name,
            is_superuser=is_superuser,
            scopes=principal_scopes,
            raw_claims=claims.model_dump(),
        )
    except HTTPException:
        return None


# =============================================================================
# WEBSOCKET ENDPOINTS
# =============================================================================

@router.websocket("/ws/dispatch")
async def dispatch_websocket(
    websocket: WebSocket,
    team_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for dispatch board real-time updates.

    Security:
    - Requires valid Origin header matching CORS allowed origins (CSWSH protection)
    - Requires valid JWT/service token with field-service:read scope
    """
    # CSWSH Protection: Validate Origin header
    origin = get_origin_from_websocket(websocket)
    if not validate_origin(origin, settings.cors_origins_list):
        ws_logger.warning(
            "websocket_origin_rejected",
            origin=origin,
            channel="dispatch",
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    principal = await authenticate_field_service_websocket(websocket, db)
    if not principal or not principal.has_scope("field-service:read"):
        ws_logger.warning(
            "websocket_auth_failed",
            origin=origin,
            channel="dispatch",
            has_principal=principal is not None,
        )
        await websocket.close(code=1008, reason="Authentication required")
        return

    ws_logger.info(
        "websocket_connected",
        origin=origin,
        channel="dispatch",
        principal_type=principal.type,
        principal_id=principal.id,
        team_id=team_id,
    )

    await manager.connect(websocket, "dispatch", team_id=team_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "event": "connected",
            "channel": "dispatch",
            "team_id": team_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Send ping every 30 seconds
                )
                # Handle incoming messages (e.g., subscribe to specific orders)
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, "dispatch", team_id=team_id)


@router.websocket("/ws/orders")
async def orders_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for order status updates.

    Security:
    - Requires valid Origin header matching CORS allowed origins (CSWSH protection)
    - Requires valid JWT/service token with field-service:read scope
    """
    # CSWSH Protection: Validate Origin header
    origin = get_origin_from_websocket(websocket)
    if not validate_origin(origin, settings.cors_origins_list):
        ws_logger.warning(
            "websocket_origin_rejected",
            origin=origin,
            channel="orders",
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    principal = await authenticate_field_service_websocket(websocket, db)
    if not principal or not principal.has_scope("field-service:read"):
        ws_logger.warning(
            "websocket_auth_failed",
            origin=origin,
            channel="orders",
            has_principal=principal is not None,
        )
        await websocket.close(code=1008, reason="Authentication required")
        return

    ws_logger.info(
        "websocket_connected",
        origin=origin,
        channel="orders",
        principal_type=principal.type,
        principal_id=principal.id,
    )

    await manager.connect(websocket, "orders")

    try:
        await websocket.send_json({
            "event": "connected",
            "channel": "orders",
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, "orders")


@router.websocket("/ws/tracking")
async def tracking_websocket(
    websocket: WebSocket,
    technician_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for technician location tracking.

    Security:
    - Requires valid Origin header matching CORS allowed origins (CSWSH protection)
    - Requires valid JWT/service token with field-service:read or field-service:mobile scope
    """
    # CSWSH Protection: Validate Origin header
    origin = get_origin_from_websocket(websocket)
    if not validate_origin(origin, settings.cors_origins_list):
        ws_logger.warning(
            "websocket_origin_rejected",
            origin=origin,
            channel="tracking",
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    principal = await authenticate_field_service_websocket(websocket, db)
    # Allow either field-service:read (dispatchers) or field-service:mobile (technicians)
    if not principal or not (
        principal.has_scope("field-service:read") or principal.has_scope("field-service:mobile")
    ):
        ws_logger.warning(
            "websocket_auth_failed",
            origin=origin,
            channel="tracking",
            has_principal=principal is not None,
        )
        await websocket.close(code=1008, reason="Authentication required")
        return

    ws_logger.info(
        "websocket_connected",
        origin=origin,
        channel="tracking",
        principal_type=principal.type,
        principal_id=principal.id,
        technician_id=technician_id,
    )

    user_id = f"tech_{technician_id}" if technician_id else None
    await manager.connect(websocket, "tracking", user_id=user_id)

    try:
        await websocket.send_json({
            "event": "connected",
            "channel": "tracking",
            "technician_id": technician_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                try:
                    message = json.loads(data)
                    # Handle location updates from technicians
                    if message.get("type") == "location_update":
                        await broadcast_location_update(
                            technician_id=message.get("technician_id", technician_id),
                            location=message.get("location", {}),
                            order_id=message.get("order_id"),
                        )
                    elif message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, "tracking", user_id=user_id)


@router.get("/ws/stats")
async def get_websocket_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics."""
    return manager.get_stats()
