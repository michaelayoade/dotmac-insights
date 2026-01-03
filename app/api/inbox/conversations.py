"""Inbox Conversations API - CRUD, assignment, status management, integrations.

Refactored to use ConversationService and MessageService for all business logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_principal, Principal
from app.models.omni import OmniConversation, OmniMessage
from app.api.inbox.websocket import (
    broadcast_assignment,
    broadcast_conversation_update,
    broadcast_new_message,
    broadcast_stats_update,
    build_inbox_stats_snapshot,
)
from app.services.support import (
    ConversationService,
    MessageService,
    ConversationFilters,
    ConversationUpdate,
    OutboundMessageData,
    InternalNoteData,
    ConversationNotFoundError,
    ConversationAssignmentError,
    ValidationError,
)

router = APIRouter()


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_conversation_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> ConversationService:
    """Dependency to get ConversationService instance."""
    return ConversationService(db, principal)


def get_message_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> MessageService:
    """Dependency to get MessageService instance."""
    return MessageService(db, principal)


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


class BulkUpdateRequest(BaseModel):
    ids: List[int]
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    add_tags: Optional[List[str]] = None
    remove_tags: Optional[List[str]] = None


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
        "ticket_id": conv.ticket_id,
        "lead_id": conv.lead_id,
        "party_id": conv.party_id,
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
    channel_id: Optional[int] = None,
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
    offset: int = Query(default=0, ge=0),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """List conversations with filtering and pagination."""
    from app.services.types import PaginationParams

    # Build filters
    filters = ConversationFilters(
        statuses=[s.strip() for s in status.split(",")] if status else None,
        priority=priority,
        channel_id=channel_id,
        assigned_agent_id=agent_id,
        assigned_team_id=team_id,
        unassigned_only=unassigned,
        starred_only=is_starred if is_starred else False,
        search=search,
        tags=[tag] if tag else None,
    )

    # Parse dates
    if start_date:
        try:
            filters.start_date = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    if end_date:
        try:
            filters.end_date = datetime.fromisoformat(end_date)
        except ValueError:
            pass

    # Get conversations using service
    pagination = PaginationParams(limit=limit, offset=offset)
    result = service.list(
        filters=filters,
        pagination=pagination,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_conversation(c) for c in result.items],
    }


@router.get(
    "/conversations/stats",
    dependencies=[Depends(Require("support:read"))],
)
async def get_conversation_stats(
    agent_id: Optional[int] = None,
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Get inbox statistics."""
    stats = service.get_stats(agent_id=agent_id)
    return {
        "total": stats.total_conversations,
        "open": stats.open_conversations,
        "pending": stats.pending_conversations,
        "resolved": stats.resolved_conversations,
        "unassigned": stats.unassigned_conversations,
        "my_conversations": stats.my_conversations,
        "unread": stats.unread_conversations,
        "snoozed": stats.snoozed_conversations,
    }


@router.get(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_conversation(
    conversation_id: int,
    message_limit: int = Query(default=50, le=200),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Get a single conversation with messages."""
    try:
        result = service.get_with_messages(conversation_id, message_limit=message_limit)
        conv_data = serialize_conversation(result.conversation)
        conv_data["messages"] = [serialize_message(msg) for msg in result.messages]
        conv_data["total_messages"] = result.total_messages
        conv_data["has_more"] = result.has_more
        return conv_data
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Update conversation status, priority, tags, etc."""
    try:
        update_data = ConversationUpdate(
            status=payload.status,
            priority=payload.priority,
            is_starred=payload.is_starred,
            tags=payload.tags,
            snoozed_until=payload.snoozed_until,
        )
        conv = service.update(conversation_id, update_data)
        db.commit()
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    conversation_payload = serialize_conversation(conv)
    await broadcast_conversation_update(
        conversation_payload,
        assigned_agent_id=conv.assigned_agent_id,
    )
    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return conversation_payload


@router.post(
    "/conversations/{conversation_id}/assign",
    dependencies=[Depends(Require("support:write"))],
)
async def assign_conversation(
    conversation_id: int,
    payload: AssignmentRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Assign a conversation to an agent or team."""
    try:
        conv = service.assign(
            conversation_id,
            agent_id=payload.agent_id,
            team_id=payload.team_id,
        )
        db.commit()
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConversationAssignmentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conversation_payload = serialize_conversation(conv)
    if conv.assigned_agent_id:
        await broadcast_assignment(
            conversation_id=conv.id,
            agent_id=conv.assigned_agent_id,
            conversation_data=conversation_payload,
        )
    else:
        await broadcast_conversation_update(conversation_payload)
    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return conversation_payload


@router.post(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(Require("support:write"))],
)
async def send_reply(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    conv_service: ConversationService = Depends(get_conversation_service),
    msg_service: MessageService = Depends(get_message_service),
    principal: Principal = Depends(get_principal),
) -> Dict[str, Any]:
    """Send a reply to a conversation."""
    try:
        # Get conversation to check it exists
        conv = conv_service.get(conversation_id)

        # Create message using service
        agent_id = getattr(principal, 'agent_id', None) if principal else None

        if payload.is_private:
            data = InternalNoteData(
                conversation_id=conversation_id,
                body=payload.body,
                agent_id=agent_id,
            )
            msg = msg_service.create_internal_note(data)
        else:
            data = OutboundMessageData(
                conversation_id=conversation_id,
                body=payload.body,
                agent_id=agent_id,
            )
            msg = msg_service.create_outbound(data)

        db.commit()
        db.refresh(msg)
        db.refresh(conv)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    message_payload = serialize_message(msg)
    conversation_payload = serialize_conversation(conv)
    await broadcast_new_message(
        message_payload,
        conversation_id=conv.id,
        assigned_agent_id=conv.assigned_agent_id,
    )
    await broadcast_conversation_update(
        conversation_payload,
        assigned_agent_id=conv.assigned_agent_id,
    )
    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return message_payload


@router.get(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(Require("support:read"))],
)
async def list_messages(
    conversation_id: int,
    before: Optional[str] = None,
    after: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    msg_service: MessageService = Depends(get_message_service),
    conv_service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """List messages for a conversation."""
    try:
        # Verify conversation exists
        conv_service.get(conversation_id)

        # Parse date filters
        before_dt = None
        after_dt = None
        if before:
            try:
                before_dt = datetime.fromisoformat(before)
            except ValueError:
                pass
        if after:
            try:
                after_dt = datetime.fromisoformat(after)
            except ValueError:
                pass

        messages = msg_service.list_for_conversation(
            conversation_id,
            before=before_dt,
            after=after_dt,
            limit=limit,
        )

        return {
            "conversation_id": conversation_id,
            "count": len(messages),
            "data": [serialize_message(msg) for msg in messages],
        }
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/mark-read",
    dependencies=[Depends(Require("support:write"))],
)
async def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Mark all messages in a conversation as read."""
    try:
        count = service.mark_read(conversation_id)
        db.commit()

        conv = service.get(conversation_id)

        conversation_payload = serialize_conversation(conv)
        await broadcast_conversation_update(
            conversation_payload,
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return {"success": True, "conversation_id": conversation_id, "messages_marked_read": count}
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/star",
    dependencies=[Depends(Require("support:write"))],
)
async def star_conversation(
    conversation_id: int,
    starred: bool = True,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Star or unstar a conversation."""
    try:
        conv = service.star(conversation_id, starred)
        db.commit()
        return {"success": True, "conversation_id": conversation_id, "is_starred": conv.is_starred}
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/tags/{tag}",
    dependencies=[Depends(Require("support:write"))],
)
async def add_tag(
    conversation_id: int,
    tag: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Add a tag to a conversation."""
    try:
        conv = service.add_tag(conversation_id, tag)
        db.commit()
        return {"success": True, "conversation_id": conversation_id, "tags": conv.tags}
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/conversations/{conversation_id}/tags/{tag}",
    dependencies=[Depends(Require("support:write"))],
)
async def remove_tag(
    conversation_id: int,
    tag: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Remove a tag from a conversation."""
    try:
        conv = service.remove_tag(conversation_id, tag)
        db.commit()
        return {"success": True, "conversation_id": conversation_id, "tags": conv.tags}
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# LIFECYCLE ENDPOINTS
# =============================================================================

@router.post(
    "/conversations/{conversation_id}/resolve",
    dependencies=[Depends(Require("support:write"))],
)
async def resolve_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Mark a conversation as resolved."""
    try:
        conv = service.resolve(conversation_id)
        db.commit()

        conversation_payload = serialize_conversation(conv)
        await broadcast_conversation_update(
            conversation_payload,
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return conversation_payload
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/snooze",
    dependencies=[Depends(Require("support:write"))],
)
async def snooze_conversation(
    conversation_id: int,
    until: datetime,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Snooze a conversation until a specific time."""
    try:
        conv = service.snooze(conversation_id, until)
        db.commit()

        conversation_payload = serialize_conversation(conv)
        await broadcast_conversation_update(
            conversation_payload,
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return conversation_payload
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/reopen",
    dependencies=[Depends(Require("support:write"))],
)
async def reopen_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Reopen a resolved or snoozed conversation."""
    try:
        conv = service.reopen(conversation_id)
        db.commit()

        conversation_payload = serialize_conversation(conv)
        await broadcast_conversation_update(
            conversation_payload,
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return conversation_payload
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/archive",
    dependencies=[Depends(Require("support:write"))],
)
async def archive_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Archive a conversation."""
    try:
        conv = service.archive(conversation_id)
        db.commit()

        conversation_payload = serialize_conversation(conv)
        await broadcast_conversation_update(
            conversation_payload,
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return {"success": True, "conversation_id": conversation_id}
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/conversations/{conversation_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    """Delete a conversation (soft delete by archiving)."""
    try:
        conv = service.archive(conversation_id)
        db.commit()

        await broadcast_conversation_update(
            serialize_conversation(conv),
            assigned_agent_id=conv.assigned_agent_id,
        )
        await broadcast_stats_update(build_inbox_stats_snapshot(db))

        return None
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Create a support ticket from a conversation."""
    try:
        ticket = service.create_ticket(
            conversation_id,
            subject=payload.subject,
            priority=payload.priority,
            category=payload.category,
            description=payload.description,
        )
        db.commit()

        return {
            "success": True,
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "conversation_id": conversation_id,
        }
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/create-lead",
    dependencies=[Depends(Require("sales:write"))],
)
async def create_lead_from_conversation(
    conversation_id: int,
    payload: CreateLeadRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Create a sales lead from a conversation."""
    try:
        lead = service.create_lead(
            conversation_id,
            lead_name=payload.lead_name,
            company_name=payload.company_name,
            source=payload.source,
            notes=payload.notes,
        )
        db.commit()

        return {
            "success": True,
            "lead_id": lead.id,
            "conversation_id": conversation_id,
        }
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.post(
    "/conversations/bulk/update",
    dependencies=[Depends(Require("support:write"))],
)
async def bulk_update_conversations(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Bulk update multiple conversations."""
    from app.services.support import ConversationBulkUpdate

    data = ConversationBulkUpdate(
        ids=payload.ids,
        status=payload.status,
        priority=payload.priority,
        assigned_agent_id=payload.assigned_agent_id,
        assigned_team_id=payload.assigned_team_id,
        add_tags=payload.add_tags,
        remove_tags=payload.remove_tags,
    )

    result = service.bulk_update(data)
    db.commit()

    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return {
        "updated_count": result.updated_count,
        "failed_count": result.failed_count,
        "failed_ids": result.failed_ids,
        "errors": result.errors,
    }


@router.post(
    "/conversations/bulk/assign",
    dependencies=[Depends(Require("support:write"))],
)
async def bulk_assign_conversations(
    ids: List[int],
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Bulk assign multiple conversations."""
    result = service.bulk_assign(ids, agent_id=agent_id, team_id=team_id)
    db.commit()

    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return {
        "updated_count": result.updated_count,
        "failed_count": result.failed_count,
        "failed_ids": result.failed_ids,
    }


@router.post(
    "/conversations/bulk/status",
    dependencies=[Depends(Require("support:write"))],
)
async def bulk_update_status(
    ids: List[int],
    status: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """Bulk update status for multiple conversations."""
    result = service.bulk_update_status(ids, status)
    db.commit()

    await broadcast_stats_update(build_inbox_stats_snapshot(db))

    return {
        "updated_count": result.updated_count,
        "failed_count": result.failed_count,
        "failed_ids": result.failed_ids,
    }
