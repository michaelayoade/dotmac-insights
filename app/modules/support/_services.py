"""
Support Web Service - Encapsulates business logic for support UI.

This service wraps database operations and provides a clean interface
for support routes, reducing direct DB queries in route handlers.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_

from app.models.unified_ticket import (
    UnifiedTicket,
    TicketStatus,
    TicketPriority,
    TicketType,
    TicketChannel,
    TicketSource,
)
from app.models.agent import Agent, Team, TeamMember
from app.models.support_canned import CannedResponse
from app.models.support_sla import SLAPolicy
from app.models.employee import Employee
from app.models.contact import Contact


class SupportWebService:
    """
    Service class for support UI operations.

    Encapsulates all database operations for the support module,
    providing a clean interface for route handlers.
    """

    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # DASHBOARD STATISTICS
    # =========================================================================

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get support dashboard statistics."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)

        # Ticket counts
        total_open = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.in_(["open", "in_progress", "pending", "waiting_on_customer"])
        ).scalar() or 0

        urgent_tickets = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.priority == "urgent",
            UnifiedTicket.status.notin_(["closed", "resolved"])
        ).scalar() or 0

        resolved_today = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status == "resolved",
            UnifiedTicket.updated_at >= today
        ).scalar() or 0

        resolved_week = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status == "resolved",
            UnifiedTicket.updated_at >= week_ago
        ).scalar() or 0

        # Status distribution
        status_counts = self.db.query(
            UnifiedTicket.status,
            func.count(UnifiedTicket.id).label("count")
        ).filter(
            UnifiedTicket.is_deleted == False
        ).group_by(UnifiedTicket.status).all()

        status_distribution = {row.status: row.count for row in status_counts}

        # Priority distribution
        priority_counts = self.db.query(
            UnifiedTicket.priority,
            func.count(UnifiedTicket.id).label("count")
        ).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.notin_(["closed", "resolved"])
        ).group_by(UnifiedTicket.priority).all()

        priority_distribution = {row.priority: row.count for row in priority_counts}

        return {
            "total_open": total_open,
            "urgent_tickets": urgent_tickets,
            "resolved_today": resolved_today,
            "resolved_week": resolved_week,
            "status_distribution": status_distribution,
            "priority_distribution": priority_distribution,
        }

    def get_agent_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get agent workload statistics."""
        agents = self.db.query(Agent).filter(
            Agent.is_active == True
        ).limit(limit).all()

        agent_stats = []
        for agent in agents:
            open_count = self.db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.assigned_to_id == agent.employee_id,
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.status.notin_(["closed", "resolved"])
            ).scalar() or 0

            agent_stats.append({
                "id": agent.id,
                "name": agent.display_name or agent.email or f"Agent {agent.id}",
                "email": agent.email,
                "open_tickets": open_count,
            })

        return agent_stats

    # =========================================================================
    # TICKET LISTING
    # =========================================================================

    def list_tickets(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        type: Optional[str] = None,
        channel: Optional[str] = None,
        assigned_to_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 25,
        sort: str = "created_at",
        dir: str = "desc",
    ) -> Dict[str, Any]:
        """
        List tickets with filtering, search, and pagination.

        Returns:
            Dict with 'items', 'total', 'page', 'per_page', 'pages'
        """
        query = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.is_deleted == False
        )

        # Search
        if q:
            search_filter = or_(
                UnifiedTicket.subject.ilike(f"%{q}%"),
                UnifiedTicket.ticket_number.ilike(f"%{q}%"),
                UnifiedTicket.contact_name.ilike(f"%{q}%"),
                UnifiedTicket.contact_email.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        # Filters
        if status:
            query = query.filter(UnifiedTicket.status == status)
        if priority:
            query = query.filter(UnifiedTicket.priority == priority)
        if type:
            query = query.filter(UnifiedTicket.ticket_type == type)
        if channel:
            query = query.filter(UnifiedTicket.channel == channel)
        if assigned_to_id:
            query = query.filter(UnifiedTicket.assigned_to_id == assigned_to_id)

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(UnifiedTicket, sort, UnifiedTicket.created_at)
        if dir == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        # Pagination
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    # =========================================================================
    # TICKET CRUD
    # =========================================================================

    def get_ticket(self, ticket_id: int) -> Optional[UnifiedTicket]:
        """Get a single ticket by ID."""
        return self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id == ticket_id,
            UnifiedTicket.is_deleted == False
        ).first()

    def get_ticket_by_number(self, ticket_number: str) -> Optional[UnifiedTicket]:
        """Get a ticket by its ticket number."""
        return self.db.query(UnifiedTicket).filter(
            UnifiedTicket.ticket_number == ticket_number,
            UnifiedTicket.is_deleted == False
        ).first()

    def create_ticket(self, data: Dict[str, Any]) -> UnifiedTicket:
        """Create a new ticket."""
        # Generate ticket number if not provided
        if "ticket_number" not in data or not data["ticket_number"]:
            max_id = self.db.query(func.max(UnifiedTicket.id)).scalar() or 0
            data["ticket_number"] = f"TKT-{max_id + 1:06d}"

        # Set defaults
        data.setdefault("status", TicketStatus.OPEN.value if hasattr(TicketStatus, 'OPEN') else "open")
        data.setdefault("priority", TicketPriority.MEDIUM.value if hasattr(TicketPriority, 'MEDIUM') else "medium")
        data.setdefault("created_at", datetime.utcnow())

        ticket = UnifiedTicket(**data)
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    def update_ticket(self, ticket_id: int, data: Dict[str, Any]) -> Optional[UnifiedTicket]:
        """Update an existing ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        data["updated_at"] = datetime.utcnow()

        for key, value in data.items():
            if hasattr(ticket, key) and value is not None:
                setattr(ticket, key, value)

        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    def delete_ticket(self, ticket_id: int) -> bool:
        """Soft delete a ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False

        ticket.is_deleted = True
        ticket.deleted_at = datetime.utcnow()
        self.db.commit()

        return True

    # =========================================================================
    # RELATED DATA
    # =========================================================================

    def get_recent_tickets(
        self,
        limit: int = 10,
        status_filter: Optional[List[str]] = None
    ) -> List[UnifiedTicket]:
        """Get recent tickets, optionally filtered by status."""
        query = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.is_deleted == False
        )

        if status_filter:
            query = query.filter(UnifiedTicket.status.in_(status_filter))

        return query.order_by(UnifiedTicket.created_at.desc()).limit(limit).all()

    def get_tickets_for_contact(
        self,
        contact_id: int,
        limit: int = 10
    ) -> List[UnifiedTicket]:
        """Get tickets associated with a contact."""
        return self.db.query(UnifiedTicket).filter(
            UnifiedTicket.unified_contact_id == contact_id,
            UnifiedTicket.is_deleted == False
        ).order_by(UnifiedTicket.created_at.desc()).limit(limit).all()

    def get_tickets_for_customer(
        self,
        customer_id: int,
        limit: int = 10
    ) -> List[UnifiedTicket]:
        """Get tickets associated with a customer."""
        return self.db.query(UnifiedTicket).filter(
            UnifiedTicket.unified_contact_id == customer_id,
            UnifiedTicket.is_deleted == False
        ).order_by(UnifiedTicket.created_at.desc()).limit(limit).all()

    # =========================================================================
    # AGENTS
    # =========================================================================

    def list_agents(
        self,
        active_only: bool = True,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List agents with pagination."""
        query = self.db.query(Agent)

        if active_only:
            query = query.filter(Agent.is_active == True)

        total = query.count()
        offset = (page - 1) * per_page
        items = query.order_by(Agent.display_name).offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_agent(self, agent_id: int) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.db.query(Agent).filter(Agent.id == agent_id).first()

    # =========================================================================
    # CANNED RESPONSES
    # =========================================================================

    def list_canned_responses(
        self,
        active_only: bool = True,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List canned responses with pagination."""
        query = self.db.query(CannedResponse)

        if active_only:
            query = query.filter(CannedResponse.is_active == True)

        total = query.count()
        offset = (page - 1) * per_page
        items = query.order_by(CannedResponse.name).offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    # =========================================================================
    # SLA POLICIES
    # =========================================================================

    def list_sla_policies(
        self,
        active_only: bool = True,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List SLA policies with pagination."""
        query = self.db.query(SLAPolicy)

        if active_only:
            query = query.filter(SLAPolicy.is_active == True)

        total = query.count()
        offset = (page - 1) * per_page
        items = query.order_by(SLAPolicy.name).offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }
