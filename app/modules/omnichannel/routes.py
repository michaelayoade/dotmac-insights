"""
Omnichannel Routes - Unified Inbox & Conversations with SSR + HTMX.

Permission Requirements:
- support:read - View conversations and messages
- support:write - Send messages, update status

Refactored to use ConversationService and MessageService for all business logic.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.omni import (
    OmniConversation,
    OmniMessage,
    OmniParticipant,
    ConversationStatus,
    ConversationPriority,
)
from app.core.security import is_htmx_request, htmx_toast
from app.services.support import (
    ConversationService,
    MessageService,
    ConversationFilters,
    OutboundMessageData,
    ConversationNotFoundError,
)
from app.services.omnichannel import OmniChannelService
from app.services.types import PaginationParams

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


def get_conversation_service(db, user) -> ConversationService:
    """Get a ConversationService instance for web routes."""
    return ConversationService(db, principal=user)


def get_message_service(db, user) -> MessageService:
    """Get a MessageService instance for web routes."""
    return MessageService(db, principal=user)


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
    service = get_conversation_service(db, user)
    channel_service = OmniChannelService(db, principal=user)

    # Build filters
    filters = ConversationFilters(
        search=q,
        status=status,
        channel_id=channel,
        priority=priority,
    )

    # Get paginated results using service
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = service.list(
        filters=filters,
        pagination=pagination,
        sort_by="last_message_at",
        sort_order="desc",
    )

    conversations = result.items
    total = result.total

    # Get all channels for filter dropdown
    channels = channel_service.list_active_channels()

    # Get stats using service
    inbox_stats = service.get_stats()
    stats = {
        "open_count": inbox_stats.open_conversations,
        "pending_count": inbox_stats.pending_conversations,
        "resolved_count": inbox_stats.resolved_conversations,
        "urgent_count": inbox_stats.unassigned_conversations,
    }

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
    service = get_conversation_service(db, user)

    try:
        conv_with_msgs = service.get_with_messages(conversation_id, limit=100)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = conv_with_msgs.conversation.subject or "Conversation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Inbox", "href": "/inbox"},
        {"label": conv_with_msgs.conversation.subject or f"Conversation #{conv_with_msgs.conversation.id}"},
    ])
    context["conversation"] = conv_with_msgs.conversation
    context["messages"] = conv_with_msgs.messages
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
    service = get_conversation_service(db, user)

    try:
        conv_with_msgs = service.get_with_messages(conversation_id, limit=100)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["conversation"] = conv_with_msgs.conversation
    context["messages"] = conv_with_msgs.messages

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
    conv_service = get_conversation_service(db, user)
    msg_service = get_message_service(db, user)

    try:
        conversation = conv_service.get(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    form = await request.form()
    body = _form_str(form, "body")

    if not body:
        htmx_toast(response, "Message cannot be empty", "error")
        return await conversation_messages(request, response, user, csrf_token, db, conversation_id)

    # Create outbound message using MessageService
    message_data = OutboundMessageData(
        conversation_id=conversation_id,
        body=body,
        channel_id=conversation.channel_id,
        agent_id=user.id if user else None,
    )
    msg_service.create_outbound(message_data)
    db.commit()

    htmx_toast(response, "Reply sent", "success")
    return await conversation_messages(request, response, user, csrf_token, db, conversation_id)


@router.post("/{conversation_id}/status", dependencies=[RequireSupportWrite])
async def update_conversation_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    conversation_id: int,
):
    """Update conversation status."""
    service = get_conversation_service(db, user)

    form = await request.form()
    new_status = _form_str(form, "status")

    if not new_status or new_status not in [s.value for s in ConversationStatus]:
        htmx_toast(response, "Invalid status", "error")
        return Response(status_code=204)

    try:
        service.update_status(conversation_id, new_status)
        db.commit()
        htmx_toast(response, f"Status updated to {new_status}", "success")
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return Response(status_code=204)


@router.post("/{conversation_id}/star", dependencies=[RequireSupportWrite])
async def toggle_conversation_star(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    conversation_id: int,
):
    """Toggle conversation star."""
    service = get_conversation_service(db, user)

    try:
        # Get current state to toggle
        conversation = service.get(conversation_id)
        new_starred = not conversation.is_starred
        conversation = service.star(conversation_id, new_starred)
        db.commit()

        action = "starred" if new_starred else "unstarred"
        htmx_toast(response, f"Conversation {action}", "success")
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return Response(status_code=204)
