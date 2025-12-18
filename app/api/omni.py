from __future__ import annotations

from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime
import hmac
import hashlib
import json
import imaplib
import email
import logging
from email.header import decode_header
from email.message import Message as EmailMessage
import base64

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.auth import Require
from app.config import settings
from app.database import get_db
from app.middleware.metrics import increment_webhook_auth_failure

logger = logging.getLogger(__name__)
from app.models.omni import (
    OmniChannel,
    OmniConversation,
    OmniParticipant,
    OmniMessage,
    OmniWebhookEvent,
    OmniAttachment,
)
from app.models.agent import Agent, Team
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from app.tasks.omni_email import poll_email_channel

# Authenticated Omni endpoints
router = APIRouter(prefix="/omni", tags=["omni"])
# Public-facing webhook ingest (no JWT expected)
public_router = APIRouter(prefix="/omni", tags=["omni"])


class ChannelCreateRequest:
    def __init__(
        self,
        name: str,
        type: str,
        config: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        is_active: bool = True,
    ):
        self.name = name
        self.type = type
        self.config = config or {}
        self.webhook_secret = webhook_secret
        self.is_active = is_active


class ChannelUpdateRequest:
    def __init__(
        self,
        name: Optional[str] = None,
        type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        self.name = name
        self.type = type
        self.config = config
        self.webhook_secret = webhook_secret
        self.is_active = is_active


def _verify_signature(secret: Optional[str], body: bytes, signature: Optional[str]) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _get_channel_or_404(db: Session, channel_name: str) -> OmniChannel:
    channel = db.query(OmniChannel).filter(OmniChannel.name == channel_name, OmniChannel.is_active == True).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or inactive")
    return channel


def _get_or_create_conversation(
    db: Session,
    channel: OmniChannel,
    external_thread_id: Optional[str],
    customer_id: Optional[int],
    ticket_id: Optional[int],
    subject: Optional[str],
) -> OmniConversation:
    conv = None
    if external_thread_id:
        conv = (
            db.query(OmniConversation)
            .filter(
                OmniConversation.channel_id == channel.id,
                OmniConversation.external_thread_id == external_thread_id,
            )
            .first()
        )
    if not conv:
        conv = OmniConversation(
            channel_id=channel.id,
            external_thread_id=external_thread_id,
            customer_id=customer_id,
            ticket_id=ticket_id,
            subject=subject,
            status="open",
        )
        db.add(conv)
        db.flush()
    return conv


def _get_or_create_participant(
    db: Session,
    handle: str,
    channel_type: str,
    display_name: Optional[str],
    customer_id: Optional[int],
) -> OmniParticipant:
    participant = (
        db.query(OmniParticipant)
        .filter(OmniParticipant.handle == handle, OmniParticipant.channel_type == channel_type)
        .first()
    )
    if not participant:
        participant = OmniParticipant(
            handle=handle,
            channel_type=channel_type,
            display_name=display_name,
            customer_id=customer_id,
        )
        db.add(participant)
        db.flush()
    return participant


def _persist_message(
    db: Session,
    conversation: OmniConversation,
    direction: str,
    body: Optional[str],
    subject: Optional[str],
    participant: Optional[OmniParticipant],
    customer_id: Optional[int],
    ticket_id: Optional[int],
    channel: Optional[OmniChannel],
    agent: Optional[Agent],
    metadata: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> OmniMessage:
    msg = OmniMessage(
        conversation_id=conversation.id,
        direction=direction,
        body=body,
        subject=subject,
        participant_id=participant.id if participant else None,
        customer_id=customer_id,
        ticket_id=ticket_id,
        channel_id=channel.id if channel else None,
        agent_id=agent.id if agent else None,
        meta=metadata,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.flush()

    for att in attachments or []:
        attachment = OmniAttachment(
            message_id=msg.id,
            filename=att.get("filename"),
            url=att.get("url"),
            mime_type=att.get("mime_type"),
            size_bytes=att.get("size_bytes"),
            meta=att.get("metadata"),
        )
        db.add(attachment)

    conversation.last_message_at = datetime.utcnow()
    return msg


def _normalize_email_payload(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], List[Dict[str, Any]]]:
    """
    Best-effort normalization for email provider webhooks (e.g., SES/SNS or generic SMTP relay).
    Returns: sender, subject, body, thread_id, attachments
    """
    sender = None
    subject = None
    body = None
    thread_id = None
    attachments: List[Dict[str, Any]] = []

    # SES-style
    mail = payload.get("mail") or {}
    if mail:
        sender = mail.get("source") or sender
        subject = mail.get("commonHeaders", {}).get("subject") or subject
        thread_id = mail.get("messageId") or thread_id

    # Generic fields
    sender = payload.get("from") or payload.get("sender") or sender
    subject = payload.get("subject") or subject
    body = payload.get("body") or payload.get("text") or payload.get("content") or body
    thread_id = payload.get("message_id") or payload.get("thread_id") or thread_id

    # Attachments (expect list of dicts)
    raw_attachments = payload.get("attachments")
    if isinstance(raw_attachments, list):
        attachments = [
            {
                "filename": a.get("filename") or a.get("name"),
                "url": a.get("url"),
                "mime_type": a.get("mime_type") or a.get("content_type"),
                "size_bytes": a.get("size"),
                "metadata": a,
            }
            for a in raw_attachments
            if isinstance(a, dict)
        ]

    return sender, subject, body, thread_id, attachments


def _extract_message_ids(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extract message-id and in-reply-to for threading."""
    msg_id = payload.get("message_id") or payload.get("id") or payload.get("mail", {}).get("messageId")
    in_reply_to = payload.get("in_reply_to") or payload.get("in-reply-to")
    if not in_reply_to:
        in_reply_to = payload.get("headers", {}).get("In-Reply-To")
    return msg_id, in_reply_to


def _send_email_via_smtp(channel: OmniChannel, to_address: str, subject: Optional[str], body: str) -> None:
    """Best-effort SMTP send for email channels."""
    cfg = channel.config or {}
    host = cfg.get("smtp_host")
    port = int(cfg.get("smtp_port") or 587)
    username = cfg.get("smtp_username")
    password = cfg.get("smtp_password")
    use_tls = cfg.get("use_tls", True)
    from_address = cfg.get("from_address") or username
    if not host or not username or not password or not from_address:
        raise HTTPException(status_code=400, detail="Email channel missing SMTP configuration (host/username/password/from_address).")

    msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = subject or ""
    msg["From"] = formataddr((cfg.get("from_name") or "", from_address))
    msg["To"] = to_address

    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(username, password)
        server.sendmail(from_address, [to_address], msg.as_string())


@public_router.post("/webhooks/{channel_name}")
async def ingest_webhook(
    channel_name: str,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(default=None, convert_underscores=True),
) -> Dict[str, Any]:
    """
    Generic webhook ingest endpoint for external providers.

    This endpoint is unauthenticated (for external providers) but uses
    signature verification for security. In production, webhook_secret
    must be configured on the channel.
    """
    body = await request.body()
    try:
        payload_json = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload_json = {}

    channel = _get_channel_or_404(db, channel_name)

    # Signature verification - fail closed in production
    if channel.webhook_secret:
        if not _verify_signature(channel.webhook_secret, body, x_signature):
            logger.warning(
                "omni_webhook_signature_invalid",
                channel=channel_name,
                has_signature=bool(x_signature),
            )
            increment_webhook_auth_failure("omni", "invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        # No webhook secret configured
        if settings.is_production:
            logger.error(
                "omni_webhook_secret_missing",
                channel=channel_name,
                message="Webhook secret not configured in production - rejecting webhook",
            )
            increment_webhook_auth_failure("omni", "no_secret")
            raise HTTPException(
                status_code=500,
                detail="Channel webhook_secret not configured"
            )
        logger.warning(
            "omni_webhook_secret_missing_dev",
            channel=channel_name,
            message="Webhook secret not configured, skipping verification (dev mode)",
        )

    provider_event_id = payload_json.get("id") or payload_json.get("event_id") or payload_json.get("message_id")

    # Idempotency: if an event with same provider_event_id already processed, return early
    if provider_event_id:
        existing = (
            db.query(OmniWebhookEvent)
            .filter(
                OmniWebhookEvent.channel_id == channel.id,
                OmniWebhookEvent.provider_event_id == provider_event_id,
                OmniWebhookEvent.processed == True,
            )
            .first()
        )
        if existing:
            return {"status": "ok", "event_id": existing.id, "processed": True}

    raw_event = OmniWebhookEvent(
        channel_id=channel.id,
        provider_event_id=provider_event_id,
        payload=payload_json,
        headers=dict(request.headers),
    )
    db.add(raw_event)
    db.flush()

    # Basic normalization stub: map minimal fields; adapter-specific logic can expand this.
    if channel.type == "email":
        sender, subject, body_text, thread_id, attachments = _normalize_email_payload(payload_json)
        msg_id, in_reply_to = _extract_message_ids(payload_json)
        thread_id = thread_id or in_reply_to or msg_id or thread_id
    else:
        sender = payload_json.get("from") or payload_json.get("sender") or ""
        subject = payload_json.get("subject")
        body_text = payload_json.get("body") or payload_json.get("text")
        thread_id = payload_json.get("thread_id") or payload_json.get("conversation_id")
        attachments = payload_json.get("attachments") if isinstance(payload_json.get("attachments"), list) else []

    participant = None
    if sender:
        participant = _get_or_create_participant(
            db,
            handle=sender,
            channel_type=channel.type,
            display_name=payload_json.get("sender_name"),
            customer_id=None,
        )

    conv = _get_or_create_conversation(
        db,
        channel=channel,
        external_thread_id=thread_id,
        customer_id=None,
        ticket_id=None,
        subject=subject,
    )

    _persist_message(
        db,
        conversation=conv,
        direction="inbound",
        body=body_text,
        subject=subject,
        participant=participant,
        customer_id=None,
        ticket_id=None,
        channel=channel,
        agent=None,
        metadata={"raw_event_id": raw_event.id},
        attachments=attachments,
    )

    raw_event.processed = True
    db.commit()
    return {"status": "ok", "event_id": raw_event.id, "conversation_id": conv.id}


# -----------------------------------------------------------------------------
# Channel management
# -----------------------------------------------------------------------------


@router.get(
    "/channels",
    dependencies=[Depends(Require("support:read"))],
)
async def list_channels(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    channels = db.query(OmniChannel).all()
    return {
        "total": len(channels),
        "data": [
            {
                "id": ch.id,
                "name": ch.name,
                "type": ch.type,
                "is_active": ch.is_active,
                "config": ch.config,
                "webhook_secret": bool(ch.webhook_secret),
            }
            for ch in channels
        ],
    }


@router.post(
    "/channels",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_channel(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    required = ["name", "type"]
    for field in required:
        if field not in payload or not payload[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    existing = db.query(OmniChannel).filter(OmniChannel.name == payload["name"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel name already exists")

    channel = OmniChannel(
        name=payload["name"],
        type=payload["type"],
        config=payload.get("config") or {},
        webhook_secret=payload.get("webhook_secret"),
        is_active=payload.get("is_active", True),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    # If email channel has IMAP config, enqueue an immediate poll to seed data
    if channel.type == "email":
        try:
            poll_email_channel.delay(channel.id)
        except Exception:
            pass
    return {"id": channel.id}


@router.patch(
    "/channels/{channel_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_channel(
    channel_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if "name" in payload:
        exists = (
            db.query(OmniChannel)
            .filter(OmniChannel.name == payload["name"], OmniChannel.id != channel_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Channel name already exists")
        channel.name = payload["name"]
    if "type" in payload and payload["type"]:
        channel.type = payload["type"]
    if "config" in payload and payload["config"] is not None:
        channel.config = payload["config"]
    if "webhook_secret" in payload:
        channel.webhook_secret = payload["webhook_secret"]
    if "is_active" in payload and payload["is_active"] is not None:
        channel.is_active = bool(payload["is_active"])

    db.commit()
    db.refresh(channel)
    return {"id": channel.id}


@router.delete(
    "/channels/{channel_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
    response_model=None,
)
async def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
):
    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.delete(channel)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/channels/{channel_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed information about a specific channel."""
    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get basic stats
    event_count = db.query(func.count(OmniWebhookEvent.id)).filter(
        OmniWebhookEvent.channel_id == channel_id
    ).scalar()
    processed_count = db.query(func.count(OmniWebhookEvent.id)).filter(
        OmniWebhookEvent.channel_id == channel_id,
        OmniWebhookEvent.processed == True
    ).scalar()
    last_event = db.query(func.max(OmniWebhookEvent.created_at)).filter(
        OmniWebhookEvent.channel_id == channel_id
    ).scalar()

    return {
        "id": channel.id,
        "name": channel.name,
        "type": channel.type,
        "is_active": channel.is_active,
        "config": channel.config,
        "webhook_secret_configured": bool(channel.webhook_secret),
        "webhook_url": f"/api/omni/webhooks/{channel.name}",
        "stats": {
            "total_events": event_count,
            "processed_events": processed_count,
            "last_event_at": last_event.isoformat() if last_event else None,
        },
        "created_at": channel.created_at.isoformat() if hasattr(channel, 'created_at') and channel.created_at else None,
    }


@router.get(
    "/channels/{channel_id}/webhook-events",
    dependencies=[Depends(Require("support:read"))],
)
async def list_channel_webhook_events(
    channel_id: int,
    processed: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List webhook events received for a specific channel."""
    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    query = db.query(OmniWebhookEvent).filter(OmniWebhookEvent.channel_id == channel_id)

    if processed is not None:
        query = query.filter(OmniWebhookEvent.processed == processed)

    total = query.count()
    events = query.order_by(OmniWebhookEvent.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "channel_id": channel_id,
        "channel_name": channel.name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "events": [
            {
                "id": e.id,
                "provider_event_id": e.provider_event_id,
                "processed": e.processed,
                "headers": e.headers,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.get(
    "/channels/{channel_id}/webhook-events/{event_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_channel_webhook_event(
    channel_id: int,
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed information about a specific webhook event including payload."""
    event = db.query(OmniWebhookEvent).filter(
        OmniWebhookEvent.id == event_id,
        OmniWebhookEvent.channel_id == channel_id,
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found")

    return {
        "id": event.id,
        "channel_id": event.channel_id,
        "provider_event_id": event.provider_event_id,
        "processed": event.processed,
        "payload": event.payload,
        "headers": event.headers,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@router.get(
    "/channels/{channel_id}/stats",
    dependencies=[Depends(Require("support:read"))],
)
async def get_channel_stats(
    channel_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get webhook statistics for a channel."""
    from datetime import timedelta
    from sqlalchemy import cast, Date

    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Overall stats
    total = db.query(func.count(OmniWebhookEvent.id)).filter(
        OmniWebhookEvent.channel_id == channel_id,
        OmniWebhookEvent.created_at >= cutoff,
    ).scalar()

    processed = db.query(func.count(OmniWebhookEvent.id)).filter(
        OmniWebhookEvent.channel_id == channel_id,
        OmniWebhookEvent.created_at >= cutoff,
        OmniWebhookEvent.processed == True,
    ).scalar()

    # Daily breakdown
    daily_query = db.query(
        cast(OmniWebhookEvent.created_at, Date).label("date"),
        func.count(OmniWebhookEvent.id).label("count"),
    ).filter(
        OmniWebhookEvent.channel_id == channel_id,
        OmniWebhookEvent.created_at >= cutoff,
    ).group_by(
        cast(OmniWebhookEvent.created_at, Date)
    ).order_by(
        cast(OmniWebhookEvent.created_at, Date)
    ).all()

    daily_data = [{"date": str(row.date), "count": row.count} for row in daily_query]

    return {
        "channel_id": channel_id,
        "channel_name": channel.name,
        "period_days": days,
        "summary": {
            "total_events": total,
            "processed": processed,
            "pending": total - processed,
            "success_rate": round((processed / total) * 100, 1) if total > 0 else None,
        },
        "daily": daily_data,
    }


@router.post(
    "/channels/{channel_id}/rotate-secret",
    dependencies=[Depends(Require("support:write"))],
)
async def rotate_channel_webhook_secret(
    channel_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generate a new webhook secret for a channel.

    Returns the new secret (only shown once).
    """
    import secrets as secrets_module

    channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Generate new secret
    new_secret = secrets_module.token_urlsafe(32)
    channel.webhook_secret = new_secret
    db.commit()

    logger.info(f"Channel webhook secret rotated: {channel.name}")

    return {
        "channel_id": channel_id,
        "channel_name": channel.name,
        "webhook_secret": new_secret,
        "webhook_url": f"/api/omni/webhooks/{channel.name}",
        "message": "Secret rotated. Update your provider to use the new secret.",
    }


@router.post(
    "/messages/send",
    dependencies=[Depends(Require("support:write"))],
)
async def send_message(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Unified outbound send endpoint. Persists message and queues adapter-specific delivery."""
    required = ["channel", "to", "body"]
    for field in required:
        if field not in payload or not payload[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    channel = _get_channel_or_404(db, payload["channel"])
    agent = None
    if payload.get("agent_id"):
        agent = db.query(Agent).filter(Agent.id == payload["agent_id"]).first()

    # Resolve conversation (existing or new)
    conv = None
    if payload.get("conversation_id"):
        conv = db.query(OmniConversation).filter(OmniConversation.id == payload["conversation_id"]).first()
    if not conv:
        conv = OmniConversation(
            channel_id=channel.id,
            external_thread_id=None,
            customer_id=None,
            ticket_id=payload.get("ticket_id"),
            subject=payload.get("subject"),
            status="open",
        )
        db.add(conv)
        db.flush()

    participant = _get_or_create_participant(
        db,
        handle=payload["to"],
        channel_type=channel.type,
        display_name=None,
        customer_id=None,
    )

    msg = _persist_message(
        db,
        conversation=conv,
        direction="outbound",
        body=payload["body"],
        subject=payload.get("subject"),
        participant=participant,
        customer_id=None,
        ticket_id=payload.get("ticket_id"),
        channel=channel,
        agent=agent,
        metadata=payload.get("metadata"),
        attachments=payload.get("attachments") or [],
    )

    # Attempt immediate delivery for email; otherwise leave pending for adapter job
    if channel.type == "email":
        try:
            _send_email_via_smtp(
                channel,
                to_address=payload["to"],
                subject=payload.get("subject"),
                body=payload["body"],
            )
            msg.delivery_status = "sent"
            msg.sent_at = datetime.utcnow()
        except HTTPException:
            raise
        except Exception as exc:
            msg.delivery_status = "failed"
            msg.meta = (msg.meta or {}) | {"send_error": str(exc)}
    else:
        msg.delivery_status = "pending"

    db.commit()

    return {
        "message_id": msg.id,
        "conversation_id": conv.id,
        "channel": channel.name,
        "delivery_status": msg.delivery_status,
    }


# -----------------------------------------------------------------------------
# Conversations and messages list
# -----------------------------------------------------------------------------


@router.get(
    "/conversations",
    dependencies=[Depends(Require("support:read"))],
)
async def list_conversations(
    ticket_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(OmniConversation)
    if ticket_id:
        query = query.filter(OmniConversation.ticket_id == ticket_id)
    if customer_id:
        query = query.filter(OmniConversation.customer_id == customer_id)
    if channel:
        ch = db.query(OmniChannel.id).filter(OmniChannel.name == channel).first()
        if not ch:
            return {"total": 0, "data": []}
        query = query.filter(OmniConversation.channel_id == ch.id)
    if status:
        query = query.filter(OmniConversation.status == status)
    if agent_id:
        # conversations with messages by agent_id
        query = query.filter(
            OmniConversation.id.in_(
                db.query(OmniMessage.conversation_id).filter(OmniMessage.agent_id == agent_id)
            )
        )
    if team_id:
        # conversations with messages assigned to agents in the team
        agent_ids = [row.agent_id for row in db.query(TeamMember).filter(TeamMember.team_id == team_id).all()]
        if agent_ids:
            query = query.filter(
                OmniConversation.id.in_(
                    db.query(OmniMessage.conversation_id).filter(OmniMessage.agent_id.in_(agent_ids))
                )
            )
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
            query = query.filter(OmniConversation.created_at >= start_dt)
        except ValueError:
            pass
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
            query = query.filter(OmniConversation.created_at <= end_dt)
        except ValueError:
            pass

    total = query.count()
    convs = query.order_by(OmniConversation.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": c.id,
                "channel_id": c.channel_id,
                "external_thread_id": c.external_thread_id,
                "ticket_id": c.ticket_id,
                "customer_id": c.customer_id,
                "status": c.status,
                "subject": c.subject,
                "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            }
            for c in convs
        ],
    }


@router.get(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(Require("support:read"))],
)
async def list_messages(
    conversation_id: int,
    direction: Optional[str] = None,
    delivery_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(OmniMessage).filter(OmniMessage.conversation_id == conversation_id)
    if direction:
        query = query.filter(OmniMessage.direction == direction)
    if delivery_status:
        query = query.filter(OmniMessage.delivery_status == delivery_status)
    total = query.count()
    messages = query.order_by(OmniMessage.created_at.asc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": m.id,
                "direction": m.direction,
                "body": m.body,
                "subject": m.subject,
                "participant_id": m.participant_id,
                "agent_id": m.agent_id,
                "delivery_status": m.delivery_status,
                "provider_message_id": m.provider_message_id,
                "meta": m.meta,
                "created_at": m.created_at.isoformat() if m.created_at else None,
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "url": att.url,
                "mime_type": att.mime_type,
                "size_bytes": att.size_bytes,
            }
            for att in m.attachments
        ],
    }
            for m in messages
        ],
    }
