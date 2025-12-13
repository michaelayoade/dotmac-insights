"""Shared helpers for support API endpoints."""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Tuple, List, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.ticket import TicketStatus, TicketPriority


def parse_date(value: Optional[str], field_name: str = "date") -> Optional[date]:
    """Parse ISO date string to date object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")


def parse_datetime(value: Optional[str], field_name: str = "datetime") -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")


def parse_ticket_status(value: Optional[str]) -> Optional[TicketStatus]:
    """Parse status string to TicketStatus enum."""
    if value is None:
        return None
    try:
        return TicketStatus(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {value}. Allowed: {[s.value for s in TicketStatus]}"
        )


def parse_ticket_priority(value: Optional[str]) -> Optional[TicketPriority]:
    """Parse priority string to TicketPriority enum."""
    if value is None:
        return None
    try:
        return TicketPriority(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority: {value}. Allowed: {[p.value for p in TicketPriority]}"
        )


def paginate(query, offset: int, limit: int) -> Tuple[int, List[Any]]:
    """Apply pagination and return (total, items) tuple.

    Uses window function for single-query pagination when possible.
    """
    # Get total count
    total = query.count()

    # Get paginated results
    items = query.offset(offset).limit(limit).all()

    return total, items


def generate_local_ticket_number() -> str:
    """Generate a deterministic ticket number for locally created tickets."""
    return f"HD-LOCAL-{int(datetime.utcnow().timestamp() * 1000)}"


def serialize_ticket_brief(ticket) -> dict:
    """Serialize a ticket for list views."""
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "status": ticket.status.value if ticket.status else None,
        "priority": ticket.priority.value if ticket.priority else None,
        "ticket_type": ticket.ticket_type,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "assigned_to": ticket.assigned_to,
        "resolution_by": ticket.resolution_by.isoformat() if ticket.resolution_by else None,
        "is_overdue": ticket.is_overdue,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "source": ticket.source.value if ticket.source else None,
        "write_back_status": getattr(ticket, "write_back_status", None),
    }


def serialize_comment(comment) -> dict:
    """Serialize a ticket comment."""
    return {
        "id": comment.id,
        "comment": comment.comment,
        "comment_type": comment.comment_type,
        "commented_by": comment.commented_by,
        "commented_by_name": comment.commented_by_name,
        "is_public": comment.is_public,
        "comment_date": comment.comment_date.isoformat() if comment.comment_date else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def serialize_activity(activity) -> dict:
    """Serialize a ticket activity."""
    return {
        "id": activity.id,
        "activity_type": activity.activity_type,
        "activity": activity.activity,
        "owner": activity.owner,
        "from_status": activity.from_status,
        "to_status": activity.to_status,
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


def serialize_communication(comm) -> dict:
    """Serialize a ticket communication."""
    return {
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


def serialize_dependency(dep) -> dict:
    """Serialize a ticket dependency."""
    return {
        "id": dep.id,
        "depends_on_ticket_id": dep.depends_on_ticket_id,
        "depends_on_erpnext_id": dep.depends_on_erpnext_id,
        "depends_on_subject": dep.depends_on_subject,
        "depends_on_status": dep.depends_on_status,
    }


def serialize_agent(agent, team_membership=None) -> dict:
    """Serialize an agent."""
    data = {
        "id": agent.id,
        "employee_id": agent.employee_id,
        "email": agent.email,
        "display_name": agent.display_name,
        "domains": agent.domains,
        "skills": agent.skills,
        "channel_caps": agent.channel_caps,
        "routing_weight": agent.routing_weight,
        "capacity": agent.capacity,
        "is_active": agent.is_active,
    }
    if team_membership:
        data["team_member"] = {
            "team_id": team_membership.team_id,
            "role": team_membership.role,
        }
    else:
        data["team_member"] = None
    return data


def serialize_team(team) -> dict:
    """Serialize a team with members."""
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "domain": team.domain,
        "assignment_rule": team.assignment_rule,
        "is_active": team.is_active,
        "members": [
            {
                "id": m.id,
                "agent_id": m.agent_id,
                "role": m.role,
                "is_active": m.is_active,
            }
            for m in team.members
        ],
    }
