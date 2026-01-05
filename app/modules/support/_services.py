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
from app.models.agent import Team, TeamMember
from app.models.party import Party, PartyRole
from app.models.support_canned import CannedResponse
from app.models.support_kb import KBArticle, KBCategory
from app.models.support_sla import SLAPolicy
from app.models.ticket import HDTicketComment, HDTicketActivity
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

    def _coerce_status(self, value: Any) -> Optional[TicketStatus]:
        """Coerce a status value into a TicketStatus enum."""
        if value is None:
            return None
        if isinstance(value, TicketStatus):
            return value
        if isinstance(value, str):
            try:
                return TicketStatus(value)
            except ValueError:
                raise ValidationError(f"Invalid status value: {value}")
        raise ValidationError(f"Invalid status value: {value}")

    def _apply_status_change(
        self,
        ticket: UnifiedTicket,
        status: TicketStatus,
        resolution: Optional[str] = None,
        resolution_type: Optional[str] = None,
    ) -> None:
        """Apply lifecycle-aware status changes on a ticket."""
        now = datetime.utcnow()
        previous_status = self._coerce_status(ticket.status)

        if status == TicketStatus.RESOLVED:
            if resolution is not None or resolution_type is not None:
                ticket.resolve(resolution or "", resolution_type)
                return
            if ticket.resolution or ticket.resolution_type:
                ticket.resolve(ticket.resolution or "", ticket.resolution_type)
                return
            ticket.status = TicketStatus.RESOLVED
            ticket.resolved_at = now
            if ticket.created_at:
                ticket.resolution_time_seconds = int(
                    (ticket.resolved_at - ticket.created_at).total_seconds()
                )
            return

        if status == TicketStatus.CLOSED:
            if ticket.resolved_at is None and previous_status != TicketStatus.RESOLVED:
                if resolution is not None or resolution_type is not None or ticket.resolution or ticket.resolution_type:
                    ticket.resolve(resolution or (ticket.resolution or ""), resolution_type or ticket.resolution_type)
                else:
                    ticket.resolved_at = now
                    if ticket.created_at:
                        ticket.resolution_time_seconds = int(
                            (ticket.resolved_at - ticket.created_at).total_seconds()
                        )
            ticket.close()
            return

        if status == TicketStatus.REOPENED:
            ticket.reopen()
            return

        ticket.status = status
        if previous_status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            ticket.resolved_at = None
            ticket.closed_at = None
            ticket.resolution_time_seconds = None

    # =========================================================================
    # DASHBOARD STATISTICS
    # =========================================================================

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get support dashboard statistics."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        now = datetime.utcnow()
        due_soon = now + timedelta(hours=24)

        # Ticket counts - use .value for PostgreSQL enum compatibility
        open_statuses = [
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.WAITING.value,
            TicketStatus.ON_HOLD.value,
            TicketStatus.REOPENED.value,
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

        response_due_soon = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.response_by.isnot(None),
            UnifiedTicket.first_response_at.is_(None),
            UnifiedTicket.response_by >= now,
            UnifiedTicket.response_by <= due_soon,
        ).scalar() or 0

        response_overdue = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.response_by.isnot(None),
            UnifiedTicket.first_response_at.is_(None),
            UnifiedTicket.response_by < now,
        ).scalar() or 0

        resolution_due_soon = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.resolution_by.isnot(None),
            UnifiedTicket.resolved_at.is_(None),
            UnifiedTicket.resolution_by >= now,
            UnifiedTicket.resolution_by <= due_soon,
        ).scalar() or 0

        resolution_overdue = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.resolution_by.isnot(None),
            UnifiedTicket.resolved_at.is_(None),
            UnifiedTicket.resolution_by < now,
        ).scalar() or 0

        return {
            "total_open": total_open,
            "urgent_tickets": urgent_tickets,
            "resolved_today": resolved_today,
            "resolved_week": resolved_week,
            "created_today": created_today,
            "status_distribution": status_distribution,
            "priority_distribution": priority_distribution,
            "response_due_soon": response_due_soon,
            "response_overdue": response_overdue,
            "resolution_due_soon": resolution_due_soon,
            "resolution_overdue": resolution_overdue,
        }

    def get_agent_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get agent workload statistics.

        Uses a single aggregate query instead of N+1 queries.
        After Agent → Party unification, agents are Party records
        with PartyRole(role="support_agent").
        """
        # Subquery for open ticket counts per party (agent)
        open_tickets_subq = (
            self.db.query(
                UnifiedTicket.assigned_to_party_id,
                func.count(UnifiedTicket.id).label("open_count")
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.status.notin_([TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value])
            )
            .group_by(UnifiedTicket.assigned_to_party_id)
            .subquery()
        )

        # Join parties (with support_agent role) with their ticket counts
        agents_with_counts = (
            self.db.query(
                Party.id,
                Party.name,
                Party.primary_email,
                func.coalesce(open_tickets_subq.c.open_count, 0).label("open_tickets")
            )
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            )
            .outerjoin(open_tickets_subq, Party.id == open_tickets_subq.c.assigned_to_party_id)
            .order_by(func.coalesce(open_tickets_subq.c.open_count, 0).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "name": row.name or row.primary_email or f"Agent {row.id}",
                "email": row.primary_email,
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
        assigned_to_party_id: Optional[int] = None,
        unassigned_only: bool = False,
        page: int = 1,
        per_page: int = 25,
        sort: str = "created_at",
        dir: str = "desc",
    ) -> Dict[str, Any]:
        """
        List tickets with filtering, search, and pagination.

        Args:
            assigned_to_party_id: Filter by assigned party (support agent).
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
            query = query.filter(UnifiedTicket.assigned_to_party_id.is_(None))
        elif assigned_to_party_id:
            query = query.filter(UnifiedTicket.assigned_to_party_id == assigned_to_party_id)

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
        missing = object()

        status = data.pop("status", missing)
        resolution = data.pop("resolution", missing)
        resolution_type = data.pop("resolution_type", missing)
        # Support both old (assigned_to_id) and new (assigned_to_party_id) field names
        assigned_to_party_id = data.pop("assigned_to_party_id", missing)
        if assigned_to_party_id is missing:
            assigned_to_party_id = data.pop("assigned_to_id", missing)
        assigned_team_id = data.pop("assigned_team_id", missing)
        assigned_team = data.pop("assigned_team", missing)

        if any(value is not missing for value in [assigned_to_party_id, assigned_team_id, assigned_team]):
            explicit_unassign = (
                assigned_to_party_id is not missing and assigned_to_party_id is None and
                assigned_team_id is not missing and assigned_team_id is None and
                (assigned_team is missing or not assigned_team)
            )
            if explicit_unassign:
                ticket.assigned_to_party_id = None
                ticket.assigned_team_id = None
                ticket.assigned_team = None
                ticket.assigned_at = None
            else:
                new_assigned_to_party_id = ticket.assigned_to_party_id if assigned_to_party_id is missing else assigned_to_party_id
                new_assigned_team_id = ticket.assigned_team_id if assigned_team_id is missing else assigned_team_id
                new_assigned_team = ticket.assigned_team if assigned_team is missing else assigned_team
                if new_assigned_to_party_id is None and new_assigned_team_id is None and not new_assigned_team:
                    ticket.assigned_to_party_id = None
                    ticket.assigned_team_id = None
                    ticket.assigned_team = None
                    ticket.assigned_at = None
                else:
                    if new_assigned_to_party_id is not None:
                        ticket.assigned_to_party_id = new_assigned_to_party_id
                    if new_assigned_team_id is not None:
                        ticket.assigned_team_id = new_assigned_team_id
                    ticket.assigned_team = new_assigned_team or None
                    ticket.assigned_at = datetime.utcnow()
                    if self._coerce_status(ticket.status) == TicketStatus.OPEN:
                        ticket.status = TicketStatus.IN_PROGRESS

        if resolution is not missing:
            ticket.resolution = resolution
        if resolution_type is not missing:
            ticket.resolution_type = resolution_type

        if status is not missing:
            status_enum = self._coerce_status(status)
            resolved_value = resolution if resolution is not missing else None
            resolved_type = resolution_type if resolution_type is not missing else None
            self._apply_status_change(ticket, status_enum, resolved_value, resolved_type)

        for key, value in data.items():
            if hasattr(ticket, key) and value is not None:
                setattr(ticket, key, value)

        ticket.updated_at = datetime.utcnow()
        if self.user_id:
            ticket.updated_by_id = self.user_id

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

        tickets = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id.in_(ids),
            UnifiedTicket.is_deleted == False,
        ).all()

        for ticket in tickets:
            self._apply_status_change(ticket, status)
            ticket.updated_at = datetime.utcnow()
            if self.user_id:
                ticket.updated_by_id = self.user_id

        return len(tickets)

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
            status = self._coerce_status(value)
            self._apply_status_change(ticket, status)

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

    def list_tickets_for_export(self, ids: Optional[List[int]] = None) -> List[UnifiedTicket]:
        """List tickets for CSV export."""
        query = self.db.query(UnifiedTicket)
        if ids:
            query = query.filter(UnifiedTicket.id.in_(ids))
        return query.order_by(UnifiedTicket.created_at.desc()).all()

    def list_open_tickets_for_party(
        self,
        party_id: int,
        limit: int = 10,
    ) -> List[UnifiedTicket]:
        """List open tickets assigned to a party (support agent)."""
        open_statuses = [
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.WAITING.value,
            TicketStatus.ON_HOLD.value,
            TicketStatus.REOPENED.value,
        ]
        return (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.assigned_to_party_id == party_id,
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.status.in_(open_statuses),
            )
            .order_by(UnifiedTicket.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_sla_breaches(
        self,
        start_dt: datetime,
        offset: int = 0,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """List tickets that breached SLA within a period."""
        breached_query = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.created_at >= start_dt,
            or_(
                UnifiedTicket.response_sla_breached.is_(True),
                UnifiedTicket.resolution_sla_breached.is_(True),
            ),
        )

        total = breached_query.count()
        tickets = (
            breached_query.order_by(UnifiedTicket.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        first_response_breaches = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.response_sla_breached == True,
            UnifiedTicket.created_at >= start_dt,
        ).scalar() or 0

        resolution_breaches = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.resolution_sla_breached == True,
            UnifiedTicket.created_at >= start_dt,
        ).scalar() or 0

        total_tickets = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.created_at >= start_dt
        ).scalar() or 1

        by_priority = self.db.query(
            UnifiedTicket.priority,
            func.count(UnifiedTicket.id).label("count"),
        ).filter(
            UnifiedTicket.created_at >= start_dt,
            or_(
                UnifiedTicket.response_sla_breached.is_(True),
                UnifiedTicket.resolution_sla_breached.is_(True),
            ),
        ).group_by(UnifiedTicket.priority).all()

        return {
            "items": tickets,
            "total": total,
            "first_response_breaches": first_response_breaches,
            "resolution_breaches": resolution_breaches,
            "total_tickets": total_tickets,
            "by_priority": by_priority,
        }

    # =========================================================================
    # AGENTS (Party with support_agent role)
    # =========================================================================

    def list_agents(
        self,
        active_only: bool = True,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List support agents (Party with support_agent role) with pagination."""
        query = (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                PartyRole.role == "support_agent",
                PartyRole.until.is_(None),
            )
        )

        if active_only:
            query = query.filter(PartyRole.status == "active")

        total = query.count()
        offset = (page - 1) * per_page
        items = query.order_by(Party.name).offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_agent(self, party_id: int) -> Optional[Party]:
        """Get a support agent (Party) by ID."""
        return (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                Party.id == party_id,
                PartyRole.role == "support_agent",
            )
            .first()
        )

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

    # =========================================================================
    # PARTY LOOKUP
    # =========================================================================

    def get_party(self, party_id: int) -> Optional[Party]:
        """Get a party by ID."""
        return self.db.query(Party).filter(Party.id == party_id).first()

    def search_parties(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Party]:
        """Search for parties by name, email, or phone."""
        if not query or len(query) < 2:
            return []

        search_filter = or_(
            Party.name.ilike(f"%{query}%"),
            Party.email.ilike(f"%{query}%"),
            Party.phone.ilike(f"%{query}%"),
        )
        return self.db.query(Party).filter(search_filter).limit(limit).all()

    # =========================================================================
    # COMMENTS AND ACTIVITY
    # =========================================================================

    def add_comment(
        self,
        ticket_id: int,
        body: str,
        is_public: bool = True,
        author_id: Optional[int] = None,
    ) -> HDTicketComment:
        """Add a comment to a ticket.

        Does NOT commit - caller must call db.commit().
        """
        # Verify ticket exists
        ticket = self.get_ticket(ticket_id)

        comment = HDTicketComment(
            ticket_id=ticket.hd_ticket_id,  # Link to HD ticket
            body=body,
            is_public=is_public,
            author_id=author_id or self.user_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(comment)
        self.db.flush()

        # Update ticket last activity
        ticket.updated_at = datetime.utcnow()
        if self.user_id:
            ticket.updated_by_id = self.user_id

        return comment

    def get_comments(
        self,
        ticket_id: int,
        public_only: bool = False,
    ) -> List[HDTicketComment]:
        """Get comments for a ticket."""
        ticket = self.get_ticket(ticket_id)

        query = self.db.query(HDTicketComment).filter(
            HDTicketComment.ticket_id == ticket.hd_ticket_id
        )

        if public_only:
            query = query.filter(HDTicketComment.is_public == True)

        return query.order_by(HDTicketComment.created_at.desc()).all()

    def get_activity_timeline(
        self,
        ticket_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get activity timeline for a ticket.

        Returns a combined list of comments and activity events.
        """
        ticket = self.get_ticket(ticket_id)

        # Get comments
        comments = self.db.query(HDTicketComment).filter(
            HDTicketComment.ticket_id == ticket.hd_ticket_id
        ).order_by(HDTicketComment.created_at.desc()).limit(limit).all()

        # Get activities
        activities = self.db.query(HDTicketActivity).filter(
            HDTicketActivity.ticket_id == ticket.hd_ticket_id
        ).order_by(HDTicketActivity.created_at.desc()).limit(limit).all()

        # Combine and sort
        timeline = []

        for comment in comments:
            timeline.append({
                "type": "comment",
                "id": comment.id,
                "body": comment.body,
                "is_public": comment.is_public,
                "author_id": comment.author_id,
                "created_at": comment.created_at,
            })

        for activity in activities:
            timeline.append({
                "type": "activity",
                "id": activity.id,
                "action": activity.action,
                "field": activity.field,
                "old_value": activity.old_value,
                "new_value": activity.new_value,
                "actor_id": activity.actor_id,
                "created_at": activity.created_at,
            })

        # Sort by created_at descending
        timeline.sort(key=lambda x: x["created_at"], reverse=True)
        return timeline[:limit]

    # =========================================================================
    # KNOWLEDGE BASE
    # =========================================================================

    def list_kb_articles(
        self,
        category_id: Optional[int] = None,
        published_only: bool = True,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List knowledge base articles with pagination."""
        query = self.db.query(KBArticle)

        if published_only:
            query = query.filter(KBArticle.is_published == True)

        if category_id:
            query = query.filter(KBArticle.category_id == category_id)

        if q:
            search_filter = or_(
                KBArticle.title.ilike(f"%{q}%"),
                KBArticle.content.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        total = query.count()
        offset = (page - 1) * per_page
        items = query.order_by(KBArticle.created_at.desc()).offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_kb_article(self, article_id: int) -> Optional[KBArticle]:
        """Get a KB article by ID."""
        return self.db.query(KBArticle).filter(KBArticle.id == article_id).first()

    def create_kb_article(self, data: Dict[str, Any]) -> KBArticle:
        """Create a new KB article.

        Does NOT commit - caller must call db.commit().
        """
        data.setdefault("created_at", datetime.utcnow())
        if self.user_id:
            data.setdefault("created_by_id", self.user_id)

        article = KBArticle(**data)
        self.db.add(article)
        self.db.flush()
        return article

    def update_kb_article(self, article_id: int, data: Dict[str, Any]) -> Optional[KBArticle]:
        """Update a KB article.

        Does NOT commit - caller must call db.commit().
        """
        article = self.get_kb_article(article_id)
        if not article:
            return None

        for key, value in data.items():
            if hasattr(article, key):
                setattr(article, key, value)

        article.updated_at = datetime.utcnow()
        if self.user_id:
            article.updated_by_id = self.user_id

        return article

    def delete_kb_article(self, article_id: int) -> bool:
        """Delete a KB article.

        Does NOT commit - caller must call db.commit().
        """
        article = self.get_kb_article(article_id)
        if not article:
            return False

        self.db.delete(article)
        self.db.flush()
        return True

    def get_kb_categories(self) -> List[KBCategory]:
        """Get all KB categories."""
        return self.db.query(KBCategory).order_by(KBCategory.name).all()

    def get_kb_stats(self) -> Dict[str, Any]:
        """Get KB statistics."""
        total_articles = self.db.query(func.count(KBArticle.id)).scalar() or 0
        published_articles = self.db.query(func.count(KBArticle.id)).filter(
            KBArticle.is_published == True
        ).scalar() or 0
        draft_articles = total_articles - published_articles
        total_categories = self.db.query(func.count(KBCategory.id)).scalar() or 0

        return {
            "total_articles": total_articles,
            "published_articles": published_articles,
            "draft_articles": draft_articles,
            "total_categories": total_categories,
        }

    # =========================================================================
    # CANNED RESPONSES CRUD
    # =========================================================================

    def get_canned_response(self, response_id: int) -> Optional[CannedResponse]:
        """Get a canned response by ID."""
        return self.db.query(CannedResponse).filter(CannedResponse.id == response_id).first()

    def create_canned_response(self, data: Dict[str, Any]) -> CannedResponse:
        """Create a new canned response.

        Does NOT commit - caller must call db.commit().
        """
        data.setdefault("created_at", datetime.utcnow())
        if self.user_id:
            data.setdefault("created_by_id", self.user_id)

        response = CannedResponse(**data)
        self.db.add(response)
        self.db.flush()
        return response

    def update_canned_response(
        self, response_id: int, data: Dict[str, Any]
    ) -> Optional[CannedResponse]:
        """Update a canned response.

        Does NOT commit - caller must call db.commit().
        """
        response = self.get_canned_response(response_id)
        if not response:
            return None

        for key, value in data.items():
            if hasattr(response, key):
                setattr(response, key, value)

        response.updated_at = datetime.utcnow()
        if self.user_id:
            response.updated_by_id = self.user_id

        return response

    def delete_canned_response(self, response_id: int) -> bool:
        """Delete a canned response.

        Does NOT commit - caller must call db.commit().
        """
        response = self.get_canned_response(response_id)
        if not response:
            return False

        self.db.delete(response)
        self.db.flush()
        return True

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Export tickets for CSV/Excel export.

        Returns a list of dicts suitable for export.
        """
        query = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.is_deleted == False
        )

        if status:
            query = query.filter(UnifiedTicket.status == status)
        if priority:
            query = query.filter(UnifiedTicket.priority == priority)
        if start_date:
            query = query.filter(UnifiedTicket.created_at >= start_date)
        if end_date:
            query = query.filter(UnifiedTicket.created_at <= end_date)

        tickets = query.order_by(UnifiedTicket.created_at.desc()).all()

        export_data = []
        for ticket in tickets:
            export_data.append({
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "status": ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
                "type": ticket.ticket_type,
                "channel": ticket.channel,
                "contact_name": ticket.contact_name,
                "contact_email": ticket.contact_email,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
                "resolution_time_seconds": ticket.resolution_time_seconds,
            })

        return export_data
