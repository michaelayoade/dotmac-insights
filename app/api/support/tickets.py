"""Ticket management endpoints: CRUD, child tables, assignments."""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Dict, Any, Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, validator, Field, conlist
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.ticket import (
    Ticket, TicketStatus, TicketPriority,
    HDTicketComment, HDTicketActivity, TicketCommunication, HDTicketDependency
)
from app.models.customer import Customer
from app.models.agent import Agent, Team, TeamMember
from app.models.auth import User
from app.models.support_tags import TicketTag, TicketCustomField, CustomFieldType
from app.auth import Require, get_current_principal
from app.cache import cached, CACHE_TTL

from .helpers import (
    parse_ticket_status, parse_ticket_priority, generate_local_ticket_number,
    serialize_ticket_brief, serialize_comment, serialize_activity,
    serialize_communication, serialize_dependency
)

router = APIRouter()

# Shared RBAC dependencies: accept either tickets:* or support:* scopes
ticket_read_dep = Depends(Require("tickets:read", "support:read"))
ticket_write_dep = Depends(Require("tickets:write", "support:write"))


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
    customer_id: Optional[int] = None
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    resolution_by: Optional[datetime] = None
    response_by: Optional[datetime] = None
    resolution_team: Optional[str] = None
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

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            TicketStatus(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid status: {value}. Allowed: {[s.value for s in TicketStatus]}")

    @validator("priority")
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

    @validator("field_type")
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

    @validator("field_type")
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
    tags: conlist(str, min_length=1)


class TicketWatchersRequest(BaseModel):
    user_ids: conlist(int, min_length=1)


class TicketMergeRequest(BaseModel):
    source_ticket_ids: conlist(int, min_length=1) = Field(
        ..., description="IDs of tickets to merge into this ticket"
    )
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
) -> Dict[str, Any]:
    """Support dashboard with ticket and conversation metrics."""
    from app.models.conversation import Conversation, ConversationStatus

    # Ticket counts by status
    ticket_by_status = db.query(
        Ticket.status,
        func.count(Ticket.id).label("count")
    ).filter(Ticket.is_deleted == False).group_by(Ticket.status).all()

    status_counts: Dict[str, int] = {row.status.value: int(getattr(row, "count", 0) or 0) for row in ticket_by_status}
    total_tickets: int = sum(status_counts.values())
    open_tickets: int = status_counts.get("open", 0) + status_counts.get("replied", 0)

    # Open tickets by priority
    by_priority = db.query(
        Ticket.priority,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        Ticket.is_deleted == False,
    ).group_by(Ticket.priority).all()

    priority_counts: Dict[str, int] = {row.priority.value: int(getattr(row, "count", 0) or 0) for row in by_priority}

    # SLA metrics
    sla_met = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
        Ticket.resolution_date <= Ticket.resolution_by,
        Ticket.is_deleted == False,
    ).scalar() or 0

    from sqlalchemy import and_
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
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
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
    customer_id: Optional[int] = None,
    ticket_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    unassigned_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tickets with filtering and pagination."""
    query = db.query(Ticket).filter(Ticket.is_deleted == False)

    if status:
        status_enum = parse_ticket_status(status)
        query = query.filter(Ticket.status == status_enum)

    if priority:
        priority_enum = parse_ticket_priority(priority)
        query = query.filter(Ticket.priority == priority_enum)

    if customer_id:
        query = query.filter(Ticket.customer_id == customer_id)

    if ticket_type:
        query = query.filter(Ticket.ticket_type == ticket_type)

    if assigned_to:
        query = query.filter(Ticket.assigned_to.ilike(f"%{assigned_to}%"))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Ticket.subject.ilike(search_term),
                Ticket.ticket_number.ilike(search_term),
                Ticket.customer_name.ilike(search_term),
            )
        )

    if overdue_only:
        query = query.filter(
            Ticket.resolution_by.isnot(None),
            Ticket.resolution_by < func.current_timestamp(),
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
        )

    if unassigned_only:
        query = query.filter(
            Ticket.assigned_to.is_(None),
            Ticket.assigned_employee_id.is_(None),
        )

    if start_date:
        query = query.filter(Ticket.created_at >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Ticket.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    tickets = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_ticket_brief(t) for t in tickets],
    }


@router.get("/tickets/{ticket_id}", dependencies=[ticket_read_dep])
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed ticket information with all child tables."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    customer = None
    if ticket.customer_id:
        cust = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email, "phone": cust.phone}

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


@router.post("/tickets", dependencies=[ticket_write_dep], status_code=201)
def create_ticket(
    payload: TicketCreateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a ticket locally (no upstream ERP write-back)."""
    valid_tags = _validate_tags(db, payload.tags)
    valid_watchers = _validate_watchers(db, payload.watchers)
    valid_custom_fields = _validate_custom_fields(db, payload.custom_fields)

    ticket = Ticket(
        ticket_number=generate_local_ticket_number(),
        subject=payload.subject,
        description=payload.description,
        status=parse_ticket_status(payload.status) or TicketStatus.OPEN,
        priority=parse_ticket_priority(payload.priority) or TicketPriority.MEDIUM,
        ticket_type=payload.ticket_type,
        issue_type=payload.issue_type,
        customer_id=payload.customer_id,
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
        tags=valid_tags,
        watchers=valid_watchers,
        custom_fields=valid_custom_fields,
        parent_ticket_id=payload.parent_ticket_id,
        merged_into_id=payload.merged_into_id,
        origin_system="local",
        write_back_status="pending",
        created_by_id=getattr(principal, "id", None),
        updated_by_id=getattr(principal, "id", None),
        opening_date=datetime.utcnow(),
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "ticket_number": ticket.ticket_number}


@router.patch("/tickets/{ticket_id}", dependencies=[ticket_write_dep])
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an existing ticket locally."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    status = parse_ticket_status(payload.status)
    priority = parse_ticket_priority(payload.priority)

    # Validate structured fields before applying
    if payload.tags is not None:
        new_tags = _validate_tags(db, payload.tags)
        # Adjust usage counts
        current_tags = ticket.tags or []
        added = [t for t in new_tags if t not in current_tags]
        removed = [t for t in current_tags if t not in new_tags]
        if added:
            for tag in db.query(TicketTag).filter(TicketTag.name.in_(added), TicketTag.is_active == True).all():
                tag.usage_count = (tag.usage_count or 0) + 1
        if removed:
            for tag in db.query(TicketTag).filter(TicketTag.name.in_(removed)).all():
                if tag.usage_count and tag.usage_count > 0:
                    tag.usage_count = tag.usage_count - 1
        ticket.tags = new_tags
    if payload.watchers is not None:
        ticket.watchers = _validate_watchers(db, payload.watchers)
    if payload.custom_fields is not None:
        ticket.custom_fields = _validate_custom_fields(db, payload.custom_fields)

    for field in [
        "subject", "description", "ticket_type", "issue_type", "customer_id",
        "project_id", "assigned_to", "assigned_employee_id", "resolution_by",
        "response_by", "resolution_team", "customer_email", "customer_phone",
        "customer_name", "region", "base_station", "parent_ticket_id", "merged_into_id",
    ]:
        value = getattr(payload, field)
        if value is not None:
            setattr(ticket, field, value)

    if status:
        ticket.status = status
    if priority:
        ticket.priority = priority

    ticket.updated_by_id = getattr(principal, "id", None)
    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "ticket_number": ticket.ticket_number}


@router.delete("/tickets/{ticket_id}", dependencies=[ticket_write_dep])
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Response:
    """Soft-delete a ticket locally."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_deleted = True
    ticket.deleted_at = datetime.utcnow()
    ticket.deleted_by_id = getattr(principal, "id", None)
    ticket.updated_at = datetime.utcnow()
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TICKET COMMENTS
# =============================================================================

@router.post("/tickets/{ticket_id}/comments", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_comment(
    ticket_id: int,
    payload: TicketCommentRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a comment to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    idx = len(ticket.comments)
    comment = HDTicketComment(
        ticket_id=ticket.id,
        comment=payload.comment,
        comment_type=payload.comment_type,
        commented_by=payload.commented_by,
        commented_by_name=payload.commented_by_name,
        is_public=payload.is_public,
        comment_date=payload.comment_date or datetime.utcnow(),
        idx=idx,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}


@router.patch("/tickets/{ticket_id}/comments/{comment_id}", dependencies=[ticket_write_dep])
def update_ticket_comment(
    ticket_id: int,
    comment_id: int,
    payload: TicketCommentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a ticket comment."""
    comment = (
        db.query(HDTicketComment)
        .join(Ticket, Ticket.id == HDTicketComment.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketComment.id == comment_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    for field in ["comment", "comment_type", "commented_by", "commented_by_name", "is_public", "comment_date"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(comment, field, value)

    db.commit()
    db.refresh(comment)
    return {"id": comment.id}


@router.delete("/tickets/{ticket_id}/comments/{comment_id}", dependencies=[ticket_write_dep])
def delete_ticket_comment(
    ticket_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a ticket comment."""
    comment = (
        db.query(HDTicketComment)
        .join(Ticket, Ticket.id == HDTicketComment.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketComment.id == comment_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TICKET ACTIVITIES
# =============================================================================

@router.post("/tickets/{ticket_id}/activities", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_activity(
    ticket_id: int,
    payload: TicketActivityRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add an activity to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    idx = len(ticket.activities)
    activity = HDTicketActivity(
        ticket_id=ticket.id,
        activity_type=payload.activity_type,
        activity=payload.activity,
        owner=payload.owner,
        from_status=payload.from_status,
        to_status=payload.to_status,
        activity_date=payload.activity_date or datetime.utcnow(),
        idx=idx,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return {"id": activity.id}


@router.patch("/tickets/{ticket_id}/activities/{activity_id}", dependencies=[ticket_write_dep])
def update_ticket_activity(
    ticket_id: int,
    activity_id: int,
    payload: TicketActivityUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a ticket activity."""
    activity = (
        db.query(HDTicketActivity)
        .join(Ticket, Ticket.id == HDTicketActivity.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketActivity.id == activity_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    for field in ["activity_type", "activity", "owner", "from_status", "to_status", "activity_date"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(activity, field, value)

    db.commit()
    db.refresh(activity)
    return {"id": activity.id}


@router.delete("/tickets/{ticket_id}/activities/{activity_id}", dependencies=[ticket_write_dep])
def delete_ticket_activity(
    ticket_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a ticket activity."""
    activity = (
        db.query(HDTicketActivity)
        .join(Ticket, Ticket.id == HDTicketActivity.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketActivity.id == activity_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TICKET DEPENDENCIES
# =============================================================================

@router.post("/tickets/{ticket_id}/depends-on", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_dependency(
    ticket_id: int,
    payload: TicketDependencyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a blocking/depends-on relationship to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if payload.depends_on_ticket_id:
        target = db.query(Ticket.id).filter(Ticket.id == payload.depends_on_ticket_id, Ticket.is_deleted == False).first()
        if not target:
            raise HTTPException(status_code=400, detail="depends_on_ticket_id does not exist")

    dependency = HDTicketDependency(
        ticket_id=ticket.id,
        depends_on_ticket_id=payload.depends_on_ticket_id,
        depends_on_erpnext_id=payload.depends_on_erpnext_id,
        depends_on_subject=payload.depends_on_subject,
        depends_on_status=payload.depends_on_status,
        idx=len(ticket.depends_on),
    )
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return {"id": dependency.id}


@router.patch("/tickets/{ticket_id}/depends-on/{dependency_id}", dependencies=[ticket_write_dep])
def update_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    payload: TicketDependencyUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a blocking/depends-on relationship."""
    dependency = (
        db.query(HDTicketDependency)
        .join(Ticket, Ticket.id == HDTicketDependency.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketDependency.id == dependency_id)
        .first()
    )
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")

    if payload.depends_on_ticket_id:
        target = db.query(Ticket.id).filter(Ticket.id == payload.depends_on_ticket_id, Ticket.is_deleted == False).first()
        if not target:
            raise HTTPException(status_code=400, detail="depends_on_ticket_id does not exist")

    for field in ["depends_on_ticket_id", "depends_on_erpnext_id", "depends_on_subject", "depends_on_status"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(dependency, field, value)

    db.commit()
    db.refresh(dependency)
    return {"id": dependency.id}


@router.delete("/tickets/{ticket_id}/depends-on/{dependency_id}", dependencies=[ticket_write_dep])
def delete_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Remove a blocking/depends-on relationship."""
    dependency = (
        db.query(HDTicketDependency)
        .join(Ticket, Ticket.id == HDTicketDependency.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, HDTicketDependency.id == dependency_id)
        .first()
    )
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    db.delete(dependency)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TICKET COMMUNICATIONS
# =============================================================================

@router.post("/tickets/{ticket_id}/communications", dependencies=[ticket_write_dep], status_code=201)
def add_ticket_communication(
    ticket_id: int,
    payload: TicketCommunicationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a communication log entry to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    comm = TicketCommunication(
        ticket_id=ticket.id,
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
        communication_date=payload.communication_date or datetime.utcnow(),
    )
    db.add(comm)
    db.commit()
    db.refresh(comm)
    return {"id": comm.id}


@router.patch("/tickets/{ticket_id}/communications/{communication_id}", dependencies=[ticket_write_dep])
def update_ticket_communication(
    ticket_id: int,
    communication_id: int,
    payload: TicketCommunicationUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a communication log entry."""
    comm = (
        db.query(TicketCommunication)
        .join(Ticket, Ticket.id == TicketCommunication.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, TicketCommunication.id == communication_id)
        .first()
    )
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    for field in [
        "communication_type", "communication_medium", "subject", "content",
        "sender", "sender_full_name", "recipients", "cc", "bcc",
        "sent_or_received", "read_receipt", "delivery_status", "communication_date",
    ]:
        value = getattr(payload, field)
        if value is not None:
            setattr(comm, field, value)

    db.commit()
    db.refresh(comm)
    return {"id": comm.id}


@router.delete("/tickets/{ticket_id}/communications/{communication_id}", dependencies=[ticket_write_dep])
def delete_ticket_communication(
    ticket_id: int,
    communication_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a communication log entry."""
    comm = (
        db.query(TicketCommunication)
        .join(Ticket, Ticket.id == TicketCommunication.ticket_id)
        .filter(Ticket.id == ticket_id, Ticket.is_deleted == False, TicketCommunication.id == communication_id)
        .first()
    )
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.delete(comm)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# ASSIGNMENT & SLA
# =============================================================================

@router.put("/tickets/{ticket_id}/assignee", dependencies=[ticket_write_dep])
def assign_ticket(
    ticket_id: int,
    payload: TicketAssigneeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Assign a ticket to an agent or team."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    team = None
    if payload.team_id:
        team = db.query(Team).filter(Team.id == payload.team_id).first()
        if not team:
            raise HTTPException(status_code=400, detail="team_id does not exist")

    member = None
    if payload.member_id:
        member = db.query(TeamMember).filter(TeamMember.id == payload.member_id).first()
        if not member:
            raise HTTPException(status_code=400, detail="member_id does not exist")
        if payload.team_id and member.team_id != payload.team_id:
            raise HTTPException(status_code=400, detail="member does not belong to team_id")

    agent = None
    if payload.agent_id:
        agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
        if not agent:
            raise HTTPException(status_code=400, detail="agent_id does not exist")

    if member and member.agent_id:
        agent = db.query(Agent).filter(Agent.id == member.agent_id).first()

    if agent and agent.employee_id:
        ticket.assigned_employee_id = agent.employee_id
    elif payload.employee_id:
        ticket.assigned_employee_id = payload.employee_id

    if agent:
        ticket.assigned_to = payload.assigned_to or agent.display_name or agent.email
    elif payload.assigned_to:
        ticket.assigned_to = payload.assigned_to

    if team:
        ticket.resolution_team = team.name

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return {
        "id": ticket.id,
        "assigned_employee_id": ticket.assigned_employee_id,
        "assigned_to": ticket.assigned_to,
        "resolution_team": ticket.resolution_team,
    }


@router.patch("/tickets/{ticket_id}/sla", dependencies=[ticket_write_dep])
def update_ticket_sla(
    ticket_id: int,
    payload: TicketSLARequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update SLA dates (response/resolution) with optional reason note."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if payload.response_by is not None:
        ticket.response_by = payload.response_by
    if payload.resolution_by is not None:
        ticket.resolution_by = payload.resolution_by

    if payload.reason:
        existing = ticket.resolution_details or ""
        note = f"[SLA override] {payload.reason}"
        ticket.resolution_details = (existing + "\n" + note).strip() if existing else note

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return {
        "id": ticket.id,
        "response_by": ticket.response_by.isoformat() if ticket.response_by else None,
        "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
    }


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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all tag definitions."""
    query = db.query(TicketTag)

    if active_only:
        query = query.filter(TicketTag.is_active == True)

    if search:
        query = query.filter(TicketTag.name.ilike(f"%{search}%"))

    total = query.count()
    tags = query.order_by(TicketTag.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_tag(t) for t in tags],
    }


@router.get("/tags/{tag_id}", dependencies=[ticket_read_dep])
def get_tag(
    tag_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific tag definition."""
    tag = db.query(TicketTag).filter(TicketTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return _serialize_tag(tag)


@router.post("/tags", dependencies=[ticket_write_dep], status_code=201)
def create_tag(
    payload: TagCreateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new tag definition."""
    existing = db.query(TicketTag).filter(TicketTag.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag with this name already exists")

    tag = TicketTag(
        name=payload.name,
        color=payload.color,
        description=payload.description,
        is_active=payload.is_active,
        created_by_id=getattr(principal, "id", None),
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"id": tag.id, "name": tag.name}


@router.patch("/tags/{tag_id}", dependencies=[ticket_write_dep])
def update_tag(
    tag_id: int,
    payload: TagUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a tag definition."""
    tag = db.query(TicketTag).filter(TicketTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if payload.name and payload.name != tag.name:
        existing = db.query(TicketTag).filter(TicketTag.name == payload.name, TicketTag.id != tag_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tag with this name already exists")

    for field in ["name", "color", "description", "is_active"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(tag, field, value)

    tag.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tag)
    return _serialize_tag(tag)


@router.delete("/tags/{tag_id}", dependencies=[ticket_write_dep])
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a tag definition."""
    tag = db.query(TicketTag).filter(TicketTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
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
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all custom field definitions."""
    query = db.query(TicketCustomField)

    if active_only:
        query = query.filter(TicketCustomField.is_active == True)

    if show_in_create is not None:
        query = query.filter(TicketCustomField.show_in_create == show_in_create)

    if show_in_list is not None:
        query = query.filter(TicketCustomField.show_in_list == show_in_list)

    fields = query.order_by(TicketCustomField.display_order, TicketCustomField.name).all()

    return {
        "total": len(fields),
        "data": [_serialize_custom_field(f) for f in fields],
    }


@router.get("/custom-fields/{field_id}", dependencies=[ticket_read_dep])
def get_custom_field(
    field_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific custom field definition."""
    field = db.query(TicketCustomField).filter(TicketCustomField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    return _serialize_custom_field(field)


@router.post("/custom-fields", dependencies=[ticket_write_dep], status_code=201)
def create_custom_field(
    payload: CustomFieldCreateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new custom field definition."""
    existing = db.query(TicketCustomField).filter(TicketCustomField.field_key == payload.field_key).first()
    if existing:
        raise HTTPException(status_code=400, detail="Custom field with this field_key already exists")

    options_data = None
    if payload.options:
        options_data = [{"value": o.value, "label": o.label} for o in payload.options]

    field = TicketCustomField(
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
        created_by_id=getattr(principal, "id", None),
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return {"id": field.id, "field_key": field.field_key}


@router.patch("/custom-fields/{field_id}", dependencies=[ticket_write_dep])
def update_custom_field(
    field_id: int,
    payload: CustomFieldUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a custom field definition."""
    field = db.query(TicketCustomField).filter(TicketCustomField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")

    for attr in [
        "name", "description", "field_type", "default_value", "is_required",
        "min_length", "max_length", "regex_pattern", "display_order",
        "show_in_list", "show_in_create", "is_active",
    ]:
        value = getattr(payload, attr)
        if value is not None:
            setattr(field, attr, value)

    if payload.options is not None:
        field.options = cast(Any, [{"value": o.value, "label": o.label} for o in payload.options])

    field.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(field)
    return _serialize_custom_field(field)


@router.delete("/custom-fields/{field_id}", dependencies=[ticket_write_dep])
def delete_custom_field(
    field_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a custom field definition."""
    field = db.query(TicketCustomField).filter(TicketCustomField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    db.delete(field)
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
) -> Dict[str, Any]:
    """Add tags to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    validated_tags = _validate_tags(db, payload.tags)

    current_tags = ticket.tags or []
    new_tags = list(dict.fromkeys(current_tags + validated_tags))

    # Validate tags exist and update usage counts
    for tag_name in validated_tags:
        if tag_name not in current_tags:
            tag = db.query(TicketTag).filter(TicketTag.name == tag_name, TicketTag.is_active == True).first()
            if tag:
                tag.usage_count = (tag.usage_count or 0) + 1

    ticket.tags = new_tags
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "tags": ticket.tags}


@router.delete("/tickets/{ticket_id}/tags/{tag_name}", dependencies=[ticket_write_dep])
def remove_ticket_tag(
    ticket_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a tag from a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    current_tags = ticket.tags or []
    if tag_name not in current_tags:
        raise HTTPException(status_code=404, detail="Tag not found on this ticket")

    # Update usage count
    tag = db.query(TicketTag).filter(TicketTag.name == tag_name).first()
    if tag and tag.usage_count and tag.usage_count > 0:
        tag.usage_count = tag.usage_count - 1

    ticket.tags = [t for t in current_tags if t != tag_name]
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "tags": ticket.tags}


# =============================================================================
# TICKET WATCHERS MANAGEMENT
# =============================================================================

@router.post("/tickets/{ticket_id}/watchers", dependencies=[ticket_write_dep])
def add_ticket_watchers(
    ticket_id: int,
    payload: TicketWatchersRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add watchers to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    validated_watchers = _validate_watchers(db, payload.user_ids)

    current_watchers = ticket.watchers or []
    new_watchers = list(dict.fromkeys(current_watchers + validated_watchers))

    ticket.watchers = new_watchers
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "watchers": ticket.watchers}


@router.delete("/tickets/{ticket_id}/watchers/{user_id}", dependencies=[ticket_write_dep])
def remove_ticket_watcher(
    ticket_id: int,
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a watcher from a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    current_watchers = ticket.watchers or []
    if user_id not in current_watchers:
        raise HTTPException(status_code=404, detail="Watcher not found on this ticket")

    ticket.watchers = [w for w in current_watchers if w != user_id]
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "watchers": ticket.watchers}


# =============================================================================
# TICKET MERGE / SPLIT
# =============================================================================

@router.post("/tickets/{ticket_id}/merge", dependencies=[ticket_write_dep])
def merge_tickets(
    ticket_id: int,
    payload: TicketMergeRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Merge source tickets into this target ticket."""
    target = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target ticket not found")

    if target.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot merge into a closed ticket")

    merged_ids = target.merged_tickets or []
    merged_count = 0

    for source_id in payload.source_ticket_ids:
        if source_id == ticket_id:
            continue

        source = db.query(Ticket).filter(Ticket.id == source_id, Ticket.is_deleted == False).first()
        if not source:
            continue

        # Copy comments from source to target
        for comment in source.comments:
            new_comment = HDTicketComment(
                ticket_id=target.id,
                comment=f"[Merged from #{source.ticket_number}] {comment.comment}",
                comment_type=comment.comment_type,
                commented_by=comment.commented_by,
                commented_by_name=comment.commented_by_name,
                is_public=comment.is_public,
                comment_date=comment.comment_date,
                idx=len(target.comments),
            )
            db.add(new_comment)

        # Merge tags
        if source.tags:
            target_tags = target.tags or []
            target.tags = list(set(target_tags + source.tags))
            # Update usage counts for newly added tags
            added = [t for t in source.tags if t not in target_tags]
            if added:
                for tag in db.query(TicketTag).filter(TicketTag.name.in_(added), TicketTag.is_active == True).all():
                    tag.usage_count = (tag.usage_count or 0) + 1

        # Link source to target
        source.merged_into_id = target.id

        if payload.close_source_tickets:
            source.status = TicketStatus.CLOSED
            source.resolution = f"Merged into ticket #{target.ticket_number}"
            source.resolution_date = datetime.utcnow()

        merged_ids.append(source_id)
        merged_count += 1

        # Add activity
        activity = HDTicketActivity(
            ticket_id=target.id,
            activity_type="merge",
            activity=f"Merged ticket #{source.ticket_number} into this ticket",
            owner=getattr(principal, "email", None),
            activity_date=datetime.utcnow(),
            idx=len(target.activities),
        )
        db.add(activity)

    target.merged_tickets = merged_ids
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    return {
        "id": target.id,
        "merged_count": merged_count,
        "merged_tickets": target.merged_tickets,
    }


@router.post("/tickets/{ticket_id}/split", dependencies=[ticket_write_dep], status_code=201)
def split_ticket(
    ticket_id: int,
    payload: TicketSplitRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a sub-ticket (child) from this ticket."""
    parent = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent ticket not found")

    child = Ticket(
        ticket_number=generate_local_ticket_number(),
        subject=payload.subject,
        description=payload.description or f"Sub-ticket of #{parent.ticket_number}",
        status=TicketStatus.OPEN,
        priority=parent.priority,
        ticket_type=parent.ticket_type,
        issue_type=parent.issue_type,
        customer_id=parent.customer_id,
        project_id=parent.project_id,
        resolution_team=parent.resolution_team,
        customer_email=parent.customer_email,
        customer_phone=parent.customer_phone,
        customer_name=parent.customer_name,
        region=parent.region,
        base_station=parent.base_station,
        parent_ticket_id=parent.id,
        origin_system="local",
        write_back_status="pending",
        created_by_id=getattr(principal, "id", None),
        updated_by_id=getattr(principal, "id", None),
        opening_date=datetime.utcnow(),
    )

    if payload.copy_tags and parent.tags:
        child.tags = parent.tags.copy()

    if payload.copy_custom_fields and parent.custom_fields:
        child.custom_fields = parent.custom_fields.copy()

    db.add(child)

    # Add activity to parent
    activity = HDTicketActivity(
        ticket_id=parent.id,
        activity_type="split",
        activity=f"Created sub-ticket: {payload.subject}",
        owner=getattr(principal, "email", None),
        activity_date=datetime.utcnow(),
        idx=len(parent.activities),
    )
    db.add(activity)

    parent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(child)

    return {
        "id": child.id,
        "ticket_number": child.ticket_number,
        "parent_ticket_id": child.parent_ticket_id,
    }


@router.get("/tickets/{ticket_id}/sub-tickets", dependencies=[ticket_read_dep])
def list_sub_tickets(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all sub-tickets of a parent ticket."""
    parent = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent ticket not found")

    sub_tickets = db.query(Ticket).filter(
        Ticket.parent_ticket_id == ticket_id,
        Ticket.is_deleted == False,
    ).order_by(Ticket.created_at.desc()).all()

    return {
        "parent_ticket_id": ticket_id,
        "total": len(sub_tickets),
        "data": [serialize_ticket_brief(t) for t in sub_tickets],
    }
