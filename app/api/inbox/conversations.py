"""Inbox Conversations API - CRUD, assignment, status management, integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.database import get_db
from app.auth import Require
from app.models.omni import (
    OmniChannel,
    OmniConversation,
    OmniMessage,
    OmniParticipant,
    InboxContact,
)
from app.models.agent import Agent, Team
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.sales import ERPNextLead

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class ConversationUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    is_starred: Optional[bool] = None
    tags: Optional[List[str]] = None
    snoozed_until: Optional[datetime] = None


class AssignmentRequest(BaseModel):
    agent_id: Optional[int] = None
    team_id: Optional[int] = None


class CreateTicketRequest(BaseModel):
    subject: Optional[str] = None
    priority: str = "medium"
    category: Optional[str] = None
    description: Optional[str] = None


class CreateLeadRequest(BaseModel):
    lead_name: Optional[str] = None
    company_name: Optional[str] = None
    source: str = "inbox"
    notes: Optional[str] = None


class SendMessageRequest(BaseModel):
    body: str
    is_private: bool = False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def serialize_conversation(conv: OmniConversation, include_messages: bool = False) -> Dict[str, Any]:
    """Serialize a conversation to JSON."""
    result: Dict[str, Any] = {
        "id": conv.id,
        "channel_id": conv.channel_id,
        "channel_type": conv.channel.type if conv.channel else None,
        "channel_name": conv.channel.name if conv.channel else None,
        "external_thread_id": conv.external_thread_id,
        "subject": conv.subject,
        "status": conv.status or "open",
        "priority": conv.priority or "medium",
        "customer_id": conv.customer_id,
        "ticket_id": conv.ticket_id,
        "lead_id": conv.lead_id,
        "assigned_agent_id": conv.assigned_agent_id,
        "assigned_agent_name": conv.assigned_agent.display_name if conv.assigned_agent else None,
        "assigned_team_id": conv.assigned_team_id,
        "assigned_team_name": conv.assigned_team.name if conv.assigned_team else None,
        "assigned_at": conv.assigned_at.isoformat() if conv.assigned_at else None,
        "is_starred": conv.is_starred,
        "unread_count": conv.unread_count,
        "message_count": conv.message_count,
        "tags": conv.tags or [],
        "contact": {
            "name": conv.contact_name,
            "email": conv.contact_email,
            "company": conv.contact_company,
        },
        "first_response_at": conv.first_response_at.isoformat() if conv.first_response_at else None,
        "resolved_at": conv.resolved_at.isoformat() if conv.resolved_at else None,
        "snoozed_until": conv.snoozed_until.isoformat() if conv.snoozed_until else None,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }

    if include_messages:
        result["messages"] = [
            serialize_message(msg) for msg in sorted(conv.messages, key=lambda m: m.created_at)
        ]

    return result


def serialize_message(msg: OmniMessage) -> Dict[str, Any]:
    """Serialize a message to JSON."""
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "direction": msg.direction,
        "body": msg.body,
        "subject": msg.subject,
        "message_type": msg.message_type,
        "participant_id": msg.participant_id,
        "agent_id": msg.agent_id,
        "delivery_status": msg.delivery_status,
        "meta": msg.meta,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "url": att.url,
                "mime_type": att.mime_type,
                "size_bytes": att.size_bytes,
            }
            for att in msg.attachments
        ],
    }


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================

@router.get(
    "/conversations",
    dependencies=[Depends(Require("support:read"))],
)
async def list_conversations(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    channel: Optional[str] = None,
    assigned_to_me: bool = False,
    unassigned: bool = False,
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_starred: Optional[bool] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "last_message_at",
    sort_order: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List conversations with filtering and pagination."""
    query = db.query(OmniConversation)

    # Apply filters
    if status:
        statuses = [s.strip() for s in status.split(",")]
        query = query.filter(OmniConversation.status.in_(statuses))

    if priority:
        priorities = [p.strip() for p in priority.split(",")]
        query = query.filter(OmniConversation.priority.in_(priorities))

    if channel:
        ch = db.query(OmniChannel).filter(OmniChannel.name == channel).first()
        if ch:
            query = query.filter(OmniConversation.channel_id == ch.id)

    if unassigned:
        query = query.filter(
            OmniConversation.assigned_agent_id.is_(None),
            OmniConversation.assigned_team_id.is_(None),
        )

    if agent_id:
        query = query.filter(OmniConversation.assigned_agent_id == agent_id)

    if team_id:
        query = query.filter(OmniConversation.assigned_team_id == team_id)

    if is_starred is not None:
        query = query.filter(OmniConversation.is_starred == is_starred)

    if tag:
        # JSON contains check - works for arrays stored as JSON
        query = query.filter(OmniConversation.tags.contains([tag]))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                OmniConversation.subject.ilike(search_term),
                OmniConversation.contact_name.ilike(search_term),
                OmniConversation.contact_email.ilike(search_term),
            )
        )

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(OmniConversation.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(OmniConversation.created_at <= end_dt)
        except ValueError:
            pass

    # Get total before pagination
    total = query.count()

    # Apply sorting
    sort_column = getattr(OmniConversation, sort_by, OmniConversation.last_message_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc().nullslast())
    else:
        query = query.order_by(sort_column.asc().nullsfirst())

    # Apply pagination
    conversations = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_conversation(c) for c in conversations],
    }


@router.get(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single conversation with messages."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return serialize_conversation(conv, include_messages=True)


@router.patch(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update conversation status, priority, tags, etc."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.status is not None:
        conv.status = payload.status
        if payload.status == "resolved":
            conv.resolved_at = datetime.utcnow()
        elif payload.status == "snoozed" and payload.snoozed_until:
            conv.snoozed_until = payload.snoozed_until

    if payload.priority is not None:
        conv.priority = payload.priority

    if payload.is_starred is not None:
        conv.is_starred = payload.is_starred

    if payload.tags is not None:
        conv.tags = cast(Any, payload.tags)

    db.commit()
    db.refresh(conv)

    return serialize_conversation(conv)


@router.post(
    "/conversations/{conversation_id}/assign",
    dependencies=[Depends(Require("support:write"))],
)
async def assign_conversation(
    conversation_id: int,
    payload: AssignmentRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Assign a conversation to an agent or team."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.agent_id is not None:
        if payload.agent_id > 0:
            agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
            if not agent:
                raise HTTPException(status_code=400, detail="Agent not found")
            conv.assigned_agent_id = payload.agent_id
        else:
            conv.assigned_agent_id = None

    if payload.team_id is not None:
        if payload.team_id > 0:
            team = db.query(Team).filter(Team.id == payload.team_id).first()
            if not team:
                raise HTTPException(status_code=400, detail="Team not found")
            conv.assigned_team_id = payload.team_id
        else:
            conv.assigned_team_id = None

    if payload.agent_id or payload.team_id:
        conv.assigned_at = datetime.utcnow()

    db.commit()
    db.refresh(conv)

    return serialize_conversation(conv)


@router.post(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(Require("support:write"))],
)
async def send_reply(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a reply to a conversation."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = OmniMessage(
        conversation_id=conv.id,
        direction="outbound",
        body=payload.body,
        message_type="private_note" if payload.is_private else "outgoing",
        channel_id=conv.channel_id,
        created_at=datetime.utcnow(),
    )
    db.add(msg)

    # Update conversation stats
    conv.message_count = (conv.message_count or 0) + 1
    conv.last_message_at = datetime.utcnow()

    # Track first response time
    if not conv.first_response_at and not payload.is_private:
        conv.first_response_at = datetime.utcnow()

    db.commit()
    db.refresh(msg)

    return serialize_message(msg)


@router.post(
    "/conversations/{conversation_id}/mark-read",
    dependencies=[Depends(Require("support:write"))],
)
async def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark all messages in a conversation as read."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.unread_count = 0

    # Mark all inbound messages as read
    db.query(OmniMessage).filter(
        OmniMessage.conversation_id == conversation_id,
        OmniMessage.direction == "inbound",
        OmniMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})

    db.commit()

    return {"success": True, "conversation_id": conversation_id}


# =============================================================================
# INTEGRATION ENDPOINTS
# =============================================================================

@router.post(
    "/conversations/{conversation_id}/create-ticket",
    dependencies=[Depends(Require("support:write"))],
)
async def create_ticket_from_conversation(
    conversation_id: int,
    payload: CreateTicketRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a support ticket from a conversation."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.ticket_id:
        raise HTTPException(status_code=400, detail="Conversation already has a ticket")

    # Build description from conversation messages
    messages_text = "\n\n".join([
        f"[{msg.direction}] {msg.body or ''}"
        for msg in sorted(conv.messages, key=lambda m: m.created_at)[:10]  # First 10 messages
    ])

    description = payload.description or messages_text or "Created from inbox conversation"

    # Create ticket
    ticket = Ticket(
        subject=payload.subject or conv.subject or "Support Request",
        description=description,
        status=TicketStatus.OPEN,
        priority=TicketPriority[payload.priority.upper()] if payload.priority else TicketPriority.MEDIUM,
        category=payload.category,
        customer_id=conv.customer_id,
        contact_name=conv.contact_name,
        contact_email=conv.contact_email,
        source="inbox",
        created_at=datetime.utcnow(),
    )
    db.add(ticket)
    db.flush()

    # Link conversation to ticket
    conv.ticket_id = ticket.id

    db.commit()
    db.refresh(ticket)

    return {
        "success": True,
        "ticket_id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "conversation_id": conversation_id,
    }


@router.post(
    "/conversations/{conversation_id}/create-lead",
    dependencies=[Depends(Require("sales:write"))],
)
async def create_lead_from_conversation(
    conversation_id: int,
    payload: CreateLeadRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a sales lead from a conversation."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.lead_id:
        raise HTTPException(status_code=400, detail="Conversation already has a lead")

    # Create lead
    lead = ERPNextLead(
        lead_name=payload.lead_name or conv.contact_name or "Unknown",
        company_name=payload.company_name or conv.contact_company,
        email_id=conv.contact_email,
        source=payload.source or "inbox",
        notes=payload.notes or f"Created from inbox conversation #{conv.id}",
        status="Open",
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.flush()

    # Link conversation to lead
    conv.lead_id = lead.id

    db.commit()
    db.refresh(lead)

    return {
        "success": True,
        "lead_id": lead.id,
        "conversation_id": conversation_id,
    }


@router.delete(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Delete a conversation (soft delete by setting status to closed)."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.status = "closed"
    db.commit()

    return None


@router.post(
    "/conversations/{conversation_id}/archive",
    dependencies=[Depends(Require("support:write"))],
)
async def archive_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Archive a conversation."""
    conv = db.query(OmniConversation).filter(OmniConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.status = "closed"
    db.commit()

    return {"success": True, "conversation_id": conversation_id}
