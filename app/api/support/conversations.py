"""Conversation endpoints (Chatwoot).

These routes are thin wrappers around ConversationService.
All business logic resides in the service layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation, ConversationStatus
from app.models.party import CustomerAccount
from app.auth import Require, get_current_user, Principal
from app.services.support import ConversationService
from app.services.support.errors import (
    ConversationNotFoundError,
    ConversationAssignmentError,
)

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StatusUpdateRequest(BaseModel):
    status: str
    snoozed_until: Optional[datetime] = None


class StarRequest(BaseModel):
    starred: bool


class AssignRequest(BaseModel):
    agent_id: Optional[int] = None
    team_id: Optional[int] = None


class TagRequest(BaseModel):
    tag: str


class SnoozeRequest(BaseModel):
    until: datetime


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_conversation_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
) -> ConversationService:
    """Provide ConversationService instance for dependency injection."""
    return ConversationService(db, principal)


@router.get("/conversations", dependencies=[Depends(Require("explorer:read"))])
def list_conversations(
    status: Optional[str] = None,
    customer_account_id: Optional[int] = None,
    party_id: Optional[int] = None,
    channel: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List Chatwoot conversations with filtering and pagination."""
    query = db.query(Conversation)

    if status:
        try:
            status_enum = ConversationStatus(status)
            query = query.filter(Conversation.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_account_id:
        query = query.filter(Conversation.customer_account_id == customer_account_id)
    elif party_id:
        query = query.join(
            CustomerAccount,
            CustomerAccount.id == Conversation.customer_account_id,
        ).filter(CustomerAccount.party_id == party_id)

    if channel:
        query = query.filter(Conversation.channel == channel)

    if search:
        search_term = f"%{search}%"
        query = query.filter(Conversation.subject.ilike(search_term))

    total = query.count()
    conversations = query.order_by(Conversation.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": c.id,
                "chatwoot_id": c.chatwoot_id,
                "status": c.status.value if c.status else None,
                "channel": c.channel,
                "customer_account_id": c.customer_account_id,
                "party_id": c.customer_account.party_id if c.customer_account else None,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "last_activity_at": c.last_activity_at.isoformat() if c.last_activity_at else None,
            }
            for c in conversations
        ],
    }


@router.get("/conversations/{conversation_id}", dependencies=[Depends(Require("explorer:read"))])
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed conversation information."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    customer_account = None
    party_id = None
    party_name = None
    if conversation.customer_account and conversation.customer_account.party:
        party = conversation.customer_account.party
        party_id = party.id
        party_name = party.name
        if not party_name:
            party_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not party_name:
            party_name = party.legal_name or party.trading_name
        customer_account = {
            "id": conversation.customer_account.id,
            "party_id": party.id,
            "name": party_name,
        }

    return {
        "id": conversation.id,
        "chatwoot_id": conversation.chatwoot_id,
        "status": conversation.status.value if conversation.status else None,
        "channel": conversation.channel,
        "subject": conversation.subject,
        "message_count": conversation.message_count,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "last_activity_at": conversation.last_activity_at.isoformat() if conversation.last_activity_at else None,
        "customer_account_id": conversation.customer_account_id,
        "party_id": party_id,
        "party_name": party_name,
        "customer_account": customer_account,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _serialize_conversation(conv) -> Dict[str, Any]:
    """Serialize a conversation for API response."""
    return {
        "id": conv.id,
        "status": conv.status,
        "is_starred": getattr(conv, "is_starred", False),
        "assigned_agent_id": getattr(conv, "assigned_party_id", None),
        "assigned_team_id": getattr(conv, "assigned_team_id", None),
        "tags": conv.tags if hasattr(conv, "tags") else None,
        "resolved_at": conv.resolved_at.isoformat() if getattr(conv, "resolved_at", None) else None,
        "snoozed_until": conv.snoozed_until.isoformat() if getattr(conv, "snoozed_until", None) else None,
        "updated_at": conv.updated_at.isoformat() if getattr(conv, "updated_at", None) else None,
    }


# =============================================================================
# CONVERSATION MUTATIONS
# =============================================================================

@router.post(
    "/conversations/{conversation_id}/status",
    dependencies=[Depends(Require("support:write"))],
)
def update_conversation_status(
    conversation_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Update conversation status."""
    try:
        conv = service.update_status(
            conversation_id,
            payload.status,
            snoozed_until=payload.snoozed_until,
        )
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/star",
    dependencies=[Depends(Require("support:write"))],
)
def star_conversation(
    conversation_id: int,
    payload: StarRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Star or unstar a conversation."""
    try:
        conv = service.star(conversation_id, payload.starred)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/assign",
    dependencies=[Depends(Require("support:write"))],
)
def assign_conversation(
    conversation_id: int,
    payload: AssignRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Assign a conversation to an agent and/or team."""
    try:
        conv = service.assign(
            conversation_id,
            agent_id=payload.agent_id,
            team_id=payload.team_id,
        )
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except ConversationAssignmentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/tag",
    dependencies=[Depends(Require("support:write"))],
)
def add_conversation_tag(
    conversation_id: int,
    payload: TagRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Add a tag to a conversation."""
    try:
        conv = service.add_tag(conversation_id, payload.tag)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.delete(
    "/conversations/{conversation_id}/tag",
    dependencies=[Depends(Require("support:write"))],
)
def remove_conversation_tag(
    conversation_id: int,
    tag: str = Query(..., description="Tag to remove"),
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Remove a tag from a conversation."""
    try:
        conv = service.remove_tag(conversation_id, tag)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/resolve",
    dependencies=[Depends(Require("support:write"))],
)
def resolve_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Mark a conversation as resolved."""
    try:
        conv = service.resolve(conversation_id)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/snooze",
    dependencies=[Depends(Require("support:write"))],
)
def snooze_conversation(
    conversation_id: int,
    payload: SnoozeRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Snooze a conversation until a specific time."""
    try:
        conv = service.snooze(conversation_id, payload.until)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/reopen",
    dependencies=[Depends(Require("support:write"))],
)
def reopen_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Reopen a resolved or snoozed conversation."""
    try:
        conv = service.reopen(conversation_id)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/archive",
    dependencies=[Depends(Require("support:write"))],
)
def archive_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Archive (close) a conversation."""
    try:
        conv = service.archive(conversation_id)
        db.commit()
        return _serialize_conversation(conv)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
