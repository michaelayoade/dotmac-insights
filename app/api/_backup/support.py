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

from app.database import get_db
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.conversation import Conversation, ConversationStatus
from app.models.customer import Customer
from app.auth import Require
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
    ).group_by(Ticket.status).all()

    status_counts: Dict[str, int] = {row.status.value: int(getattr(row, "count", 0) or 0) for row in ticket_by_status}
    total_tickets: int = sum(status_counts.values())
    open_tickets: int = status_counts.get("open", 0) + status_counts.get("replied", 0)

    # Open tickets by priority
    by_priority = db.query(
        Ticket.priority,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).group_by(Ticket.priority).all()

    priority_counts: Dict[str, int] = {row.priority.value: int(getattr(row, "count", 0) or 0) for row in by_priority}

    # SLA metrics
    sla_met = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
        Ticket.resolution_date <= Ticket.resolution_by
    ).scalar() or 0

    sla_breached = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        or_(
            Ticket.resolution_date > Ticket.resolution_by,
            and_(
                Ticket.resolution_date.is_(None),
                Ticket.resolution_by < func.current_timestamp()
            )
        )
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
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
    ).scalar() or 0

    # Unassigned tickets
    unassigned = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        Ticket.assigned_to.is_(None),
        Ticket.assigned_employee_id.is_(None),
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
    query = db.query(Ticket)

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
            }
            for t in tickets
        ],
    }


@router.get("/tickets/{ticket_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed ticket information."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    customer = None
    if ticket.customer_id:
        cust = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email, "phone": cust.phone}

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
        "external_ids": {
            "erpnext_id": ticket.erpnext_id,
            "splynx_id": ticket.splynx_id,
        },
        "customer": customer,
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
