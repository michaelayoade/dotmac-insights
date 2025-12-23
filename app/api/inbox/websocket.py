"""
Inbox WebSocket API

Real-time updates for inbox conversations, messages, and stats.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set, Any, Optional
import json
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

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
import structlog

ws_logger = structlog.get_logger("inbox.websocket")
from app.database import get_db
from app.models.omni import OmniConversation

router = APIRouter()


class InboxConnectionManager:
    """Manages WebSocket connections for inbox real-time updates."""

    def __init__(self) -> None:
        # Connections grouped by channel
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "stats": set(),         # Dashboard stats updates
            "conversations": set(), # Conversation updates
            "messages": set(),      # New message notifications
        }
        # User-specific connections (by user_id)
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # Agent-specific connections (by agent_id)
        self.agent_connections: Dict[int, Set[WebSocket]] = {}
        # Track connection metadata for cleanup
        self.connection_channels: Dict[WebSocket, Set[str]] = {}
        self.connection_users: Dict[WebSocket, str] = {}
        self.connection_agents: Dict[WebSocket, int] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channel: str,
        user_id: Optional[str] = None,
        agent_id: Optional[int] = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        # Add to channel
        if channel in self.active_connections:
            self.active_connections[channel].add(websocket)
            self.connection_channels.setdefault(websocket, set()).add(channel)

        # Track user-specific connection
        if user_id:
            self.user_connections.setdefault(user_id, set()).add(websocket)
            self.connection_users[websocket] = user_id

        # Track agent-specific connection
        if agent_id:
            self.agent_connections.setdefault(agent_id, set()).add(websocket)
            self.connection_agents[websocket] = agent_id

    def subscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Subscribe a connection to an additional channel."""
        if channel not in self.active_connections:
            return False
        if websocket not in self.active_connections[channel]:
            self.active_connections[channel].add(websocket)
            self.connection_channels.setdefault(websocket, set()).add(channel)
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from all tracking structures."""
        channels = self.connection_channels.pop(websocket, set())
        for channel in channels:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)

        user_id = self.connection_users.pop(websocket, None)
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        agent_id = self.connection_agents.pop(websocket, None)
        if agent_id is not None and agent_id in self.agent_connections:
            self.agent_connections[agent_id].discard(websocket)
            if not self.agent_connections[agent_id]:
                del self.agent_connections[agent_id]

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]) -> None:
        """Broadcast message to all connections in a channel."""
        if channel not in self.active_connections:
            return

        disconnected = []
        for connection in list(self.active_connections[channel]):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_agent(self, agent_id: int, message: Dict[str, Any]) -> None:
        """Broadcast message to all connections for a specific agent."""
        if agent_id not in self.agent_connections:
            return

        disconnected = []
        for connection in list(self.agent_connections[agent_id]):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific user."""
        if user_id in self.user_connections:
            for connection in list(self.user_connections[user_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(connection)

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "channels": {
                channel: len(conns)
                for channel, conns in self.active_connections.items()
            },
            "users_connected": len(self.user_connections),
            "agents_with_connections": len(self.agent_connections),
        }


# Global connection manager
manager = InboxConnectionManager()


# Event types for inbox
class InboxEvent:
    STATS_UPDATE = "stats_update"
    CONVERSATION_UPDATE = "conversation_update"
    CONVERSATION_ASSIGNED = "conversation_assigned"
    NEW_MESSAGE = "new_message"
    MESSAGE_READ = "message_read"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"


async def broadcast_stats_update(stats: Dict[str, Any]) -> None:
    """Broadcast updated inbox stats to all stats subscribers."""
    message = {
        "event": InboxEvent.STATS_UPDATE,
        "data": stats,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast_to_channel("stats", message)


async def broadcast_conversation_update(
    conversation_data: Dict[str, Any],
    assigned_agent_id: Optional[int] = None,
) -> None:
    """Broadcast a conversation update."""
    message = {
        "event": InboxEvent.CONVERSATION_UPDATE,
        "data": conversation_data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Broadcast to conversations channel
    await manager.broadcast_to_channel("conversations", message)

    # If assigned to agent, also notify them
    if assigned_agent_id:
        await manager.broadcast_to_agent(assigned_agent_id, message)


async def broadcast_new_message(
    message_data: Dict[str, Any],
    conversation_id: int,
    assigned_agent_id: Optional[int] = None,
) -> None:
    """Broadcast a new message notification."""
    message = {
        "event": InboxEvent.NEW_MESSAGE,
        "data": {
            "conversation_id": conversation_id,
            "message": message_data,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Broadcast to messages channel
    await manager.broadcast_to_channel("messages", message)

    # If conversation assigned, notify agent
    if assigned_agent_id:
        await manager.broadcast_to_agent(assigned_agent_id, message)


async def broadcast_assignment(
    conversation_id: int,
    agent_id: int,
    conversation_data: Dict[str, Any],
) -> None:
    """Broadcast when a conversation is assigned to an agent."""
    message = {
        "event": InboxEvent.CONVERSATION_ASSIGNED,
        "data": {
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "conversation": conversation_data,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Notify the assigned agent
    await manager.broadcast_to_agent(agent_id, message)

    # Also broadcast to conversations channel for dashboard updates
    await manager.broadcast_to_channel("conversations", message)


def build_inbox_stats_snapshot(db: Session) -> Dict[str, Any]:
    """Compute lightweight inbox stats for live updates."""
    open_count = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.status == "open")
        .scalar()
    ) or 0

    pending_count = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.status == "pending")
        .scalar()
    ) or 0

    resolved_count = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.status == "resolved")
        .scalar()
    ) or 0

    total_unread = (
        db.query(func.sum(OmniConversation.unread_count))
        .filter(OmniConversation.status.in_(["open", "pending"]))
        .scalar()
    ) or 0

    unassigned_count = (
        db.query(func.count(OmniConversation.id))
        .filter(
            OmniConversation.status.in_(["open", "pending"]),
            OmniConversation.assigned_agent_id.is_(None),
            OmniConversation.assigned_team_id.is_(None),
        )
        .scalar()
    ) or 0

    return {
        "open_count": open_count,
        "pending_count": pending_count,
        "resolved_count": resolved_count,
        "unassigned_count": unassigned_count,
        "total_unread": total_unread,
        "agents_online": manager.get_stats().get("agents_with_connections", 0),
    }


async def authenticate_inbox_websocket(
    websocket: WebSocket,
    db: Session,
) -> Optional[Principal]:
    """Authenticate WebSocket via bearer token or cookie."""
    token: Optional[str] = None

    auth_header = websocket.headers.get("authorization")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()

    if not token:
        token = websocket.cookies.get(AUTH_COOKIE_NAME)

    if not token:
        return None

    try:
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

@router.websocket("/ws/inbox")
async def inbox_websocket(
    websocket: WebSocket,
    channel: str = Query(default="stats"),
    agent_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    """
    WebSocket endpoint for inbox real-time updates.

    Channels:
    - stats: Dashboard statistics updates (open/pending/unread counts)
    - conversations: Conversation list updates
    - messages: New message notifications

    Query params:
    - channel: Which channel to subscribe to (default: stats)
    - agent_id: Optional agent ID for agent-specific notifications

    Security:
    - Requires valid Origin header matching CORS allowed origins (CSWSH protection)
    - Requires valid JWT/service token with support:read scope
    """
    # CSWSH Protection: Validate Origin header
    origin = get_origin_from_websocket(websocket)
    if not validate_origin(origin, settings.cors_origins_list):
        ws_logger.warning(
            "websocket_origin_rejected",
            origin=origin,
            allowed_origins=settings.cors_origins_list,
            channel=channel,
        )
        await websocket.close(code=1008, reason="Invalid origin")
        return

    if channel not in manager.active_connections:
        await websocket.close(code=1008, reason="Invalid channel")
        return

    principal = await authenticate_inbox_websocket(websocket, db)
    if not principal or not principal.has_scope("support:read"):
        ws_logger.warning(
            "websocket_auth_failed",
            origin=origin,
            channel=channel,
            has_principal=principal is not None,
        )
        await websocket.close(code=1008, reason="Authentication required")
        return

    ws_logger.info(
        "websocket_connected",
        origin=origin,
        channel=channel,
        principal_type=principal.type,
        principal_id=principal.id,
        agent_id=agent_id,
    )

    user_id = f"{principal.type}_{principal.id}"
    await manager.connect(websocket, channel, user_id=user_id, agent_id=agent_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "event": "connected",
            "channel": channel,
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Send heartbeat every 30 seconds
                )
                # Handle incoming messages
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif message.get("type") == "subscribe":
                        # Allow subscribing to additional channels
                        new_channel = message.get("channel")
                        if new_channel and manager.subscribe(websocket, new_channel):
                            await websocket.send_json({
                                "type": "subscribed",
                                "channel": new_channel,
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "invalid_channel",
                            })
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/ws/inbox/stats")
async def get_inbox_websocket_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics for inbox."""
    return manager.get_stats()
