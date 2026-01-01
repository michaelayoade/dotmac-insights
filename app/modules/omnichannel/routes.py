"""
Omnichannel Routes - Unified Inbox & Conversations with SSR + HTMX.

Permission Requirements:
- support:read - View conversations and messages
- support:write - Send messages, update status
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.omni import (
    OmniChannel,
    OmniConversation,
    OmniMessage,
    OmniParticipant,
    ConversationStatus,
    ConversationPriority,
)
from app.core.security import is_htmx_request, htmx_toast

# Permission dependencies
RequireSupportRead = Depends(require_scope("support:read"))
RequireSupportWrite = Depends(require_scope("support:write"))

router = APIRouter(prefix="/inbox", tags=["omnichannel"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def get_status_options():
    """Get status options for filter dropdown."""
    return [
        {"value": s.value, "label": s.value.title()}
        for s in ConversationStatus
    ]


def get_priority_options():
    """Get priority options for filter dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in ConversationPriority
    ]


def get_inbox_stats(db) -> dict:
    """Calculate inbox statistics."""
    open_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == ConversationStatus.OPEN.value
    ).scalar() or 0

    pending_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == ConversationStatus.PENDING.value
    ).scalar() or 0

    resolved_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == ConversationStatus.RESOLVED.value
    ).scalar() or 0

    urgent_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.priority == ConversationPriority.URGENT.value,
        OmniConversation.status.in_([
            ConversationStatus.OPEN.value,
            ConversationStatus.PENDING.value
        ])
    ).scalar() or 0

    return {
        "open_count": open_count,
        "pending_count": pending_count,
        "resolved_count": resolved_count,
        "urgent_count": urgent_count,
    }


@router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def inbox_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    channel: Optional[int] = Query(None, description="Filter by channel ID"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Inbox page - conversations list."""
    # Build query
    query = db.query(OmniConversation)

    # Search
    if q:
        search_filter = or_(
            OmniConversation.subject.ilike(f"%{q}%"),
            OmniConversation.contact_name.ilike(f"%{q}%"),
            OmniConversation.contact_email.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(OmniConversation.status == status)
    if channel:
        query = query.filter(OmniConversation.channel_id == channel)
    if priority:
        query = query.filter(OmniConversation.priority == priority)

    # Count total
    total = query.count()

    # Sort by last message, then created
    query = query.order_by(
        OmniConversation.last_message_at.desc().nullsfirst(),
        OmniConversation.created_at.desc()
    )

    # Paginate
    offset = (page - 1) * per_page
    conversations = query.offset(offset).limit(per_page).all()

    # Get all channels for filter dropdown
    channels = db.query(OmniChannel).filter(OmniChannel.is_active == True).all()

    # Get stats
    stats = get_inbox_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["conversations"] = conversations
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_channel"] = channel
    context["current_priority"] = priority
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["channels"] = channels
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/omnichannel/templates/partials/conversations_list.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Inbox"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Inbox"},
    ])

    template = templates.get_template("modules/omnichannel/templates/pages/inbox.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def inbox_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    channel: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Conversations list partial for HTMX updates."""
    return await inbox_list(
        request, response, user, csrf_token, db,
        q, status, channel, priority, page, per_page
    )


@router.get("/{conversation_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def conversation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    conversation_id: int,
):
    """Conversation detail page with message thread."""
    conversation = db.query(OmniConversation).filter(
        OmniConversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    messages = db.query(OmniMessage).filter(
        OmniMessage.conversation_id == conversation_id
    ).order_by(OmniMessage.created_at.asc()).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = conversation.subject or "Conversation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Inbox", "href": "/inbox"},
        {"label": conversation.subject or f"Conversation #{conversation.id}"},
    ])
    context["conversation"] = conversation
    context["messages"] = messages
    context["status_options"] = get_status_options()

    template = templates.get_template("modules/omnichannel/templates/pages/conversation.html")
    return HTMLResponse(template.render(context))


@router.get("/{conversation_id}/messages", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def conversation_messages(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    conversation_id: int,
):
    """Messages thread partial for HTMX polling."""
    conversation = db.query(OmniConversation).filter(
        OmniConversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.query(OmniMessage).filter(
        OmniMessage.conversation_id == conversation_id
    ).order_by(OmniMessage.created_at.asc()).all()

    context = get_base_context(request, response, user, csrf_token)
    context["conversation"] = conversation
    context["messages"] = messages

    template = templates.get_template("modules/omnichannel/templates/partials/messages_thread.html")
    return HTMLResponse(template.render(context))


@router.post("/{conversation_id}/reply", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def conversation_reply(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    conversation_id: int,
    _: CSRFProtect,
):
    """Send a reply to a conversation."""
    conversation = db.query(OmniConversation).filter(
        OmniConversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    form = await request.form()
    body = _form_str(form, "body")

    if not body:
        htmx_toast(response, "Message cannot be empty", "error")
        return await conversation_messages(request, response, user, csrf_token, db, conversation_id)

    # Create outbound message
    message = OmniMessage(
        conversation_id=conversation_id,
        direction="outbound",
        body=body,
        channel_id=conversation.channel_id,
        delivery_status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)

    # Update conversation
    conversation.last_message_at = datetime.now(timezone.utc)
    conversation.message_count = (conversation.message_count or 0) + 1

    # Set first response time if not set
    if not conversation.first_response_at:
        conversation.first_response_at = datetime.now(timezone.utc)

    db.commit()

    htmx_toast(response, "Reply sent", "success")
    return await conversation_messages(request, response, user, csrf_token, db, conversation_id)


@router.post("/{conversation_id}/status", dependencies=[RequireSupportWrite])
async def update_conversation_status(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    conversation_id: int,
):
    """Update conversation status."""
    conversation = db.query(OmniConversation).filter(
        OmniConversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status and new_status in [s.value for s in ConversationStatus]:
        conversation.status = new_status

        # Track resolved time
        if new_status == ConversationStatus.RESOLVED.value:
            conversation.resolved_at = datetime.now(timezone.utc)
        else:
            conversation.resolved_at = None

        db.commit()
        htmx_toast(response, f"Status updated to {new_status}", "success")
    else:
        htmx_toast(response, "Invalid status", "error")

    return Response(status_code=204)


@router.post("/{conversation_id}/star", dependencies=[RequireSupportWrite])
async def toggle_conversation_star(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    conversation_id: int,
):
    """Toggle conversation star."""
    conversation = db.query(OmniConversation).filter(
        OmniConversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.is_starred = not conversation.is_starred
    db.commit()

    action = "starred" if conversation.is_starred else "unstarred"
    htmx_toast(response, f"Conversation {action}", "success")

    return Response(status_code=204)
