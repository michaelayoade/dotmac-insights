"""
Support Web Service - Business logic for the support web UI.

This service wraps database operations for the support module,
providing a clean interface for route handlers. It operates on
UnifiedTicket (the consolidated support ticket model).

All mutating methods do NOT commit the transaction. The caller
(route handler) is responsible for calling db.commit() after
the operation succeeds.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime, timedelta
import uuid
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
from app.services.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from app.auth import Principal


class SupportWebService:
    """
    Service class for support UI operations on UnifiedTicket.

    Encapsulates all database operations for the support module,
    providing a clean interface for route handlers.

    All mutating methods do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    # Allowed sort columns to prevent SQL injection via getattr
    ALLOWED_TICKET_SORTS = {
        "created_at", "updated_at", "ticket_number", "subject",
        "status", "priority", "ticket_type", "due_date",
    }

    def __init__(
        self,
        db: Session,
        user_id: Optional[int] = None,
        principal: Optional["Principal"] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.principal = principal

    # =========================================================================
    # DASHBOARD STATISTICS
    # =========================================================================

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get support dashboard statistics."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)

        # Ticket counts - use .value for PostgreSQL enum compatibility
        open_statuses = [
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.WAITING.value,
            TicketStatus.REOPENED.value
        ]
        total_open = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.in_(open_statuses)
        ).scalar() or 0

        urgent_tickets = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.priority == TicketPriority.URGENT.value,
            UnifiedTicket.status.notin_([TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value])
        ).scalar() or 0

        resolved_today = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status == TicketStatus.RESOLVED.value,
            UnifiedTicket.updated_at >= today
        ).scalar() or 0

        resolved_week = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status == TicketStatus.RESOLVED.value,
            UnifiedTicket.updated_at >= week_ago
        ).scalar() or 0

        created_today = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.created_at >= today
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
            UnifiedTicket.status.notin_([TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value])
        ).group_by(UnifiedTicket.priority).all()

        priority_distribution = {row.priority: row.count for row in priority_counts}

        return {
            "total_open": total_open,
            "urgent_tickets": urgent_tickets,
            "resolved_today": resolved_today,
            "resolved_week": resolved_week,
            "created_today": created_today,
            "status_distribution": status_distribution,
            "priority_distribution": priority_distribution,
        }

    def get_agent_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get agent workload statistics.

        Uses a single aggregate query instead of N+1 queries.
        """
        # Get agents with their ticket counts in a single query
        from sqlalchemy import outerjoin
        from sqlalchemy.orm import aliased

        # Subquery for open ticket counts per agent
        open_tickets_subq = (
            self.db.query(
                UnifiedTicket.assigned_to_id,
                func.count(UnifiedTicket.id).label("open_count")
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.status.notin_([TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value])
            )
            .group_by(UnifiedTicket.assigned_to_id)
            .subquery()
        )

        # Join agents with their ticket counts
        agents_with_counts = (
            self.db.query(
                Agent.id,
                Agent.display_name,
                Agent.email,
                Agent.employee_id,
                func.coalesce(open_tickets_subq.c.open_count, 0).label("open_tickets")
            )
            .outerjoin(open_tickets_subq, Agent.employee_id == open_tickets_subq.c.assigned_to_id)
            .filter(Agent.is_active == True)
            .order_by(func.coalesce(open_tickets_subq.c.open_count, 0).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "name": row.display_name or row.email or f"Agent {row.id}",
                "email": row.email,
                "open_tickets": row.open_tickets,
            }
            for row in agents_with_counts
        ]

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
        unassigned_only: bool = False,
        page: int = 1,
        per_page: int = 25,
        sort: str = "created_at",
        dir: str = "desc",
    ) -> Dict[str, Any]:
        """
        List tickets with filtering, search, and pagination.

        Args:
            unassigned_only: If True, only return tickets with no assigned agent.

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
        if unassigned_only:
            query = query.filter(UnifiedTicket.assigned_to_id.is_(None))
        elif assigned_to_id:
            query = query.filter(UnifiedTicket.assigned_to_id == assigned_to_id)

        # Count total
        total = query.count()

        # Sorting - validate sort column and direction
        if sort not in self.ALLOWED_TICKET_SORTS:
            sort = "created_at"
        if dir not in ("asc", "desc"):
            dir = "desc"

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

    def get_ticket(self, ticket_id: int) -> UnifiedTicket:
        """Get a single ticket by ID.

        Args:
            ticket_id: The ticket ID.

        Returns:
            The UnifiedTicket instance.

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id == ticket_id,
            UnifiedTicket.is_deleted == False
        ).first()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    def get_ticket_or_none(self, ticket_id: int) -> Optional[UnifiedTicket]:
        """Get a single ticket by ID, returning None if not found."""
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
        """Create a new ticket.

        Does NOT commit - caller must call db.commit().

        Args:
            data: Ticket data dict.

        Returns:
            The created UnifiedTicket (not yet committed).
        """
        # Generate unique ticket number using timestamp + random suffix
        # This avoids race conditions from max(id) + 1 approach
        if "ticket_number" not in data or not data["ticket_number"]:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            suffix = uuid.uuid4().hex[:4].upper()
            data["ticket_number"] = f"TKT-{timestamp}-{suffix}"

        # Set defaults
        data.setdefault("status", TicketStatus.OPEN.value if hasattr(TicketStatus, 'OPEN') else "open")
        data.setdefault("priority", TicketPriority.MEDIUM.value if hasattr(TicketPriority, 'MEDIUM') else "medium")
        data.setdefault("created_at", datetime.utcnow())
        if self.user_id:
            data.setdefault("created_by_id", self.user_id)
            data.setdefault("updated_by_id", self.user_id)

        ticket = UnifiedTicket(**data)
        self.db.add(ticket)
        # Flush to get the ID without committing
        self.db.flush()

        return ticket

    def update_ticket(self, ticket_id: int, data: Dict[str, Any]) -> UnifiedTicket:
        """Update an existing ticket.

        Does NOT commit - caller must call db.commit().

        Args:
            ticket_id: The ticket ID.
            data: Fields to update.

        Returns:
            The updated UnifiedTicket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        data["updated_at"] = datetime.utcnow()
        if self.user_id:
            data["updated_by_id"] = self.user_id

        for key, value in data.items():
            if hasattr(ticket, key) and value is not None:
                setattr(ticket, key, value)

        return ticket

    def delete_ticket(self, ticket_id: int) -> UnifiedTicket:
        """Soft delete a ticket.

        Does NOT commit - caller must call db.commit().

        Args:
            ticket_id: The ticket ID.

        Returns:
            The deleted UnifiedTicket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        ticket.is_deleted = True
        ticket.deleted_at = datetime.utcnow()
        if self.user_id:
            ticket.deleted_by_id = self.user_id

        return ticket

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def bulk_update_status(self, ids: List[int], status: TicketStatus) -> int:
        """Bulk update status for multiple tickets.

        Does NOT commit - caller must call db.commit().

        Args:
            ids: List of ticket IDs to update.
            status: Target status value.

        Returns:
            Number of tickets updated.
        """
        if not ids:
            return 0

        now = datetime.utcnow()
        updates = {
            "status": status.value if hasattr(status, 'value') else status,
            "updated_at": now,
        }
        if self.user_id:
            updates["updated_by_id"] = self.user_id

        # Auto-set resolution date for resolved/closed
        if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            updates["resolution_date"] = now

        updated = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id.in_(ids),
            UnifiedTicket.is_deleted == False,
        ).update(updates, synchronize_session=False)

        return updated

    def bulk_update_priority(self, ids: List[int], priority: TicketPriority) -> int:
        """Bulk update priority for multiple tickets.

        Does NOT commit - caller must call db.commit().

        Args:
            ids: List of ticket IDs to update.
            priority: Target priority value.

        Returns:
            Number of tickets updated.
        """
        if not ids:
            return 0

        updated = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id.in_(ids),
            UnifiedTicket.is_deleted == False,
        ).update(
            {
                "priority": priority.value if hasattr(priority, 'value') else priority,
                "updated_at": datetime.utcnow(),
                "updated_by_id": self.user_id if self.user_id else None,
            },
            synchronize_session=False,
        )

        return updated

    def bulk_delete(self, ids: List[int]) -> int:
        """Bulk soft-delete multiple tickets.

        Does NOT commit - caller must call db.commit().

        Args:
            ids: List of ticket IDs to delete.

        Returns:
            Number of tickets deleted.
        """
        if not ids:
            return 0

        now = datetime.utcnow()
        deleted = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id.in_(ids),
            UnifiedTicket.is_deleted == False,
        ).update(
            {
                "is_deleted": True,
                "deleted_at": now,
                "updated_at": now,
                "deleted_by_id": self.user_id if self.user_id else None,
                "updated_by_id": self.user_id if self.user_id else None,
            },
            synchronize_session=False,
        )

        return deleted

    def update_field(self, ticket_id: int, field: str, value: str) -> UnifiedTicket:
        """Update a single field on a ticket (for inline editing).

        Does NOT commit - caller must call db.commit().

        Args:
            ticket_id: The ticket ID.
            field: The field name to update (status, priority).
            value: The new value as string.

        Returns:
            The updated ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If field is not allowed or value is invalid.
        """
        allowed_fields = {"status", "priority"}
        if field not in allowed_fields:
            raise ValidationError(f"Field '{field}' is not allowed for inline editing")

        ticket = self.get_ticket(ticket_id)

        if field == "status":
            try:
                status = TicketStatus(value)
                ticket.status = status.value
                # Auto-set resolution date for resolved/closed
                if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                    if ticket.resolution_date is None:
                        ticket.resolution_date = datetime.utcnow()
            except ValueError:
                raise ValidationError(f"Invalid status value: {value}")

        elif field == "priority":
            try:
                ticket.priority = TicketPriority(value).value
            except ValueError:
                raise ValidationError(f"Invalid priority value: {value}")

        ticket.updated_at = datetime.utcnow()
        if self.user_id:
            ticket.updated_by_id = self.user_id

        return ticket

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

    def get_tickets_for_party(
        self,
        party_id: int,
        limit: int = 10
    ) -> List[UnifiedTicket]:
        """Get tickets associated with a party."""
        return self.db.query(UnifiedTicket).filter(
            UnifiedTicket.party_id == party_id,
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
