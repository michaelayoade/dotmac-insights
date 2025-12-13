"""
Support Domain Router

Provides all support-related endpoints:
- /dashboard - Open tickets, SLA metrics, response times
- /tickets - List, detail tickets
- /conversations - List, detail Chatwoot conversations
- /analytics/* - Volume trends, resolution times, SLA performance
- /insights/* - Patterns, agent performance
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, validator

from app.database import get_db
from app.models.ticket import Ticket, TicketStatus, TicketPriority, HDTicketComment, HDTicketActivity, TicketCommunication
from app.models.ticket import HDTicketDependency
from app.models.conversation import Conversation, ConversationStatus
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.agent import Agent, Team, TeamMember
from app.auth import Require, get_current_principal
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("support-dashboard", ttl=CACHE_TTL["short"])
async def get_support_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Support dashboard with ticket and conversation metrics.
    """
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
# DATA ENDPOINTS
# =============================================================================

@router.get("/tickets", dependencies=[Depends(Require("explorer:read"))])
async def list_tickets(
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
        try:
            status_enum = TicketStatus(status)
            query = query.filter(Ticket.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if priority:
        try:
            priority_enum = TicketPriority(priority)
            query = query.filter(Ticket.priority == priority_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

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
        "data": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "subject": t.subject,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
                "ticket_type": t.ticket_type,
                "customer_id": t.customer_id,
                "customer_name": t.customer_name,
                "assigned_to": t.assigned_to,
                "resolution_by": t.resolution_by.isoformat() if t.resolution_by else None,
                "is_overdue": t.is_overdue,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "source": t.source.value if t.source else None,
                "write_back_status": getattr(t, "write_back_status", None),
            }
            for t in tickets
        ],
    }


@router.get("/tickets/{ticket_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_ticket(
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

    # Build comments list
    comments = [
        {
            "id": c.id,
            "comment": c.comment,
            "comment_type": c.comment_type,
            "commented_by": c.commented_by,
            "commented_by_name": c.commented_by_name,
            "is_public": c.is_public,
            "comment_date": c.comment_date.isoformat() if c.comment_date else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in sorted(ticket.comments, key=lambda x: x.idx)
    ]

    # Build activities list
    activities = [
        {
            "id": a.id,
            "activity_type": a.activity_type,
            "activity": a.activity,
            "owner": a.owner,
            "from_status": a.from_status,
            "to_status": a.to_status,
            "activity_date": a.activity_date.isoformat() if a.activity_date else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in sorted(ticket.activities, key=lambda x: x.idx)
    ]

    # Build communications list
    communications = [
        {
            "id": comm.id,
            "erpnext_id": comm.erpnext_id,
            "communication_type": comm.communication_type,
            "communication_medium": comm.communication_medium,
            "subject": comm.subject,
            "content": comm.content,
            "sender": comm.sender,
            "sender_full_name": comm.sender_full_name,
            "recipients": comm.recipients,
            "sent_or_received": comm.sent_or_received,
            "communication_date": comm.communication_date.isoformat() if comm.communication_date else None,
        }
        for comm in ticket.communications
    ]

    # Build depends_on list
    depends_on = [
        {
            "id": d.id,
            "depends_on_ticket_id": d.depends_on_ticket_id,
            "depends_on_erpnext_id": d.depends_on_erpnext_id,
            "depends_on_subject": d.depends_on_subject,
            "depends_on_status": d.depends_on_status,
        }
        for d in sorted(ticket.depends_on, key=lambda x: x.idx)
    ]

    # Build expenses list
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


# =============================================================================
# CRUD (local DB only)
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


def _parse_ticket_status(value: Optional[str]) -> Optional[TicketStatus]:
    if value is None:
        return None
    try:
        return TicketStatus(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {value}")


def _parse_ticket_priority(value: Optional[str]) -> Optional[TicketPriority]:
    if value is None:
        return None
    try:
        return TicketPriority(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {value}")


def _generate_local_ticket_number() -> str:
    """Generate a deterministic ticket number for locally created tickets."""
    return f"HD-LOCAL-{int(datetime.utcnow().timestamp() * 1000)}"


@router.post(
    "/tickets",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_ticket(
    payload: TicketCreateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a ticket locally (no upstream ERP write-back)."""
    ticket = Ticket(
        ticket_number=_generate_local_ticket_number(),
        subject=payload.subject,
        description=payload.description,
        status=_parse_ticket_status(payload.status) or TicketStatus.OPEN,
        priority=_parse_ticket_priority(payload.priority) or TicketPriority.MEDIUM,
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


@router.patch(
    "/tickets/{ticket_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an existing ticket locally."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    status = _parse_ticket_status(payload.status)
    priority = _parse_ticket_priority(payload.priority)

    # Apply updates
    for field in [
        "subject",
        "description",
        "ticket_type",
        "issue_type",
        "customer_id",
        "project_id",
        "assigned_to",
        "assigned_employee_id",
        "resolution_by",
        "response_by",
        "resolution_team",
        "customer_email",
        "customer_phone",
        "customer_name",
        "region",
        "base_station",
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


@router.delete(
    "/tickets/{ticket_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> None:
    """Soft-delete a ticket locally."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_deleted = True
    ticket.deleted_at = datetime.utcnow()
    ticket.deleted_by_id = getattr(principal, "id", None)
    ticket.updated_at = datetime.utcnow()
    db.commit()


# =============================================================================
# AGENTS & TEAMS
# =============================================================================


class TeamCreateRequest(BaseModel):
    team_name: str
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None
    is_active: bool = True


class TeamUpdateRequest(BaseModel):
    team_name: Optional[str] = None
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberCreateRequest(BaseModel):
    agent_id: int
    role: Optional[str] = None


class AgentCreateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[dict] = None
    skills: Optional[dict] = None
    channel_caps: Optional[dict] = None
    routing_weight: int = 1
    capacity: Optional[int] = None
    is_active: bool = True


class AgentUpdateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[dict] = None
    skills: Optional[dict] = None
    channel_caps: Optional[dict] = None
    routing_weight: Optional[int] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


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
    assigned_to: Optional[str] = None  # free-text fallback
    agent_id: Optional[int] = None


class TicketSLARequest(BaseModel):
    response_by: Optional[datetime] = None
    resolution_by: Optional[datetime] = None
    reason: Optional[str] = None


@router.get("/agents", dependencies=[Depends(Require("support:read"))])
async def list_agents(
    team_id: Optional[int] = None,
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List agents with optional filtering by team or domain."""
    query = db.query(Agent)
    if domain:
        query = query.filter(Agent.domains.contains({domain: True}))
    agents = query.all()

    team_membership = {}
    if team_id:
        member_rows = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
        team_membership = {m.agent_id: m for m in member_rows}

    return {
        "total": len(agents),
        "data": [
            {
                "id": a.id,
                "employee_id": a.employee_id,
                "email": a.email,
                "display_name": a.display_name,
                "domains": a.domains,
                "skills": a.skills,
                "channel_caps": a.channel_caps,
                "routing_weight": a.routing_weight,
                "capacity": a.capacity,
                "is_active": a.is_active,
                "team_member": {
                    "team_id": team_membership[a.id].team_id,
                    "role": team_membership[a.id].role,
                } if a.id in team_membership else None,
            }
            for a in agents
        ],
    }


@router.post(
    "/agents",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_agent(
    payload: AgentCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a unified agent (linked to employee if provided)."""
    display_name = payload.display_name
    email = payload.email
    if payload.employee_id:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if emp:
            display_name = display_name or emp.name
            email = email or emp.email
    agent = Agent(
        employee_id=payload.employee_id,
        email=email,
        display_name=display_name,
        domains=payload.domains,
        skills=payload.skills,
        channel_caps=payload.channel_caps,
        routing_weight=payload.routing_weight,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"id": agent.id}


@router.patch(
    "/agents/{agent_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update agent metadata."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.employee_id is not None:
        agent.employee_id = payload.employee_id
    if payload.email is not None:
        agent.email = payload.email
    if payload.display_name is not None:
        agent.display_name = payload.display_name
    if payload.domains is not None:
        agent.domains = payload.domains
    if payload.skills is not None:
        agent.skills = payload.skills
    if payload.channel_caps is not None:
        agent.channel_caps = payload.channel_caps
    if payload.routing_weight is not None:
        agent.routing_weight = payload.routing_weight
    if payload.capacity is not None:
        agent.capacity = payload.capacity
    if payload.is_active is not None:
        agent.is_active = payload.is_active

    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    return {"id": agent.id}


@router.delete(
    "/agents/{agent_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete an agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()


@router.get("/teams", dependencies=[Depends(Require("support:read"))])
async def list_teams(
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List teams with members."""
    query = db.query(Team)
    if domain:
        query = query.filter(Team.domain == domain)
    teams = query.all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "domain": t.domain,
            "assignment_rule": t.assignment_rule,
            "is_active": t.is_active,
            "members": [
                {
                    "id": m.id,
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "is_active": m.is_active,
                }
                for m in t.members
            ],
        }
        for t in teams
    ]


@router.post(
    "/teams",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a team."""
    team = Team(
        name=payload.team_name,
        description=payload.description,
        assignment_rule=payload.assignment_rule,
        domain=payload.domain,
        is_active=payload.is_active,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"id": team.id, "team_name": team.name}


@router.patch(
    "/teams/{team_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if payload.team_name is not None:
        team.name = payload.team_name
    if payload.description is not None:
        team.description = payload.description
    if payload.assignment_rule is not None:
        team.assignment_rule = payload.assignment_rule
    if payload.domain is not None:
        team.domain = payload.domain
    if payload.is_active is not None:
        team.is_active = payload.is_active

    db.commit()
    db.refresh(team)
    return {"id": team.id, "team_name": team.name}


@router.delete(
    "/teams/{team_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a team and its members."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete(team)
    db.commit()


@router.post(
    "/teams/{team_id}/members",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def add_team_member(
    team_id: int,
    payload: TeamMemberCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add an agent to a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=400, detail="agent_id does not exist")

    member = TeamMember(
        team_id=team_id,
        agent_id=payload.agent_id,
        role=payload.role,
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "team_id": member.team_id}


@router.delete(
    "/teams/{team_id}/members/{member_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def remove_team_member(
    team_id: int,
    member_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Remove an agent from a team."""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id, TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    db.delete(member)
    db.commit()


# =============================================================================
# Ticket comments
# =============================================================================


@router.post(
    "/tickets/{ticket_id}/comments",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def add_ticket_comment(
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


@router.patch(
    "/tickets/{ticket_id}/comments/{comment_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket_comment(
    ticket_id: int,
    comment_id: int,
    payload: TicketCommentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a ticket comment."""
    comment = (
        db.query(HDTicketComment)
        .join(Ticket, Ticket.id == HDTicketComment.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketComment.id == comment_id,
        )
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


@router.delete(
    "/tickets/{ticket_id}/comments/{comment_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_ticket_comment(
    ticket_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a ticket comment."""
    comment = (
        db.query(HDTicketComment)
        .join(Ticket, Ticket.id == HDTicketComment.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketComment.id == comment_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()


# =============================================================================
# Ticket activities
# =============================================================================


@router.post(
    "/tickets/{ticket_id}/activities",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def add_ticket_activity(
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


@router.patch(
    "/tickets/{ticket_id}/activities/{activity_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket_activity(
    ticket_id: int,
    activity_id: int,
    payload: TicketActivityUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a ticket activity."""
    activity = (
        db.query(HDTicketActivity)
        .join(Ticket, Ticket.id == HDTicketActivity.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketActivity.id == activity_id,
        )
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


@router.delete(
    "/tickets/{ticket_id}/activities/{activity_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_ticket_activity(
    ticket_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a ticket activity."""
    activity = (
        db.query(HDTicketActivity)
        .join(Ticket, Ticket.id == HDTicketActivity.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketActivity.id == activity_id,
        )
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()


# =============================================================================
# Ticket dependencies (blocking relationships)
# =============================================================================


@router.post(
    "/tickets/{ticket_id}/depends-on",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def add_ticket_dependency(
    ticket_id: int,
    payload: TicketDependencyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a blocking/depends-on relationship to a ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Ensure target exists if referencing by ticket_id
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


@router.patch(
    "/tickets/{ticket_id}/depends-on/{dependency_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    payload: TicketDependencyUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a blocking/depends-on relationship."""
    dependency = (
        db.query(HDTicketDependency)
        .join(Ticket, Ticket.id == HDTicketDependency.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketDependency.id == dependency_id,
        )
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


@router.delete(
    "/tickets/{ticket_id}/depends-on/{dependency_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_ticket_dependency(
    ticket_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Remove a blocking/depends-on relationship."""
    dependency = (
        db.query(HDTicketDependency)
        .join(Ticket, Ticket.id == HDTicketDependency.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            HDTicketDependency.id == dependency_id,
        )
        .first()
    )
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    db.delete(dependency)
    db.commit()


# =============================================================================
# Ticket communications (local log)
# =============================================================================


@router.post(
    "/tickets/{ticket_id}/communications",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def add_ticket_communication(
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


@router.patch(
    "/tickets/{ticket_id}/communications/{communication_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket_communication(
    ticket_id: int,
    communication_id: int,
    payload: TicketCommunicationUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a communication log entry."""
    comm = (
        db.query(TicketCommunication)
        .join(Ticket, Ticket.id == TicketCommunication.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            TicketCommunication.id == communication_id,
        )
        .first()
    )
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    for field in [
        "communication_type",
        "communication_medium",
        "subject",
        "content",
        "sender",
        "sender_full_name",
        "recipients",
        "cc",
        "bcc",
        "sent_or_received",
        "read_receipt",
        "delivery_status",
        "communication_date",
    ]:
        value = getattr(payload, field)
        if value is not None:
            setattr(comm, field, value)

    db.commit()
    db.refresh(comm)
    return {"id": comm.id}


@router.delete(
    "/tickets/{ticket_id}/communications/{communication_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_ticket_communication(
    ticket_id: int,
    communication_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a communication log entry."""
    comm = (
        db.query(TicketCommunication)
        .join(Ticket, Ticket.id == TicketCommunication.ticket_id)
        .filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
            TicketCommunication.id == communication_id,
        )
        .first()
    )
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.delete(comm)
    db.commit()


# =============================================================================
# Assignment helper
# =============================================================================


@router.put(
    "/tickets/{ticket_id}/assignee",
    dependencies=[Depends(Require("support:write"))],
)
async def assign_ticket(
    ticket_id: int,
    payload: TicketAssigneeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Assign a ticket to an agent or team.

    Resolution logic:
    - If member_id provided, use its employee_id (if any) and user/user_name for assigned_to.
    - Else if employee_id provided, set assigned_employee_id; assigned_to falls back to current value or stays untouched unless provided.
    - team_id populates resolution_team (does not force member).
    - assigned_to can override the display assignee string.
    """
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


# =============================================================================
# SLA overrides
# =============================================================================


@router.patch(
    "/tickets/{ticket_id}/sla",
    dependencies=[Depends(Require("support:write"))],
)
async def update_ticket_sla(
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


@router.get("/conversations", dependencies=[Depends(Require("explorer:read"))])
async def list_conversations(
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
async def get_conversation(
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


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/volume-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_volume_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly ticket volume trend."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    volume = db.query(
        extract("year", Ticket.created_at).label("year"),
        extract("month", Ticket.created_at).label("month"),
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
        func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.created_at <= end_dt,
    ).group_by(
        extract("year", Ticket.created_at),
        extract("month", Ticket.created_at),
    ).order_by(
        extract("year", Ticket.created_at),
        extract("month", Ticket.created_at),
    ).all()

    return [
        {
            "year": int(v.year),
            "month": int(v.month),
            "period": f"{int(v.year)}-{int(v.month):02d}",
            "total": v.total,
            "resolved": v.resolved,
            "closed": v.closed,
            "resolution_rate": round((v.resolved + v.closed) / v.total * 100, 1) if v.total > 0 else 0,
        }
        for v in volume
    ]


@router.get("/analytics/resolution-time", dependencies=[Depends(Require("analytics:read"))])
async def get_resolution_time_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get average resolution time trend by month."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    resolution_hours = func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600

    trend = db.query(
        extract("year", Ticket.resolution_date).label("year"),
        extract("month", Ticket.resolution_date).label("month"),
        func.avg(resolution_hours).label("avg_hours"),
        func.count(Ticket.id).label("ticket_count"),
    ).filter(
        Ticket.resolution_date.isnot(None),
        Ticket.opening_date.isnot(None),
        Ticket.resolution_date >= start_dt,
    ).group_by(
        extract("year", Ticket.resolution_date),
        extract("month", Ticket.resolution_date),
    ).order_by(
        extract("year", Ticket.resolution_date),
        extract("month", Ticket.resolution_date),
    ).all()

    return [
        {
            "year": int(t.year),
            "month": int(t.month),
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "avg_resolution_hours": round(float(t.avg_hours or 0), 1),
            "ticket_count": t.ticket_count,
        }
        for t in trend
    ]


@router.get("/analytics/by-category", dependencies=[Depends(Require("analytics:read"))])
async def get_tickets_by_category(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ticket distribution by type and category."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    # By ticket type
    by_type = db.query(
        Ticket.ticket_type,
        func.count(Ticket.id).label("count"),
        func.sum(case((Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]), 1), else_=0)).label("resolved"),
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.ticket_type.isnot(None),
    ).group_by(Ticket.ticket_type).order_by(func.count(Ticket.id).desc()).limit(20).all()

    # By issue type
    by_issue = db.query(
        Ticket.issue_type,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.issue_type.isnot(None),
    ).group_by(Ticket.issue_type).order_by(func.count(Ticket.id).desc()).limit(20).all()

    return {
        "by_ticket_type": [
            {
                "type": row.ticket_type,
                "count": row.count,
                "resolved": row.resolved,
                "resolution_rate": round(int(getattr(row, "resolved", 0) or 0) / int(getattr(row, "count", 1) or 1) * 100, 1) if getattr(row, "count", 0) else 0,
            }
            for row in by_type
        ],
        "by_issue_type": [
            {"type": row.issue_type, "count": row.count}
            for row in by_issue
        ],
    }


@router.get("/analytics/sla-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("support-sla", ttl=CACHE_TTL["medium"])
async def get_sla_performance(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get SLA attainment trend by month."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    sla_data = db.query(
        extract("year", Ticket.resolution_date).label("year"),
        extract("month", Ticket.resolution_date).label("month"),
        func.sum(case(
            (Ticket.resolution_date <= Ticket.resolution_by, 1),
            else_=0
        )).label("met"),
        func.sum(case(
            (Ticket.resolution_date > Ticket.resolution_by, 1),
            else_=0
        )).label("breached"),
        func.count(Ticket.id).label("total"),
    ).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
        Ticket.resolution_date >= start_dt,
    ).group_by(
        extract("year", Ticket.resolution_date),
        extract("month", Ticket.resolution_date),
    ).order_by(
        extract("year", Ticket.resolution_date),
        extract("month", Ticket.resolution_date),
    ).all()

    return [
        {
            "year": int(s.year),
            "month": int(s.month),
            "period": f"{int(s.year)}-{int(s.month):02d}",
            "met": s.met,
            "breached": s.breached,
            "total": s.total,
            "attainment_rate": round(s.met / s.total * 100, 1) if s.total > 0 else 0,
        }
        for s in sla_data
    ]


# =============================================================================
# INSIGHTS
# =============================================================================

@router.get("/insights/patterns", dependencies=[Depends(Require("analytics:read"))])
@cached("support-patterns", ttl=CACHE_TTL["medium"])
async def get_support_patterns(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze support patterns including peak times and common issues."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    # Peak hours
    by_hour = db.query(
        extract("hour", Ticket.created_at).label("hour"),
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= start_dt,
    ).group_by(extract("hour", Ticket.created_at)).order_by(func.count(Ticket.id).desc()).all()

    # Peak days
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    by_day = db.query(
        extract("dow", Ticket.created_at).label("day"),
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= start_dt,
    ).group_by(extract("dow", Ticket.created_at)).order_by(func.count(Ticket.id).desc()).all()

    # By region
    by_region = db.query(
        Ticket.region,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.region.isnot(None),
    ).group_by(Ticket.region).order_by(func.count(Ticket.id).desc()).limit(10).all()

    return {
        "peak_hours": [
            {"hour": int(h.hour), "count": h.count}
            for h in by_hour[:5]
        ],
        "peak_days": [
            {"day": day_names[int(d.day)], "day_num": int(d.day), "count": d.count}
            for d in by_day
        ],
        "by_region": [
            {"region": r.region, "count": r.count}
            for r in by_region
        ],
    }


@router.get("/insights/agent-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("support-agent-perf", ttl=CACHE_TTL["medium"])
async def get_agent_performance(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze agent/assignee performance metrics."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    resolution_hours = func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600

    by_assignee = db.query(
        Ticket.assigned_to,
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]), 1), else_=0)).label("resolved"),
        func.avg(resolution_hours).label("avg_resolution_hours"),
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.assigned_to.isnot(None),
    ).group_by(Ticket.assigned_to).order_by(func.count(Ticket.id).desc()).limit(20).all()

    return {
        "by_assignee": [
            {
                "assignee": a.assigned_to,
                "total_tickets": a.total,
                "resolved": a.resolved,
                "resolution_rate": round(a.resolved / a.total * 100, 1) if a.total > 0 else 0,
                "avg_resolution_hours": round(float(a.avg_resolution_hours or 0), 1),
            }
            for a in by_assignee
        ],
    }
