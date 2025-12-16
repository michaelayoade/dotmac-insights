"""Inbox Analytics API - Dashboard metrics and performance data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from app.database import get_db
from app.auth import Require
from app.models.omni import OmniConversation, OmniMessage, OmniChannel, InboxContact
from app.models.agent import Agent

router = APIRouter()


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/analytics/summary",
    dependencies=[Depends(Require("support:read"))],
)
async def get_analytics_summary(
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get inbox analytics summary for dashboard."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Total conversations in period
    total_conversations = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.created_at >= start_date)
        .scalar()
    ) or 0

    # By status
    status_counts = (
        db.query(
            OmniConversation.status,
            func.count(OmniConversation.id),
        )
        .filter(OmniConversation.created_at >= start_date)
        .group_by(OmniConversation.status)
        .all()
    )
    by_status = {s or "open": c for s, c in status_counts}

    # Currently open (all time)
    open_count = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.status == "open")
        .scalar()
    ) or 0

    pending_count = (
        db.query(func.count(OmniConversation.id))
        .filter(OmniConversation.status == "pending")
        .scalar()
    ) or 0

    # Unread count
    total_unread = (
        db.query(func.sum(OmniConversation.unread_count))
        .filter(OmniConversation.status.in_(["open", "pending"]))
        .scalar()
    ) or 0

    # Resolved today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    resolved_today = (
        db.query(func.count(OmniConversation.id))
        .filter(
            OmniConversation.resolved_at >= today_start,
            OmniConversation.status == "resolved",
        )
        .scalar()
    ) or 0

    # Messages in period
    total_messages = (
        db.query(func.count(OmniMessage.id))
        .filter(OmniMessage.created_at >= start_date)
        .scalar()
    ) or 0

    inbound_messages = (
        db.query(func.count(OmniMessage.id))
        .filter(
            OmniMessage.created_at >= start_date,
            OmniMessage.direction == "inbound",
        )
        .scalar()
    ) or 0

    outbound_messages = (
        db.query(func.count(OmniMessage.id))
        .filter(
            OmniMessage.created_at >= start_date,
            OmniMessage.direction == "outbound",
        )
        .scalar()
    ) or 0

    # Average first response time (for conversations with first_response_at)
    avg_first_response = (
        db.query(
            func.avg(
                func.extract(
                    "epoch",
                    OmniConversation.first_response_at - OmniConversation.created_at,
                )
            )
        )
        .filter(
            OmniConversation.first_response_at.isnot(None),
            OmniConversation.created_at >= start_date,
        )
        .scalar()
    )
    avg_first_response_hours = round(avg_first_response / 3600, 1) if avg_first_response else None

    # By channel
    channel_counts = (
        db.query(
            OmniChannel.type,
            func.count(OmniConversation.id),
        )
        .join(OmniConversation, OmniConversation.channel_id == OmniChannel.id)
        .filter(OmniConversation.created_at >= start_date)
        .group_by(OmniChannel.type)
        .all()
    )
    by_channel = {t: c for t, c in channel_counts}

    # Unassigned count
    unassigned_count = (
        db.query(func.count(OmniConversation.id))
        .filter(
            OmniConversation.status.in_(["open", "pending"]),
            OmniConversation.assigned_agent_id.is_(None),
            OmniConversation.assigned_team_id.is_(None),
        )
        .scalar()
    ) or 0

    return {
        "period_days": days,
        "total_conversations": total_conversations,
        "open_count": open_count,
        "pending_count": pending_count,
        "resolved_today": resolved_today,
        "total_unread": total_unread,
        "unassigned_count": unassigned_count,
        "total_messages": total_messages,
        "inbound_messages": inbound_messages,
        "outbound_messages": outbound_messages,
        "avg_first_response_hours": avg_first_response_hours,
        "by_status": by_status,
        "by_channel": by_channel,
    }


@router.get(
    "/analytics/volume",
    dependencies=[Depends(Require("support:read"))],
)
async def get_volume_analytics(
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get conversation volume by day for charts."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Volume by day
    daily_volume = (
        db.query(
            func.date(OmniConversation.created_at).label("date"),
            func.count(OmniConversation.id).label("count"),
        )
        .filter(OmniConversation.created_at >= start_date)
        .group_by(func.date(OmniConversation.created_at))
        .order_by(func.date(OmniConversation.created_at))
        .all()
    )

    # Volume by channel by day
    channel_daily = (
        db.query(
            func.date(OmniConversation.created_at).label("date"),
            OmniChannel.type.label("channel"),
            func.count(OmniConversation.id).label("count"),
        )
        .join(OmniConversation, OmniConversation.channel_id == OmniChannel.id)
        .filter(OmniConversation.created_at >= start_date)
        .group_by(func.date(OmniConversation.created_at), OmniChannel.type)
        .order_by(func.date(OmniConversation.created_at))
        .all()
    )

    # Transform channel data into per-day structure
    channel_by_day: Dict[str, Dict[str, int]] = {}
    for row in channel_daily:
        date_str = row.date.isoformat() if row.date else ""
        if date_str not in channel_by_day:
            channel_by_day[date_str] = {}
        channel_by_day[date_str][row.channel] = row.count

    return {
        "period_days": days,
        "daily_volume": [
            {"date": d.date.isoformat() if d.date else "", "count": d.count}
            for d in daily_volume
        ],
        "channel_by_day": [
            {"date": date, **channels}
            for date, channels in channel_by_day.items()
        ],
    }


@router.get(
    "/analytics/agents",
    dependencies=[Depends(Require("support:read"))],
)
async def get_agent_analytics(
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get agent performance metrics."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Conversations per agent
    agent_conversations = (
        db.query(
            Agent.id,
            Agent.display_name,
            Agent.email,
            func.count(OmniConversation.id).label("conversation_count"),
        )
        .join(OmniConversation, OmniConversation.assigned_agent_id == Agent.id)
        .filter(OmniConversation.assigned_at >= start_date)
        .group_by(Agent.id, Agent.display_name, Agent.email)
        .order_by(func.count(OmniConversation.id).desc())
        .all()
    )

    # Messages sent per agent
    agent_messages = (
        db.query(
            Agent.id,
            func.count(OmniMessage.id).label("message_count"),
        )
        .join(OmniMessage, OmniMessage.agent_id == Agent.id)
        .filter(
            OmniMessage.created_at >= start_date,
            OmniMessage.direction == "outbound",
        )
        .group_by(Agent.id)
        .all()
    )
    messages_by_agent = {a.id: a.message_count for a in agent_messages}

    # Average first response time per agent
    agent_response_times = (
        db.query(
            OmniConversation.assigned_agent_id,
            func.avg(
                func.extract(
                    "epoch",
                    OmniConversation.first_response_at - OmniConversation.created_at,
                )
            ).label("avg_response_seconds"),
        )
        .filter(
            OmniConversation.first_response_at.isnot(None),
            OmniConversation.assigned_agent_id.isnot(None),
            OmniConversation.created_at >= start_date,
        )
        .group_by(OmniConversation.assigned_agent_id)
        .all()
    )
    response_times_by_agent = {
        a.assigned_agent_id: round(a.avg_response_seconds / 3600, 1) if a.avg_response_seconds else None
        for a in agent_response_times
    }

    return {
        "period_days": days,
        "agents": [
            {
                "id": a.id,
                "name": a.display_name or a.email,
                "conversations": a.conversation_count,
                "messages_sent": messages_by_agent.get(a.id, 0),
                "avg_response_time_hours": response_times_by_agent.get(a.id),
            }
            for a in agent_conversations
        ],
    }


@router.get(
    "/analytics/channels",
    dependencies=[Depends(Require("support:read"))],
)
async def get_channel_analytics(
    days: int = Query(default=7, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get channel performance metrics."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Conversations per channel
    channel_stats = (
        db.query(
            OmniChannel.id,
            OmniChannel.name,
            OmniChannel.type,
            func.count(OmniConversation.id).label("conversation_count"),
            func.avg(
                func.extract(
                    "epoch",
                    OmniConversation.first_response_at - OmniConversation.created_at,
                )
            ).label("avg_response_seconds"),
        )
        .outerjoin(OmniConversation, and_(
            OmniConversation.channel_id == OmniChannel.id,
            OmniConversation.created_at >= start_date,
        ))
        .filter(OmniChannel.is_active == True)
        .group_by(OmniChannel.id, OmniChannel.name, OmniChannel.type)
        .all()
    )

    return {
        "period_days": days,
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "conversation_count": c.conversation_count or 0,
                "avg_response_time_hours": round(c.avg_response_seconds / 3600, 1) if c.avg_response_seconds else None,
            }
            for c in channel_stats
        ],
    }
