"""Messages API - REST endpoints for omnichannel message operations.

Provides endpoints for:
- Listing messages in a conversation
- Creating outbound messages and internal notes
- Delivery status tracking
- Attachment management
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.services.support.messages import MessageService
from app.services.support.types import (
    AttachmentData,
    InternalNoteData,
    OutboundMessageData,
)
from app.services.support.errors import (
    ConversationNotFoundError,
    DuplicateMessageError,
    MessageNotFoundError,
)

router = APIRouter()

# RBAC dependencies
message_read_dep = Depends(Require("support:messages:read", "support:read"))
message_write_dep = Depends(Require("support:messages:write", "support:write"))


# ---------------------------------------------------------------------------
# Service Dependency
# ---------------------------------------------------------------------------


def get_message_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> MessageService:
    """Dependency to get a MessageService instance."""
    return MessageService(db, principal)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class AttachmentRequest(BaseModel):
    """Attachment data for a message."""

    filename: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class OutboundMessageRequest(BaseModel):
    """Request to create an outbound message."""

    body: str = Field(..., min_length=1)
    subject: Optional[str] = None
    channel_id: Optional[int] = None
    attachments: List[AttachmentRequest] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class InternalNoteRequest(BaseModel):
    """Request to create an internal note."""

    body: str = Field(..., min_length=1)
    mentioned_agent_ids: List[int] = Field(default_factory=list)


class MarkFailedRequest(BaseModel):
    """Request to mark a message as failed."""

    error: str = Field(..., min_length=1)
    error_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Response Serializers
# ---------------------------------------------------------------------------


def serialize_message(msg) -> Dict[str, Any]:
    """Serialize a message for API response."""
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "direction": msg.direction,
        "body": msg.body,
        "subject": msg.subject,
        "message_type": msg.message_type,
        "agent_id": msg.agent_id,
        "participant_id": msg.participant_id,
        "channel_id": msg.channel_id,
        "provider_message_id": msg.provider_message_id,
        "delivery_status": msg.delivery_status,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "meta": msg.meta,
        "attachments": [serialize_attachment(a) for a in (msg.attachments or [])],
    }


def serialize_attachment(att) -> Dict[str, Any]:
    """Serialize an attachment for API response."""
    return {
        "id": att.id,
        "message_id": att.message_id,
        "filename": att.filename,
        "url": att.url,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "meta": att.meta,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/conversations/{conversation_id}/messages",
    dependencies=[message_read_dep],
)
def list_messages(
    conversation_id: int,
    before: Optional[datetime] = None,
    after: Optional[datetime] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """List messages for a conversation.

    Args:
        conversation_id: The conversation ID.
        before: Only return messages before this time.
        after: Only return messages after this time.
        limit: Maximum number of messages to return.

    Returns:
        List of messages with metadata.
    """
    try:
        messages = service.list_for_conversation(
            conversation_id=conversation_id,
            before=before,
            after=after,
            limit=limit,
        )
        return {
            "conversation_id": conversation_id,
            "count": len(messages),
            "data": [serialize_message(m) for m in messages],
        }
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/messages/{message_id}",
    dependencies=[message_read_dep],
)
def get_message(
    message_id: int,
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Get a message by ID.

    Args:
        message_id: The message ID.

    Returns:
        Message details.
    """
    try:
        msg = service.get(message_id)
        return serialize_message(msg)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/conversations/{conversation_id}/messages",
    dependencies=[message_write_dep],
    status_code=201,
)
def create_outbound_message(
    conversation_id: int,
    request: OutboundMessageRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Create an outbound message (agent reply).

    Args:
        conversation_id: The conversation ID.
        request: Message data.

    Returns:
        Created message.
    """
    try:
        data = OutboundMessageData(
            conversation_id=conversation_id,
            body=request.body,
            subject=request.subject,
            channel_id=request.channel_id,
            agent_id=principal.user_id if principal else None,
            attachments=[
                AttachmentData(
                    filename=a.filename,
                    url=a.url,
                    mime_type=a.mime_type,
                    size_bytes=a.size_bytes,
                    meta=a.meta,
                )
                for a in request.attachments
            ],
            meta=request.meta,
        )
        msg = service.create_outbound(data)
        db.commit()
        return serialize_message(msg)
    except ConversationNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/conversations/{conversation_id}/notes",
    dependencies=[message_write_dep],
    status_code=201,
)
def create_internal_note(
    conversation_id: int,
    request: InternalNoteRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Create an internal note (not visible to customer).

    Args:
        conversation_id: The conversation ID.
        request: Note data.

    Returns:
        Created note.
    """
    try:
        data = InternalNoteData(
            conversation_id=conversation_id,
            body=request.body,
            agent_id=principal.user_id if principal else 0,
            mentioned_agent_ids=request.mentioned_agent_ids,
        )
        msg = service.create_internal_note(data)
        db.commit()
        return serialize_message(msg)
    except ConversationNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/messages/{message_id}/delivered",
    dependencies=[message_write_dep],
)
def mark_delivered(
    message_id: int,
    provider_message_id: Optional[str] = None,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Mark a message as delivered.

    Args:
        message_id: The message ID.
        provider_message_id: Optional provider's message ID.

    Returns:
        Updated message.
    """
    try:
        msg = service.mark_delivered(message_id, provider_message_id)
        db.commit()
        return serialize_message(msg)
    except MessageNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/messages/{message_id}/sent",
    dependencies=[message_write_dep],
)
def mark_sent(
    message_id: int,
    provider_message_id: Optional[str] = None,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Mark a message as sent.

    Args:
        message_id: The message ID.
        provider_message_id: Optional provider's message ID.

    Returns:
        Updated message.
    """
    try:
        msg = service.mark_sent(message_id, provider_message_id)
        db.commit()
        return serialize_message(msg)
    except MessageNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/messages/{message_id}/read",
    dependencies=[message_write_dep],
)
def mark_read(
    message_id: int,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Mark a message as read.

    Args:
        message_id: The message ID.

    Returns:
        Updated message.
    """
    try:
        msg = service.mark_read(message_id)
        db.commit()
        return serialize_message(msg)
    except MessageNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/messages/{message_id}/failed",
    dependencies=[message_write_dep],
)
def mark_failed(
    message_id: int,
    request: MarkFailedRequest,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Mark a message as failed.

    Args:
        message_id: The message ID.
        request: Error details.

    Returns:
        Updated message.
    """
    try:
        msg = service.mark_failed(message_id, request.error, request.error_code)
        db.commit()
        return serialize_message(msg)
    except MessageNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/conversations/{conversation_id}/mark-read",
    dependencies=[message_write_dep],
)
def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Mark all inbound messages in a conversation as read.

    Args:
        conversation_id: The conversation ID.

    Returns:
        Number of messages marked as read.
    """
    try:
        count = service.mark_conversation_read(conversation_id)
        db.commit()
        return {"conversation_id": conversation_id, "messages_marked_read": count}
    except ConversationNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/messages/{message_id}/attachments",
    dependencies=[message_read_dep],
)
def get_attachments(
    message_id: int,
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Get all attachments for a message.

    Args:
        message_id: The message ID.

    Returns:
        List of attachments.
    """
    attachments = service.get_attachments(message_id)
    return {
        "message_id": message_id,
        "count": len(attachments),
        "data": [serialize_attachment(a) for a in attachments],
    }


@router.post(
    "/messages/{message_id}/attachments",
    dependencies=[message_write_dep],
    status_code=201,
)
def add_attachment(
    message_id: int,
    request: AttachmentRequest,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Dict[str, Any]:
    """Add an attachment to a message.

    Args:
        message_id: The message ID.
        request: Attachment data.

    Returns:
        Created attachment.
    """
    try:
        data = AttachmentData(
            filename=request.filename,
            url=request.url,
            mime_type=request.mime_type,
            size_bytes=request.size_bytes,
            meta=request.meta,
        )
        attachment = service.add_attachment(message_id, data)
        db.commit()
        return serialize_attachment(attachment)
    except MessageNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/attachments/{attachment_id}",
    dependencies=[message_write_dep],
)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    service: MessageService = Depends(get_message_service),
) -> Response:
    """Delete an attachment.

    Args:
        attachment_id: The attachment ID.

    Returns:
        204 No Content on success.
    """
    deleted = service.delete_attachment(attachment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Attachment not found")
    db.commit()
    return Response(status_code=204)
