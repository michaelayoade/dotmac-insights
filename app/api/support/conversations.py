"""Conversation endpoints (Chatwoot)."""
from __future__ import annotations

from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation, ConversationStatus
from app.models.customer import Customer
from app.auth import Require

router = APIRouter()


@router.get("/conversations", dependencies=[Depends(Require("explorer:read"))])
def list_conversations(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    channel: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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

    if customer_id:
        query = query.filter(Conversation.customer_id == customer_id)

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
                "customer_id": c.customer_id,
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

    customer = None
    if conversation.customer_id:
        cust = db.query(Customer).filter(Customer.id == conversation.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    return {
        "id": conversation.id,
        "chatwoot_id": conversation.chatwoot_id,
        "status": conversation.status.value if conversation.status else None,
        "channel": conversation.channel,
        "subject": conversation.subject,
        "message_count": conversation.message_count,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "last_activity_at": conversation.last_activity_at.isoformat() if conversation.last_activity_at else None,
        "customer": customer,
    }
