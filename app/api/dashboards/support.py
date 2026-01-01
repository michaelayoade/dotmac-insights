"""
Support Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.api.dashboards.common import resolve_currency_or_raise, parse_date_param

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.conversation import Conversation, ConversationStatus, Message

router = APIRouter(tags=["dashboards"])

# =============================================================================
# SUPPORT DASHBOARD - Consolidated (7 calls → 1)
# =============================================================================

@router.get("/support", dependencies=[Depends(Require("support:read"))])
@cached("dashboard-support", ttl=CACHE_TTL["short"])
async def get_support_dashboard(
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Support Dashboard endpoint.

    Combines data from:
    - Support dashboard (open, resolved, overdue tickets)
    - Volume trend (6 months)
    - SLA performance
    - Tickets by category
    - Queue health
    - SLA breaches summary
    - Teams and agents count
    """
    # Import ticket models dynamically to avoid circular imports
    from app.models.unified_ticket import UnifiedTicket as Ticket, TicketStatus, TicketPriority
    from app.models.agent import Team, Agent

    now = datetime.now(timezone.utc)
    today = date.today()
    thirty_days_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)
    start_dt = parse_date_param(start_date, "start_date")
    end_dt = parse_date_param(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    range_start = datetime.combine(start_dt, datetime.min.time()) if start_dt else None
    range_end = datetime.combine(end_dt, datetime.max.time()) if end_dt else None

    def apply_range_filter(query, column):
        if range_start:
            query = query.filter(column >= range_start)
        if range_end:
            query = query.filter(column <= range_end)
        return query

    # =========== MAIN METRICS ===========
    # Note: Database enum uses lowercase values, so we use the enum .value attribute
    open_status_values = ["open", "in_progress", "waiting"]
    resolved_status_values = ["resolved", "closed"]

    open_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values)
    )
    open_tickets_query = apply_range_filter(open_tickets_query, Ticket.created_at)
    open_tickets = open_tickets_query.scalar() or 0

    resolved_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(resolved_status_values)
    )
    resolved_tickets_query = apply_range_filter(resolved_tickets_query, Ticket.created_at)
    resolved_tickets = resolved_tickets_query.scalar() or 0

    overdue_cutoff = range_end or now
    overdue_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values),
        Ticket.resolution_by < overdue_cutoff,
    )
    overdue_tickets_query = apply_range_filter(overdue_tickets_query, Ticket.created_at)
    overdue_tickets = overdue_tickets_query.scalar() or 0

    unassigned_tickets_query = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_(open_status_values),
        Ticket.assigned_to_id.is_(None),
    )
    unassigned_tickets_query = apply_range_filter(unassigned_tickets_query, Ticket.created_at)
    unassigned_tickets = unassigned_tickets_query.scalar() or 0

    # Average resolution time (hours)
    avg_resolution_query = db.query(
        func.avg(func.extract('epoch', Ticket.resolved_at - Ticket.created_at) / 3600)
    ).filter(
        Ticket.resolved_at.isnot(None),
        Ticket.created_at.isnot(None),
    )
    avg_resolution_query = apply_range_filter(avg_resolution_query, Ticket.created_at)
    avg_resolution = avg_resolution_query.scalar()
    avg_resolution_hours = round(float(avg_resolution or 0), 1)

    # SLA attainment (use resolution_by as indicator that SLA applies)
    total_with_sla_query = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.status.in_(resolved_status_values)
    )
    total_with_sla_query = apply_range_filter(total_with_sla_query, Ticket.created_at)
    total_with_sla = total_with_sla_query.scalar() or 0

    sla_met_query = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.status.in_(resolved_status_values),
        Ticket.resolution_sla_breached == False,
    )
    sla_met_query = apply_range_filter(sla_met_query, Ticket.created_at)
    sla_met = sla_met_query.scalar() or 0

    sla_attainment = round(sla_met / total_with_sla * 100, 1) if total_with_sla > 0 else 100

    # =========== VOLUME TREND (6 months) ===========
    trunc = func.date_trunc("month", Ticket.created_at)
    trend_start = range_start or six_months_ago
    volume_query = db.query(
        func.to_char(trunc, "YYYY-MM").label("period"),
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= trend_start,
    )
    if range_end:
        volume_query = volume_query.filter(Ticket.created_at <= range_end)
    volume_query = volume_query.group_by(trunc).order_by(trunc)
    volume_trend = [
        {
            "period": r.period,
            "count": r.count,
        }
        for r in volume_query.all()
    ]

    # =========== SLA PERFORMANCE (6 months) ===========
    sla_performance = []
    sla_query = db.query(
        func.to_char(trunc, "YYYY-MM").label("period"),
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.resolution_sla_breached == False, 1), else_=0)).label("met"),
        func.sum(case((Ticket.resolution_sla_breached == True, 1), else_=0)).label("breached"),
    ).filter(
        Ticket.created_at >= trend_start,
        Ticket.resolution_by.isnot(None),
    )
    if range_end:
        sla_query = sla_query.filter(Ticket.created_at <= range_end)
    for r in sla_query.group_by(trunc).order_by(trunc).all():
        total = r.total or 0
        met = int(r.met or 0)
        breached = int(r.breached or 0)
        sla_performance.append({
            "period": r.period,
            "total": total,
            "met": met,
            "breached": breached,
            "rate": round(met / total * 100, 1) if total > 0 else 100,
        })

    # =========== BY CATEGORY (30 days) ===========
    category_start = range_start or thirty_days_ago
    by_category_query = db.query(
        Ticket.category,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.created_at >= category_start,
    )
    if range_end:
        by_category_query = by_category_query.filter(Ticket.created_at <= range_end)
    by_category = [
        {
            "category": r.category or "Uncategorized",
            "count": r.count,
        }
        for r in by_category_query.group_by(Ticket.category).order_by(func.count(Ticket.id).desc()).limit(10).all()
    ]

    # =========== QUEUE HEALTH ===========
    # Avg wait time for unassigned tickets
    avg_wait_query = db.query(
        func.avg(func.extract('epoch', func.now() - Ticket.created_at) / 3600)
    ).filter(
        Ticket.assigned_to_id.is_(None),
        Ticket.status == "open",
    )
    avg_wait_query = apply_range_filter(avg_wait_query, Ticket.created_at)
    avg_wait = avg_wait_query.scalar()

    # Agent capacity
    total_agents = db.query(func.count(Agent.id)).filter(Agent.is_active == True).scalar() or 0

    # Current load (open tickets per agent)
    current_load = round(open_tickets / total_agents, 1) if total_agents > 0 else 0

    queue_health = {
        "unassigned_count": unassigned_tickets,
        "avg_wait_hours": round(float(avg_wait or 0), 1),
        "total_agents": total_agents,
        "current_load": current_load,
    }

    # =========== SLA BREACHES (30 days) ===========
    breaches_query = db.query(
        Ticket.priority,
        func.count(Ticket.id).label("breach_count"),
    ).filter(
        Ticket.resolution_sla_breached == True,
        Ticket.created_at >= category_start,
    ).group_by(Ticket.priority)
    if range_end:
        breaches_query = breaches_query.filter(Ticket.created_at <= range_end)

    sla_breaches = {
        r.priority.value if r.priority else "unknown": int(r.breach_count or 0)
        for r in breaches_query.all()
    }
    total_breaches = sum(sla_breaches.values())

    # =========== TEAMS & AGENTS ===========
    team_count = db.query(func.count(Team.id)).filter(Team.is_active == True).scalar() or 0
    active_agents = total_agents

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
            "overdue_tickets": overdue_tickets,
            "unassigned_tickets": unassigned_tickets,
            "avg_resolution_hours": avg_resolution_hours,
            "sla_attainment": sla_attainment,
            "team_count": team_count,
            "agent_count": active_agents,
        },

        "volume_trend": volume_trend,
        "sla_performance": sla_performance,
        "by_category": by_category,
        "queue_health": queue_health,

        "sla_breaches": {
            "total": total_breaches,
            "by_priority": sla_breaches,
        },
    }


# =============================================================================
# INBOX DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/inbox", dependencies=[Depends(Require("inbox:read"))])
@cached("dashboard-inbox", ttl=CACHE_TTL["short"])
async def get_inbox_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Inbox Dashboard endpoint.

    Combines data from:
    - Conversation summary (open, pending, resolved)
    - By channel breakdown
    - By priority breakdown
    - Recent conversations
    """
    from app.models.omni import OmniConversation, OmniChannel

    now = datetime.now(timezone.utc)
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # =========== CONVERSATION COUNTS ===========
    open_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "open"
    ).scalar() or 0

    pending_count = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "pending"
    ).scalar() or 0

    resolved_today = db.query(func.count(OmniConversation.id)).filter(
        OmniConversation.status == "resolved",
        OmniConversation.resolved_at >= today_start
    ).scalar() or 0

    total_unread = db.query(func.sum(OmniConversation.unread_count)).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).scalar() or 0

    # =========== BY CHANNEL ===========
    by_channel = db.query(
        OmniChannel.type,
        func.count(OmniConversation.id).label("count")
    ).join(OmniChannel, OmniConversation.channel_id == OmniChannel.id).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).group_by(OmniChannel.type).all()

    channel_breakdown = {
        row.type: row.count
        for row in by_channel
    }

    # =========== BY PRIORITY ===========
    by_priority = db.query(
        OmniConversation.priority,
        func.count(OmniConversation.id).label("count")
    ).filter(
        OmniConversation.status.in_(["open", "pending"])
    ).group_by(OmniConversation.priority).all()

    priority_breakdown = {
        row.priority: row.count
        for row in by_priority
    }

    # =========== RECENT CONVERSATIONS ===========
    recent_conversations = [
        {
            "id": c.id,
            "subject": c.subject,
            "contact_name": c.contact_name,
            "contact_email": c.contact_email,
            "status": c.status,
            "priority": c.priority,
            "unread_count": c.unread_count,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        }
        for c in db.query(OmniConversation).filter(
            OmniConversation.status.in_(["open", "pending"])
        ).order_by(
            OmniConversation.last_message_at.desc()
        ).limit(10).all()
    ]

    # =========== AVG RESPONSE TIME ===========
    avg_response = db.query(
        func.avg(
            func.extract(
                "epoch",
                OmniConversation.first_response_at - OmniConversation.created_at,
            )
        )
    ).filter(
        OmniConversation.first_response_at.isnot(None)
    ).scalar()
    avg_response_hours = round(float(avg_response or 0) / 3600, 1)

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "open_count": open_count,
            "pending_count": pending_count,
            "resolved_today": resolved_today,
            "total_unread": int(total_unread or 0),
        },

        "by_channel": channel_breakdown,
        "by_priority": priority_breakdown,
        "avg_response_time_hours": avg_response_hours,

        "recent": recent_conversations,
    }


