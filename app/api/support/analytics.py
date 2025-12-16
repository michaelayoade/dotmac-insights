"""Support analytics and insights endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract

from app.database import get_db
from app.models.ticket import Ticket, TicketStatus
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/overview", dependencies=[Depends(Require("analytics:read"))])
def get_support_overview(
    months: int = Query(default=6, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lightweight overview used by the support dashboards."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    total = db.query(func.count(Ticket.id)).scalar() or 0
    open_count = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.IN_PROGRESS])
    ).scalar() or 0
    resolved = db.query(func.count(Ticket.id)).filter(Ticket.status == TicketStatus.RESOLVED).scalar() or 0
    closed = db.query(func.count(Ticket.id)).filter(Ticket.status == TicketStatus.CLOSED).scalar() or 0

    # Resolution time (hours)
    resolution_hours = func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600
    resolution_stats = db.query(
        func.avg(resolution_hours).label("avg_hours"),
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.resolution_date.isnot(None),
        Ticket.opening_date.isnot(None),
        Ticket.resolution_date >= start_dt,
    ).first()

    # SLA attainment
    sla_met = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
        Ticket.resolution_date <= Ticket.resolution_by,
    ).scalar() or 0
    sla_total = db.query(func.count(Ticket.id)).filter(
        Ticket.resolution_by.isnot(None),
        Ticket.resolution_date.isnot(None),
    ).scalar() or 0

    return {
        "ticket_volume": {
            "total": total,
            "open": open_count,
            "resolved": resolved,
            "closed": closed,
        },
        "resolution_time": {
            "avg_hours": round(float(resolution_stats.avg_hours or 0), 1) if resolution_stats else 0,
            "sample_size": int(resolution_stats.count or 0) if resolution_stats else 0,
        },
        "sla": {
            "met": sla_met,
            "total_tracked": sla_total,
            "attainment_rate": round(sla_met / sla_total * 100, 1) if sla_total > 0 else 0,
        },
        "trend_window_months": months,
    }

@router.get("/analytics/volume-trend", dependencies=[Depends(Require("analytics:read"))])
def get_volume_trend(
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
def get_resolution_time_trend(
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
def get_tickets_by_category(
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


@router.get("/metrics", dependencies=[Depends(Require("analytics:read"))])
def get_support_metrics(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for support metrics expected by the frontend."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    total = db.query(func.count(Ticket.id)).filter(Ticket.created_at >= start_dt).scalar() or 0
    resolved = db.query(func.count(Ticket.id)).filter(
        Ticket.created_at >= start_dt,
        Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
    ).scalar() or 0
    avg_resolution_hours = db.query(
        func.avg(
            func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600
        )
    ).filter(
        Ticket.created_at >= start_dt,
        Ticket.resolution_date.isnot(None),
        Ticket.opening_date.isnot(None),
    ).scalar()

    return {
        "period_days": days,
        "total": total,
        "resolved": resolved,
        "open": max(total - resolved, 0),
        "avg_resolution_hours": round(float(avg_resolution_hours or 0), 1),
    }


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
