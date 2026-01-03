"""Ticket management endpoints: CRUD, child tables, assignments."""
from __future__ import annotations

import re
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_

from app.database import get_db
from app.models.ticket import (
    Ticket, TicketStatus, TicketPriority,
    HDTicketComment, HDTicketActivity, TicketCommunication, HDTicketDependency
)
from app.models.party import Party, CustomerAccount
from app.models.agent import Agent, Team, TeamMember
from app.models.auth import User
from app.models.support_tags import TicketTag, TicketCustomField, CustomFieldType
from app.auth import Principal, Require, get_current_principal
from app.cache import cached, CACHE_TTL
from app.services.errors import NotFoundError, ServiceError, ValidationError, DuplicateError
from app.services.support.ticket_types import (
    ActivityData,
    AssignmentData,
    CommentData,
    CommunicationData,
    DependencyData,
    MergeData,
    SLAUpdateData,
    SplitData,
    TicketCreateData,
    TicketFilters,
    TicketUpdateData,
)
from app.services.support.types import (
    TagCreate,
    TagUpdate,
    CustomFieldCreate,
    CustomFieldUpdate,
)
from app.services.support.tickets import TicketService
from app.services.types import PaginationParams

from .helpers import (
    parse_ticket_status, parse_ticket_priority, generate_local_ticket_number,
    serialize_ticket_brief, serialize_comment, serialize_activity,
    serialize_communication, serialize_dependency
)

router = APIRouter()

# Shared RBAC dependencies: accept either tickets:* or support:* scopes
ticket_read_dep = Depends(Require("tickets:read", "support:read"))
ticket_write_dep = Depends(Require("tickets:write", "support:write"))


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------


def get_ticket_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> TicketService:
    """Dependency to get a TicketService instance."""
    return TicketService(db, principal)


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def _validate_tags(db: Session, tags: Optional[List[str]]) -> List[str]:
    """Ensure provided tags exist and are active; returns deduped list."""
    if not tags:
        return []
    clean = [t.strip() for t in tags if t and t.strip()]
    clean = list(dict.fromkeys(clean))  # preserve order, de-dupe
    if not clean:
        return []

    existing = db.query(TicketTag).filter(
        TicketTag.name.in_(clean),
        TicketTag.is_active == True,
    ).all()
    found = {t.name for t in existing}
    missing = [t for t in clean if t not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown or inactive tags: {missing}")
    return clean


def _validate_watchers(db: Session, watcher_ids: Optional[List[int]]) -> List[int]:
    """Ensure watcher IDs refer to existing users; returns deduped list."""
    if not watcher_ids:
        return []
    unique_ids = list(dict.fromkeys([wid for wid in watcher_ids if wid is not None]))
    if not unique_ids:
        return []
    rows = db.query(User.id).filter(User.id.in_(unique_ids)).all()
    found_ids = {row.id for row in rows}
    missing = [wid for wid in unique_ids if wid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown watcher user_ids: {missing}")
    return unique_ids


def _validate_custom_fields(db: Session, custom_fields: Optional[dict]) -> dict:
    """Validate custom field payload against definitions; returns sanitized dict."""
    if custom_fields is None:
        return {}
    if not isinstance(custom_fields, dict):
        raise HTTPException(status_code=400, detail="custom_fields must be an object")

    keys = list(custom_fields.keys())
    if not keys:
        return {}

    defs = db.query(TicketCustomField).filter(
        TicketCustomField.field_key.in_(keys),
        TicketCustomField.is_active == True,
    ).all()
    def_map = {f.field_key: f for f in defs}

    if len(def_map) != len(keys):
        missing = [k for k in keys if k not in def_map]
        raise HTTPException(status_code=400, detail=f"Unknown or inactive custom_fields: {missing}")

    # Enforce required fields
    required_missing = [f.field_key for f in def_map.values() if f.is_required and f.field_key not in custom_fields]
    if required_missing:
        raise HTTPException(status_code=400, detail=f"Missing required custom_fields: {required_missing}")

    sanitized: Dict[str, Any] = {}
    for key, value in custom_fields.items():
        field = def_map[key]
        ftype = field.field_type or CustomFieldType.TEXT.value

        # Type checks
        if ftype == CustomFieldType.TEXT.value or ftype == CustomFieldType.URL.value or ftype == CustomFieldType.EMAIL.value:
            if value is None:
                sanitized[key] = value
            elif not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be a string")
            else:
                sanitized[key] = value
        elif ftype == CustomFieldType.NUMBER.value:
            if not isinstance(value, (int, float)):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be a number")
            sanitized[key] = value
        elif ftype == CustomFieldType.DROPDOWN.value:
            options = [opt.get("value") for opt in (field.options or []) if isinstance(opt, dict)]
            if value not in options:
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be one of {options}")
            sanitized[key] = value
        elif ftype == CustomFieldType.MULTI_SELECT.value:
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be a list")
            options = [opt.get("value") for opt in (field.options or []) if isinstance(opt, dict)]
            invalid = [v for v in value if v not in options]
            if invalid:
                raise HTTPException(status_code=400, detail=f"Field '{key}' has invalid options: {invalid}")
            sanitized[key] = value
        elif ftype == CustomFieldType.DATE.value:
            if not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be an ISO date string")
            try:
                date.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be an ISO date (YYYY-MM-DD)")
            sanitized[key] = value
        elif ftype == CustomFieldType.DATETIME.value:
            if not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be an ISO datetime string")
            try:
                datetime.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be an ISO datetime")
            sanitized[key] = value
        elif ftype == CustomFieldType.CHECKBOX.value:
            if not isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be a boolean")
            sanitized[key] = value
        else:
            sanitized[key] = value

        # Length and regex constraints for string-like fields
        if isinstance(sanitized.get(key), str):
            sval = sanitized[key]
            if field.min_length is not None and len(sval) < field.min_length:
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be at least {field.min_length} characters")
            if field.max_length is not None and len(sval) > field.max_length:
                raise HTTPException(status_code=400, detail=f"Field '{key}' must be at most {field.max_length} characters")
            if field.regex_pattern:
                try:
                    if not re.fullmatch(field.regex_pattern, sval):
                        raise HTTPException(status_code=400, detail=f"Field '{key}' does not match required pattern")
                except re.error:
                    # Invalid regex in definition; treat as server error
                    raise HTTPException(status_code=500, detail=f"Invalid regex for field '{key}'")

    return sanitized


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TicketBaseRequest(BaseModel):
    subject: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    ticket_type: Optional[str] = None
    issue_type: Optional[str] = None
    customer_account_id: Optional[int] = None
    party_id: Optional[int] = None
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    resolution_by: Optional[datetime] = None
    response_by: Optional[datetime] = None
    resolution_team: Optional[str] = None
    resolution: Optional[str] = None
    resolution_details: Optional[str] = None
    resolution_date: Optional[datetime] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    region: Optional[str] = None
    base_station: Optional[str] = None
    tags: Optional[List[str]] = None
    watchers: Optional[List[int]] = None
    custom_fields: Optional[dict] = None
    merged_into_id: Optional[int] = None
    parent_ticket_id: Optional[int] = None

    @field_validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            TicketStatus(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid status: {value}. Allowed: {[s.value for s in TicketStatus]}")

    @field_validator("priority")
    def _validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            TicketPriority(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid priority: {value}. Allowed: {[p.value for p in TicketPriority]}")


class TicketCreateRequest(TicketBaseRequest):
    subject: str
    priority: str = TicketPriority.MEDIUM.value
    status: str = TicketStatus.OPEN.value


class TicketUpdateRequest(TicketBaseRequest):
    pass


class TicketCommentRequest(BaseModel):
    comment: str
    comment_type: Optional[str] = None
    commented_by: Optional[str] = None
    commented_by_name: Optional[str] = None
    is_public: bool = True
    comment_date: Optional[datetime] = None


class TicketCommentUpdateRequest(BaseModel):
    comment: Optional[str] = None
    comment_type: Optional[str] = None
    commented_by: Optional[str] = None
    commented_by_name: Optional[str] = None
    is_public: Optional[bool] = None
    comment_date: Optional[datetime] = None


class TicketActivityRequest(BaseModel):
    activity_type: Optional[str] = None
    activity: str
    owner: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    activity_date: Optional[datetime] = None


class TicketActivityUpdateRequest(BaseModel):
    activity_type: Optional[str] = None
    activity: Optional[str] = None
    owner: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    activity_date: Optional[datetime] = None


class TicketDependencyRequest(BaseModel):
    depends_on_ticket_id: Optional[int] = None
    depends_on_erpnext_id: Optional[str] = None
    depends_on_subject: Optional[str] = None
    depends_on_status: Optional[str] = None


class TicketDependencyUpdateRequest(BaseModel):
    depends_on_ticket_id: Optional[int] = None
    depends_on_erpnext_id: Optional[str] = None
    depends_on_subject: Optional[str] = None
    depends_on_status: Optional[str] = None


class TicketCommunicationRequest(BaseModel):
    communication_type: Optional[str] = None
    communication_medium: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    sender: Optional[str] = None
    sender_full_name: Optional[str] = None
    recipients: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    sent_or_received: Optional[str] = None
    read_receipt: bool = False
    delivery_status: Optional[str] = None
    communication_date: Optional[datetime] = None


class TicketCommunicationUpdateRequest(BaseModel):
    communication_type: Optional[str] = None
    communication_medium: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    sender: Optional[str] = None
    sender_full_name: Optional[str] = None
    recipients: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    sent_or_received: Optional[str] = None
    read_receipt: Optional[bool] = None
    delivery_status: Optional[str] = None
    communication_date: Optional[datetime] = None


class TicketAssigneeRequest(BaseModel):
    team_id: Optional[int] = None
    member_id: Optional[int] = None
    employee_id: Optional[int] = None
    assigned_to: Optional[str] = None
    agent_id: Optional[int] = None
    tags: Optional[List[str]] = None
    watchers: Optional[List[int]] = None
    custom_fields: Optional[dict] = None
    merged_into_id: Optional[int] = None
    parent_ticket_id: Optional[int] = None


class TicketSLARequest(BaseModel):
    response_by: Optional[datetime] = None
    resolution_by: Optional[datetime] = None
    reason: Optional[str] = None


# --- Tag Definition Models ---

class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20, pattern=r"^#[A-Fa-f0-9]{6}$")
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = True


class TagUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20, pattern=r"^#[A-Fa-f0-9]{6}$")
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


# --- Custom Field Definition Models ---

class CustomFieldOptionItem(BaseModel):
    value: str
    label: str


class CustomFieldCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    field_key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    description: Optional[str] = Field(None, max_length=500)
    field_type: str = CustomFieldType.TEXT.value
    options: Optional[List[CustomFieldOptionItem]] = None
    default_value: Optional[str] = None
    is_required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex_pattern: Optional[str] = None
    display_order: int = 100
    show_in_list: bool = False
    show_in_create: bool = True
    is_active: bool = True

    @field_validator("field_type")
    def _validate_field_type(cls, value: str) -> str:
        try:
            CustomFieldType(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid field_type: {value}. Allowed: {[t.value for t in CustomFieldType]}")


class CustomFieldUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    field_type: Optional[str] = None
    options: Optional[List[CustomFieldOptionItem]] = None
    default_value: Optional[str] = None
    is_required: Optional[bool] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex_pattern: Optional[str] = None
    display_order: Optional[int] = None
    show_in_list: Optional[bool] = None
    show_in_create: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("field_type")
    def _validate_field_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            CustomFieldType(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid field_type: {value}. Allowed: {[t.value for t in CustomFieldType]}")


# --- Ticket Tag/Watcher/Merge Models ---

class TicketTagsRequest(BaseModel):
    tags: List[str]


class TicketWatchersRequest(BaseModel):
    user_ids: List[int]


class TicketMergeRequest(BaseModel):
    source_ticket_ids: List[int]
    close_source_tickets: bool = True


class TicketSplitRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    description: Optional[str] = None
    copy_tags: bool = True
    copy_custom_fields: bool = False


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("support-dashboard", ttl=CACHE_TTL["short"])
async def get_support_dashboard(
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Support dashboard with ticket and conversation metrics."""
    from app.models.conversation import Conversation, ConversationStatus
    from sqlalchemy import and_
    from datetime import timedelta

    # Get basic ticket stats from service
    ticket_stats = service.get_dashboard_stats()
    status_counts = ticket_stats["status_distribution"]
    priority_counts = ticket_stats["priority_distribution"]

    total_tickets: int = sum(status_counts.values())
    open_tickets: int = ticket_stats["total_open"]

    # SLA metrics (complex analytics - keep as direct queries for now)
    sla_met = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
        Ticket.resolution_date <= Ticket.resolution_by,
        Ticket.is_deleted == False,
    ).scalar() or 0

    sla_breached = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        or_(
            Ticket.resolution_date > Ticket.resolution_by,
            and_(
                Ticket.resolution_date.is_(None),
                Ticket.resolution_by < func.current_timestamp()
            )
        ),
        Ticket.is_deleted == False,
    ).scalar() or 0

    sla_total = sla_met + sla_breached
    sla_attainment = round(sla_met / sla_total * 100, 1) if sla_total > 0 else 0

    # Average resolution time (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    avg_resolution = db.query(
        func.avg(func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600)
    ).filter(
        Ticket.resolution_date.isnot(None),
        Ticket.opening_date.isnot(None),
        Ticket.resolution_date >= thirty_days_ago,
        Ticket.is_deleted == False,
    ).scalar() or 0

    # Conversation metrics
    conv_by_status = db.query(
        Conversation.status,
        func.count(Conversation.id).label("count")
    ).group_by(Conversation.status).all()

    conv_status_counts: Dict[str, int] = {row.status.value: int(getattr(row, "count", 0) or 0) for row in conv_by_status}
    total_conversations: int = sum(conv_status_counts.values())
    open_conversations: int = conv_status_counts.get("open", 0) + conv_status_counts.get("pending", 0)

    # Overdue tickets
    overdue_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_by < func.current_timestamp(),
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD]),
        Ticket.is_deleted == False,
    ).scalar() or 0

    # Unassigned tickets
    unassigned = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        Ticket.assigned_to.is_(None),
        Ticket.assigned_employee_id.is_(None),
        Ticket.is_deleted == False,
    ).scalar() or 0

    return {
        "tickets": {
            "total": total_tickets,
            "open": open_tickets,
            "resolved": status_counts.get("resolved", 0),
            "closed": status_counts.get("closed", 0),
            "on_hold": status_counts.get("on_hold", 0),
        },
        "by_priority": priority_counts,
        "sla": {
            "met": sla_met,
            "breached": sla_breached,
            "attainment_rate": sla_attainment,
        },
        "metrics": {
            "avg_resolution_hours": round(float(avg_resolution), 1),
            "overdue_tickets": overdue_tickets,
            "unassigned_tickets": unassigned,
        },
        "conversations": {
            "total": total_conversations,
            "open": open_conversations,
            "resolved": conv_status_counts.get("resolved", 0),
        },
    }


# =============================================================================
# TICKET CRUD
# =============================================================================

@router.get("/tickets", dependencies=[ticket_read_dep])
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer_account_id: Optional[int] = None,
    party_id: Optional[int] = None,
    ticket_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    unassigned_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """List tickets with filtering and pagination."""
    # Build filters
    filters = TicketFilters(
        status=parse_ticket_status(status) if status else None,
        priority=parse_ticket_priority(priority) if priority else None,
        customer_account_id=customer_account_id,
        party_id=party_id,
        ticket_type=ticket_type,
        assigned_to=assigned_to,
        search=search,
        overdue_only=overdue_only,
        unassigned_only=unassigned_only,
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

    # Get paginated results using service
    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_tickets(filters=filters, pagination=pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_ticket_brief(t) for t in result.items],
    }


@router.get("/tickets/{ticket_id}", dependencies=[ticket_read_dep])
def get_ticket(
    ticket_id: int,
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Get detailed ticket information with all child tables."""
    try:
        # Use service with eager loading for child tables
        ticket = service.get_ticket(ticket_id, include_children=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Customer is now eagerly loaded
    customer = None
    if ticket.customer:
        customer = {"id": ticket.customer.id, "name": ticket.customer.name, "email": ticket.customer.email, "phone": ticket.customer.phone}

    comments = [serialize_comment(c) for c in sorted(ticket.comments, key=lambda x: x.idx)]
    activities = [serialize_activity(a) for a in sorted(ticket.activities, key=lambda x: x.idx)]
    communications = [serialize_communication(comm) for comm in ticket.communications]
    depends_on = [serialize_dependency(d) for d in sorted(ticket.depends_on, key=lambda x: x.idx)]

    expenses = [
        {
            "id": e.id,
            "erpnext_id": e.erpnext_id,
            "expense_type": e.expense_type,
            "description": e.description,
            "total_claimed_amount": float(e.total_claimed_amount) if e.total_claimed_amount else 0,
            "total_sanctioned_amount": float(e.total_sanctioned_amount) if e.total_sanctioned_amount else 0,
            "status": e.status.value if e.status else None,
            "expense_date": e.expense_date.isoformat() if e.expense_date else None,
        }
        for e in ticket.expenses
    ]

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status.value if ticket.status else None,
        "priority": ticket.priority.value if ticket.priority else None,
        "ticket_type": ticket.ticket_type,
        "issue_type": ticket.issue_type,
        "assigned_to": ticket.assigned_to,
        "raised_by": ticket.raised_by,
        "resolution_team": ticket.resolution_team,
        "tags": ticket.tags or [],
        "watchers": ticket.watchers or [],
        "custom_fields": ticket.custom_fields or {},
        "merged_into_id": ticket.merged_into_id,
        "merged_tickets": ticket.merged_tickets or [],
        "parent_ticket_id": ticket.parent_ticket_id,
        "csat_sent": ticket.csat_sent,
        "csat_response_id": ticket.csat_response_id,
        "region": ticket.region,
        "base_station": ticket.base_station,
        "sla": {
            "response_by": ticket.response_by.isoformat() if ticket.response_by else None,
            "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
            "first_responded_on": ticket.first_responded_on.isoformat() if ticket.first_responded_on else None,
            "agreement_status": ticket.agreement_status,
            "is_overdue": ticket.is_overdue,
        },
        "resolution": {
            "resolution": ticket.resolution,
            "resolution_details": ticket.resolution_details,
            "resolution_date": ticket.resolution_date.isoformat() if ticket.resolution_date else None,
        },
        "feedback": {
            "rating": ticket.feedback_rating,
            "text": ticket.feedback_text,
        },
        "dates": {
            "opening_date": ticket.opening_date.isoformat() if ticket.opening_date else None,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        },
        "metrics": {
            "time_to_resolution_hours": ticket.time_to_resolution_hours,
        },
        "source": ticket.source.value if ticket.source else None,
        "write_back_status": getattr(ticket, "write_back_status", None),
        "external_ids": {
            "erpnext_id": ticket.erpnext_id,
            "splynx_id": ticket.splynx_id,
        },
        "customer": customer,
        "comments": comments,
        "activities": activities,
        "communications": communications,
        "depends_on": depends_on,
        "expenses": expenses,
    }


@router.get("/tickets/{ticket_id}/full", dependencies=[ticket_read_dep])
@cached("ticket-full-detail", ttl=CACHE_TTL.get("short", 60))
async def get_ticket_full_detail(
    ticket_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """
    Get consolidated ticket detail with all related data in a single call.

    Combines:
    - Ticket details
    - Unified timeline (activities, comments, communications merged & sorted)
    - Attachments
    - Related tickets (dependencies, sub-tickets, merged tickets)
    - Full SLA status with time calculations
    - Assignee details
    """
    now = datetime.now(timezone.utc)
    today = date.today()

    try:
        ticket = service.get_ticket(ticket_id, include_children=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Customer account info
    customer = None
    if ticket.customer_account_id:
        account = (
            db.query(CustomerAccount)
            .filter(CustomerAccount.id == ticket.customer_account_id)
            .first()
        )
        if account:
            party = None
            if account.party_id:
                party = db.query(Party).filter(Party.id == account.party_id).first()
            customer = {
                "id": account.id,
                "party_id": account.party_id,
                "name": party.name if party else None,
                "primary_email": party.primary_email if party else None,
                "primary_phone": party.primary_phone if party else None,
                "status": account.status,
            }

    # Assignee info
    assignee = None
    if ticket.assigned_to:
        agent = db.query(Agent).filter(
            or_(
                Agent.display_name == ticket.assigned_to,
                Agent.email == ticket.assigned_to,
            )
        ).first()
        if agent:
            assignee = {
                "id": agent.id,
                "name": agent.display_name or agent.email,
                "email": agent.email,
                "avatar_url": None,
                "team": ticket.resolution_team,
            }

    # Build unified timeline
    timeline = []

    # Add comments to timeline
    for comment in ticket.comments:
        timeline.append({
            "id": f"comment-{comment.id}",
            "type": "comment",
            "content": comment.comment,
            "author": {
                "id": comment.commented_by,
                "name": comment.commented_by_name or comment.commented_by,
                "role": "public" if comment.is_public else "internal",
            },
            "timestamp": comment.comment_date.isoformat() if comment.comment_date else None,
            "is_internal": not comment.is_public,
            "metadata": {},
        })

    # Add activities to timeline
    for activity in ticket.activities:
        timeline.append({
            "id": f"activity-{activity.id}",
            "type": "activity",
            "content": activity.activity,
            "author": {
                "id": activity.owner,
                "name": activity.owner,
                "role": "system",
            },
            "timestamp": activity.activity_date.isoformat() if activity.activity_date else None,
            "is_internal": True,
            "metadata": {
                "activity_type": activity.activity_type,
            },
        })

    # Add communications to timeline
    for comm in ticket.communications:
        timeline.append({
            "id": f"comm-{comm.id}",
            "type": "communication",
            "content": comm.content,
            "author": {
                "id": comm.sender,
                "name": comm.sender_full_name or comm.sender,
                "role": "external" if comm.communication_type and "email" in comm.communication_type.lower() else "internal",
            },
            "timestamp": comm.communication_date.isoformat() if comm.communication_date else None,
            "is_internal": False,
            "metadata": {
                "subject": comm.subject,
                "communication_type": comm.communication_type,
                "recipients": comm.recipients,
            },
        })

    # Sort timeline by timestamp
    timeline.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

    # Attachments (from communications)
    attachments: list[dict[str, Any]] = []

    # Related tickets
    depends_on_tickets: list[dict[str, Any]] = []
    sub_tickets_list: list[dict[str, Any]] = []
    merged_tickets_list: list[dict[str, Any]] = []
    parent_ticket: Optional[dict[str, Any]] = None

    # Dependencies
    for dep in ticket.depends_on:
        dep_ticket = db.query(Ticket).filter(Ticket.id == dep.depends_on_ticket_id).first()
        if dep_ticket:
            depends_on_tickets.append({
                "id": dep_ticket.id,
                "ticket_number": dep_ticket.ticket_number,
                "subject": dep_ticket.subject,
                "status": dep_ticket.status.value if dep_ticket.status else None,
            })

    # Sub-tickets
    sub_tickets = db.query(Ticket).filter(
        Ticket.parent_ticket_id == ticket.id,
        Ticket.is_deleted == False,
    ).all()
    for sub in sub_tickets:
        sub_tickets_list.append({
            "id": sub.id,
            "ticket_number": sub.ticket_number,
            "subject": sub.subject,
            "status": sub.status.value if sub.status else None,
        })

    # Merged tickets
    if ticket.merged_tickets:
        for merged_id in ticket.merged_tickets:
            merged = db.query(Ticket).filter(Ticket.id == merged_id).first()
            if merged:
                merged_tickets_list.append({
                    "id": merged.id,
                    "ticket_number": merged.ticket_number,
                    "subject": merged.subject,
                    "status": merged.status.value if merged.status else None,
                })

    # Parent ticket
    if ticket.parent_ticket_id:
        parent = db.query(Ticket).filter(Ticket.id == ticket.parent_ticket_id).first()
        if parent:
            parent_ticket = {
                "id": parent.id,
                "ticket_number": parent.ticket_number,
                "subject": parent.subject,
                "status": parent.status.value if parent.status else None,
            }
    related_tickets = {
        "depends_on": depends_on_tickets,
        "sub_tickets": sub_tickets_list,
        "merged_tickets": merged_tickets_list,
        "parent": parent_ticket,
    }

    # SLA status with calculations
    sla_status = {
        "response_by": ticket.response_by.isoformat() if ticket.response_by else None,
        "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
        "first_responded_on": ticket.first_responded_on.isoformat() if ticket.first_responded_on else None,
        "agreement_status": ticket.agreement_status,
        "is_overdue": ticket.is_overdue,
        "response_met": ticket.first_responded_on <= ticket.response_by if ticket.first_responded_on and ticket.response_by else None,
        "resolution_met": None,
        "time_to_resolution_hours": ticket.time_to_resolution_hours,
    }

    # Calculate resolution SLA status
    if ticket.status == TicketStatus.CLOSED and ticket.resolution_date and ticket.resolution_by:
        sla_status["resolution_met"] = ticket.resolution_date <= ticket.resolution_by

    # Time remaining/overdue calculation
    if ticket.resolution_by and ticket.status not in [TicketStatus.CLOSED, TicketStatus.RESOLVED]:
        resolution_deadline = datetime.combine(ticket.resolution_by, datetime.max.time()) if isinstance(ticket.resolution_by, date) else ticket.resolution_by
        if hasattr(resolution_deadline, 'tzinfo') and resolution_deadline.tzinfo is None:
            from datetime import timezone as tz
            resolution_deadline = resolution_deadline.replace(tzinfo=tz.utc)
        time_remaining = resolution_deadline - now
        sla_status["time_remaining_hours"] = max(0, time_remaining.total_seconds() / 3600)
        sla_status["is_breached"] = time_remaining.total_seconds() < 0
    else:
        sla_status["time_remaining_hours"] = None
        sla_status["is_breached"] = False

    return {
        "generated_at": now.isoformat(),

        "ticket": {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "subject": ticket.subject,
            "description": ticket.description,
            "status": ticket.status.value if ticket.status else None,
            "priority": ticket.priority.value if ticket.priority else None,
            "ticket_type": ticket.ticket_type,
            "issue_type": ticket.issue_type,
            "source": ticket.source.value if ticket.source else None,
            "tags": ticket.tags or [],
            "watchers": ticket.watchers or [],
            "custom_fields": ticket.custom_fields or {},
            "region": ticket.region,
            "base_station": ticket.base_station,
            "resolution": ticket.resolution,
            "resolution_details": ticket.resolution_details,
            "resolution_date": ticket.resolution_date.isoformat() if ticket.resolution_date else None,
            "feedback_rating": ticket.feedback_rating,
            "feedback_text": ticket.feedback_text,
            "opening_date": ticket.opening_date.isoformat() if ticket.opening_date else None,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        },

        "customer": customer,
        "assignee": assignee,
        "sla_status": sla_status,
        "timeline": timeline,
        "attachments": attachments,
        "related_tickets": related_tickets,

        "summary": {
            "timeline_count": len(timeline),
            "attachment_count": len(attachments),
            "dependencies_count": len(depends_on_tickets),
            "sub_tickets_count": len(sub_tickets_list),
        },
    }


@router.post("/tickets", dependencies=[ticket_write_dep], status_code=201)
def create_ticket(
    payload: TicketCreateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Create a ticket locally (no upstream ERP write-back)."""
    try:
        data = TicketCreateData(
            subject=payload.subject,
            description=payload.description,
            status=parse_ticket_status(payload.status) or TicketStatus.OPEN,
            priority=parse_ticket_priority(payload.priority) or TicketPriority.MEDIUM,
            ticket_type=payload.ticket_type,
            issue_type=payload.issue_type,
            customer_account_id=payload.customer_account_id,
            party_id=payload.party_id,
            project_id=payload.project_id,
            assigned_to=payload.assigned_to,
            assigned_employee_id=payload.assigned_employee_id,
            resolution_by=payload.resolution_by,
            response_by=payload.response_by,
            resolution_team=payload.resolution_team,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            region=payload.region,
            base_station=payload.base_station,
            tags=payload.tags or [],
            watchers=payload.watchers or [],
            custom_fields=payload.custom_fields or {},
            parent_ticket_id=payload.parent_ticket_id,
        )
        ticket = service.create_ticket(data)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "ticket_number": ticket.ticket_number}
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}", dependencies=[ticket_write_dep])
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update an existing ticket locally."""
    try:
        data = TicketUpdateData(
            subject=payload.subject,
            description=payload.description,
            status=parse_ticket_status(payload.status),
            priority=parse_ticket_priority(payload.priority),
            ticket_type=payload.ticket_type,
            issue_type=payload.issue_type,
            customer_account_id=payload.customer_account_id,
            party_id=payload.party_id,
            project_id=payload.project_id,
            assigned_to=payload.assigned_to,
            assigned_employee_id=payload.assigned_employee_id,
            resolution_by=payload.resolution_by,
            response_by=payload.response_by,
            resolution_team=payload.resolution_team,
            resolution=payload.resolution,
            resolution_details=payload.resolution_details,
            resolution_date=payload.resolution_date,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            region=payload.region,
            base_station=payload.base_station,
            tags=payload.tags,
            watchers=payload.watchers,
            custom_fields=payload.custom_fields,
            parent_ticket_id=payload.parent_ticket_id,
            merged_into_id=payload.merged_into_id,
        )
        ticket = service.update_ticket(ticket_id, data)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "ticket_number": ticket.ticket_number}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}", dependencies=[ticket_write_dep])
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Soft-delete a ticket locally."""
    try:
        service.delete_ticket(ticket_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET COMMENTS
# =============================================================================

@router.post("/tickets/{ticket_id}/comments", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_comment(
    ticket_id: int,
    payload: TicketCommentRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add a comment to a ticket."""
    try:
        data = CommentData(
            comment=payload.comment,
            comment_type=payload.comment_type,
            commented_by=payload.commented_by,
            commented_by_name=payload.commented_by_name,
            is_public=payload.is_public,
            comment_date=payload.comment_date,
        )
        comment = service.add_comment(ticket_id, data)
        db.commit()
        db.refresh(comment)
        return {"id": comment.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}/comments/{comment_id}", dependencies=[ticket_write_dep])
def update_ticket_comment(
    ticket_id: int,
    comment_id: int,
    payload: TicketCommentUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a ticket comment."""
    try:
        data = CommentData(
            comment=payload.comment or "",
            comment_type=payload.comment_type,
            commented_by=payload.commented_by,
            commented_by_name=payload.commented_by_name,
            is_public=payload.is_public if payload.is_public is not None else True,
            comment_date=payload.comment_date,
        )
        comment = service.update_comment(ticket_id, comment_id, data)
        db.commit()
        db.refresh(comment)
        return {"id": comment.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/comments/{comment_id}", dependencies=[ticket_write_dep])
def delete_ticket_comment(
    ticket_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Delete a ticket comment."""
    try:
        service.delete_comment(ticket_id, comment_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET ACTIVITIES
# =============================================================================

@router.post("/tickets/{ticket_id}/activities", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_activity(
    ticket_id: int,
    payload: TicketActivityRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add an activity to a ticket."""
    try:
        data = ActivityData(
            activity=payload.activity,
            activity_type=payload.activity_type,
            owner=payload.owner,
            from_status=payload.from_status,
            to_status=payload.to_status,
            activity_date=payload.activity_date,
        )
        activity = service.add_activity(ticket_id, data)
        db.commit()
        db.refresh(activity)
        return {"id": activity.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}/activities/{activity_id}", dependencies=[ticket_write_dep])
def update_ticket_activity(
    ticket_id: int,
    activity_id: int,
    payload: TicketActivityUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a ticket activity."""
    try:
        data = ActivityData(
            activity=payload.activity or "",
            activity_type=payload.activity_type,
            owner=payload.owner,
            from_status=payload.from_status,
            to_status=payload.to_status,
            activity_date=payload.activity_date,
        )
        activity = service.update_activity(ticket_id, activity_id, data)
        db.commit()
        db.refresh(activity)
        return {"id": activity.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/activities/{activity_id}", dependencies=[ticket_write_dep])
def delete_ticket_activity(
    ticket_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Delete a ticket activity."""
    try:
        service.delete_activity(ticket_id, activity_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET DEPENDENCIES
# =============================================================================

@router.post("/tickets/{ticket_id}/depends-on", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_dependency(
    ticket_id: int,
    payload: TicketDependencyRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add a blocking/depends-on relationship to a ticket."""
    try:
        data = DependencyData(
            depends_on_ticket_id=payload.depends_on_ticket_id,
            depends_on_erpnext_id=payload.depends_on_erpnext_id,
            depends_on_subject=payload.depends_on_subject,
            depends_on_status=payload.depends_on_status,
        )
        dependency = service.add_dependency(ticket_id, data)
        db.commit()
        db.refresh(dependency)
        return {"id": dependency.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}/depends-on/{dependency_id}", dependencies=[ticket_write_dep])
def update_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    payload: TicketDependencyUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a blocking/depends-on relationship."""
    try:
        data = DependencyData(
            depends_on_ticket_id=payload.depends_on_ticket_id,
            depends_on_erpnext_id=payload.depends_on_erpnext_id,
            depends_on_subject=payload.depends_on_subject,
            depends_on_status=payload.depends_on_status,
        )
        dependency = service.update_dependency(ticket_id, dependency_id, data)
        db.commit()
        db.refresh(dependency)
        return {"id": dependency.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/depends-on/{dependency_id}", dependencies=[ticket_write_dep])
def delete_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Remove a blocking/depends-on relationship."""
    try:
        service.delete_dependency(ticket_id, dependency_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET COMMUNICATIONS
# =============================================================================

@router.post("/tickets/{ticket_id}/communications", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_communication(
    ticket_id: int,
    payload: TicketCommunicationRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add a communication log entry to a ticket."""
    try:
        data = CommunicationData(
            communication_type=payload.communication_type,
            communication_medium=payload.communication_medium,
            subject=payload.subject,
            content=payload.content,
            sender=payload.sender,
            sender_full_name=payload.sender_full_name,
            recipients=payload.recipients,
            cc=payload.cc,
            bcc=payload.bcc,
            sent_or_received=payload.sent_or_received,
            read_receipt=payload.read_receipt,
            delivery_status=payload.delivery_status,
            communication_date=payload.communication_date,
        )
        comm = service.add_communication(ticket_id, data)
        db.commit()
        db.refresh(comm)
        return {"id": comm.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}/communications/{communication_id}", dependencies=[ticket_write_dep])
def update_ticket_communication(
    ticket_id: int,
    communication_id: int,
    payload: TicketCommunicationUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a communication log entry."""
    try:
        data = CommunicationData(
            communication_type=payload.communication_type,
            communication_medium=payload.communication_medium,
            subject=payload.subject,
            content=payload.content,
            sender=payload.sender,
            sender_full_name=payload.sender_full_name,
            recipients=payload.recipients,
            cc=payload.cc,
            bcc=payload.bcc,
            sent_or_received=payload.sent_or_received,
            read_receipt=payload.read_receipt if payload.read_receipt is not None else False,
            delivery_status=payload.delivery_status,
            communication_date=payload.communication_date,
        )
        comm = service.update_communication(ticket_id, communication_id, data)
        db.commit()
        db.refresh(comm)
        return {"id": comm.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/communications/{communication_id}", dependencies=[ticket_write_dep])
def delete_ticket_communication(
    ticket_id: int,
    communication_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Delete a communication log entry."""
    try:
        service.delete_communication(ticket_id, communication_id)
        db.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# ASSIGNMENT & SLA
# =============================================================================

@router.put("/tickets/{ticket_id}/assignee", dependencies=[ticket_write_dep])
def assign_ticket(
    ticket_id: int,
    payload: TicketAssigneeRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Assign a ticket to an agent or team."""
    try:
        data = AssignmentData(
            team_id=payload.team_id,
            member_id=payload.member_id,
            employee_id=payload.employee_id,
            assigned_to=payload.assigned_to,
            agent_id=payload.agent_id,
        )
        ticket = service.assign_ticket(ticket_id, data)
        db.commit()
        db.refresh(ticket)
        return {
            "id": ticket.id,
            "assigned_employee_id": ticket.assigned_employee_id,
            "assigned_to": ticket.assigned_to,
            "resolution_team": ticket.resolution_team,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/tickets/{ticket_id}/sla", dependencies=[ticket_write_dep])
def update_ticket_sla(
    ticket_id: int,
    payload: TicketSLARequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update SLA dates (response/resolution) with optional reason note."""
    try:
        data = SLAUpdateData(
            response_by=payload.response_by,
            resolution_by=payload.resolution_by,
            reason=payload.reason,
        )
        ticket = service.update_sla(ticket_id, data)
        db.commit()
        db.refresh(ticket)
        return {
            "id": ticket.id,
            "response_by": ticket.response_by.isoformat() if ticket.response_by else None,
            "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TAG DEFINITIONS
# =============================================================================

def _serialize_tag(tag: TicketTag) -> Dict[str, Any]:
    """Serialize a tag definition."""
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "usage_count": tag.usage_count,
        "is_active": tag.is_active,
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
        "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
    }


@router.get("/tags", dependencies=[ticket_read_dep])
def list_tags(
    active_only: bool = True,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """List all tag definitions."""
    tags, total = service.list_tags(
        is_active=True if active_only else None,
        search=search,
        skip=offset,
        limit=limit,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_tag(t) for t in tags],
    }


@router.get("/tags/{tag_id}", dependencies=[ticket_read_dep])
def get_tag(
    tag_id: int,
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Get a specific tag definition."""
    tag = service.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return _serialize_tag(tag)


@router.post("/tags", dependencies=[ticket_write_dep], status_code=201)
def create_tag(
    payload: TagCreateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Create a new tag definition."""
    try:
        tag = service.create_tag(TagCreate(
            name=payload.name,
            color=payload.color,
            description=payload.description,
            is_active=payload.is_active,
        ))
        db.commit()
        return {"id": tag.id, "name": tag.name}
    except DuplicateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/tags/{tag_id}", dependencies=[ticket_write_dep])
def update_tag(
    tag_id: int,
    payload: TagUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a tag definition."""
    try:
        tag = service.update_tag(
            tag_id,
            TagUpdate(
                name=payload.name,
                color=payload.color,
                description=payload.description,
                is_active=payload.is_active,
            ),
        )
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        db.commit()
        return _serialize_tag(tag)
    except DuplicateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tags/{tag_id}", dependencies=[ticket_write_dep])
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Delete a tag definition."""
    if not service.delete_tag(tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    db.commit()
    return Response(status_code=204)


# =============================================================================
# CUSTOM FIELD DEFINITIONS
# =============================================================================

def _serialize_custom_field(field: TicketCustomField) -> Dict[str, Any]:
    """Serialize a custom field definition."""
    return {
        "id": field.id,
        "name": field.name,
        "field_key": field.field_key,
        "description": field.description,
        "field_type": field.field_type,
        "options": field.options,
        "default_value": field.default_value,
        "is_required": field.is_required,
        "min_length": field.min_length,
        "max_length": field.max_length,
        "regex_pattern": field.regex_pattern,
        "display_order": field.display_order,
        "show_in_list": field.show_in_list,
        "show_in_create": field.show_in_create,
        "is_active": field.is_active,
        "created_at": field.created_at.isoformat() if field.created_at else None,
        "updated_at": field.updated_at.isoformat() if field.updated_at else None,
    }


@router.get("/custom-fields", dependencies=[ticket_read_dep])
def list_custom_fields(
    active_only: bool = True,
    show_in_create: Optional[bool] = None,
    show_in_list: Optional[bool] = None,
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """List all custom field definitions."""
    fields = service.list_custom_fields(
        is_active=True if active_only else None,
        show_in_create=show_in_create,
        show_in_list=show_in_list,
    )

    return {
        "total": len(fields),
        "data": [_serialize_custom_field(f) for f in fields],
    }


@router.get("/custom-fields/{field_id}", dependencies=[ticket_read_dep])
def get_custom_field(
    field_id: int,
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Get a specific custom field definition."""
    field = service.get_custom_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    return _serialize_custom_field(field)


@router.post("/custom-fields", dependencies=[ticket_write_dep], status_code=201)
def create_custom_field(
    payload: CustomFieldCreateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Create a new custom field definition."""
    try:
        options_data = None
        if payload.options:
            options_data = [{"value": o.value, "label": o.label} for o in payload.options]

        field = service.create_custom_field(CustomFieldCreate(
            name=payload.name,
            field_key=payload.field_key,
            description=payload.description,
            field_type=payload.field_type,
            options=options_data,
            default_value=payload.default_value,
            is_required=payload.is_required,
            min_length=payload.min_length,
            max_length=payload.max_length,
            regex_pattern=payload.regex_pattern,
            display_order=payload.display_order,
            show_in_list=payload.show_in_list,
            show_in_create=payload.show_in_create,
            is_active=payload.is_active,
        ))
        db.commit()
        return {"id": field.id, "field_key": field.field_key}
    except DuplicateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/custom-fields/{field_id}", dependencies=[ticket_write_dep])
def update_custom_field(
    field_id: int,
    payload: CustomFieldUpdateRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Update a custom field definition."""
    try:
        options_data = None
        if payload.options is not None:
            options_data = [{"value": o.value, "label": o.label} for o in payload.options]

        field = service.update_custom_field(
            field_id,
            CustomFieldUpdate(
                name=payload.name,
                description=payload.description,
                field_type=payload.field_type,
                options=options_data,
                default_value=payload.default_value,
                is_required=payload.is_required,
                min_length=payload.min_length,
                max_length=payload.max_length,
                regex_pattern=payload.regex_pattern,
                display_order=payload.display_order,
                show_in_list=payload.show_in_list,
                show_in_create=payload.show_in_create,
                is_active=payload.is_active,
            ),
        )
        if not field:
            raise HTTPException(status_code=404, detail="Custom field not found")
        db.commit()
        return _serialize_custom_field(field)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/custom-fields/{field_id}", dependencies=[ticket_write_dep])
def delete_custom_field(
    field_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Response:
    """Delete a custom field definition."""
    if not service.delete_custom_field(field_id):
        raise HTTPException(status_code=404, detail="Custom field not found")
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TICKET TAGS MANAGEMENT
# =============================================================================

@router.post("/tickets/{ticket_id}/tags", dependencies=[ticket_write_dep])
def add_ticket_tags(
    ticket_id: int,
    payload: TicketTagsRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add tags to a ticket."""
    try:
        ticket = service.add_tags(ticket_id, payload.tags)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "tags": ticket.tags}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/tags/{tag_name}", dependencies=[ticket_write_dep])
def remove_ticket_tag(
    ticket_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Remove a tag from a ticket."""
    try:
        ticket = service.remove_tag(ticket_id, tag_name)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "tags": ticket.tags}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET WATCHERS MANAGEMENT
# =============================================================================

@router.post("/tickets/{ticket_id}/watchers", dependencies=[ticket_write_dep])
def add_ticket_watchers(
    ticket_id: int,
    payload: TicketWatchersRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Add watchers to a ticket."""
    try:
        ticket = service.add_watchers(ticket_id, payload.user_ids)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "watchers": ticket.watchers}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/tickets/{ticket_id}/watchers/{user_id}", dependencies=[ticket_write_dep])
def remove_ticket_watcher(
    ticket_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Remove a watcher from a ticket."""
    try:
        ticket = service.remove_watcher(ticket_id, user_id)
        db.commit()
        db.refresh(ticket)
        return {"id": ticket.id, "watchers": ticket.watchers}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# =============================================================================
# TICKET MERGE / SPLIT
# =============================================================================

@router.post("/tickets/{ticket_id}/merge", dependencies=[ticket_write_dep])
def merge_tickets(
    ticket_id: int,
    payload: TicketMergeRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Merge source tickets into this target ticket."""
    try:
        data = MergeData(
            source_ticket_ids=payload.source_ticket_ids,
            close_source_tickets=payload.close_source_tickets,
        )
        target = service.merge_tickets(ticket_id, data)
        db.commit()
        db.refresh(target)
        return {
            "id": target.id,
            "merged_count": len(payload.source_ticket_ids),
            "merged_tickets": target.merged_tickets,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("/tickets/{ticket_id}/split", dependencies=[ticket_write_dep], status_code=201)
def split_ticket(
    ticket_id: int,
    payload: TicketSplitRequest,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """Create a sub-ticket (child) from this ticket."""
    try:
        data = SplitData(
            subject=payload.subject,
            description=payload.description,
            copy_tags=payload.copy_tags,
            copy_custom_fields=payload.copy_custom_fields,
        )
        child = service.split_ticket(ticket_id, data)
        db.commit()
        db.refresh(child)
        return {
            "id": child.id,
            "ticket_number": child.ticket_number,
            "parent_ticket_id": child.parent_ticket_id,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get("/tickets/{ticket_id}/sub-tickets", dependencies=[ticket_read_dep])
def list_sub_tickets(
    ticket_id: int,
    db: Session = Depends(get_db),
    service: TicketService = Depends(get_ticket_service),
) -> Dict[str, Any]:
    """List all sub-tickets of a parent ticket."""
    try:
        sub_tickets = service.list_sub_tickets(ticket_id)
        return {
            "parent_ticket_id": ticket_id,
            "total": len(sub_tickets),
            "data": [serialize_ticket_brief(t) for t in sub_tickets],
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
