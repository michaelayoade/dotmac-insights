"""Conversation endpoints (Chatwoot)."""
from __future__ import annotations

from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation, ConversationStatus
from app.models.party import CustomerAccount
from app.auth import Require

router = APIRouter()


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
