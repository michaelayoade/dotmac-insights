"""Queue service - business logic for support ticket queues.

This service handles custom queue/view management:
- CRUD operations for saved ticket queues
- Filter execution to retrieve matching tickets
- Queue ordering and visibility

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.support_settings import SupportQueue
from app.models.unified_ticket import UnifiedTicket

from .types import (
    QueueCreate,
    QueueUpdate,
)
from .errors import (
    DuplicateQueueError,
    QueueNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["QueueService"]


class QueueService:
    """Service for support queue management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        active_only: bool = True,
        include_private: bool = False,
        include_all: bool = False,
        company: Optional[str] = None,
    ) -> List[SupportQueue]:
        """List support queues.

        Args:
            active_only: Only return active queues.
            include_private: Include private queues (for current user).
            include_all: Skip visibility filtering (admin use).
            company: Filter by company.

        Returns:
            List of SupportQueue instances.
        """
        query = self.db.query(SupportQueue)

        if company:
            query = query.filter(
                or_(SupportQueue.company == company, SupportQueue.company.is_(None))
            )

        if active_only:
            query = query.filter(SupportQueue.is_active == True)

        # Visibility filter
        if not include_all:
            if include_private and self.principal:
                user_id = getattr(self.principal, "id", None)
                query = query.filter(
                    or_(
                        SupportQueue.is_public == True,
                        SupportQueue.owner_id == user_id,
                    )
                )
            else:
                query = query.filter(SupportQueue.is_public == True)

        return query.order_by(SupportQueue.display_order.asc(), SupportQueue.name.asc()).all()

    def get(self, queue_id: int) -> SupportQueue:
        """Get a queue by ID.

        Args:
            queue_id: The queue ID.

        Returns:
            SupportQueue instance.

        Raises:
            QueueNotFoundError: If not found.
        """
        queue = (
            self.db.query(SupportQueue)
            .filter(SupportQueue.id == queue_id)
            .first()
        )
        if not queue:
            raise QueueNotFoundError(queue_id)
        return queue

    def get_by_name(self, name: str, company: Optional[str] = None) -> Optional[SupportQueue]:
        """Get a queue by name.

        Args:
            name: The queue name.
            company: Optional company filter.

        Returns:
            SupportQueue instance or None.
        """
        query = self.db.query(SupportQueue).filter(SupportQueue.name == name)
        if company:
            query = query.filter(
                or_(SupportQueue.company == company, SupportQueue.company.is_(None))
            )
        return query.first()

    def get_system_queues(self, company: Optional[str] = None) -> List[SupportQueue]:
        """Get system-defined queues.

        Args:
            company: Optional company filter.

        Returns:
            List of system SupportQueue instances.
        """
        query = self.db.query(SupportQueue).filter(
            SupportQueue.queue_type == "SYSTEM",
            SupportQueue.is_active == True,
        )
        if company:
            query = query.filter(
                or_(SupportQueue.company == company, SupportQueue.company.is_(None))
            )
        return query.order_by(SupportQueue.display_order.asc()).all()

    def get_user_queues(self, user_id: int) -> List[SupportQueue]:
        """Get queues owned by a specific user.

        Args:
            user_id: The owner user ID.

        Returns:
            List of SupportQueue instances.
        """
        return (
            self.db.query(SupportQueue)
            .filter(
                SupportQueue.owner_id == user_id,
                SupportQueue.is_active == True,
            )
            .order_by(SupportQueue.display_order.asc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: QueueCreate, company: Optional[str] = None) -> SupportQueue:
        """Create a new queue.

        Args:
            data: Queue creation data.
            company: Optional company scope.

        Returns:
            Created SupportQueue instance.

        Raises:
            DuplicateQueueError: If name already exists for company.
        """
        # Check for duplicate name
        existing = self.get_by_name(data.name, company)
        if existing:
            raise DuplicateQueueError(data.name)

        queue = SupportQueue(
            company=company,
            name=data.name,
            description=data.description,
            queue_type=data.queue_type.upper(),
            filters=data.filters,
            sort_by=data.sort_by,
            sort_direction=data.sort_direction.upper(),
            is_public=data.is_public,
            owner_id=data.owner_id,
            icon=data.icon,
            color=data.color,
            is_active=True,
        )

        # If no owner specified and creating private queue, set current user
        if not data.is_public and not data.owner_id and self.principal:
            queue.owner_id = getattr(self.principal, "id", None)

        self.db.add(queue)
        self.db.flush()
        return queue

    def update(self, queue_id: int, data: QueueUpdate) -> SupportQueue:
        """Update a queue.

        Args:
            queue_id: The queue ID.
            data: Update data.

        Returns:
            Updated SupportQueue instance.

        Raises:
            QueueNotFoundError: If not found.
            DuplicateQueueError: If new name conflicts.
        """
        queue = self.get(queue_id)

        if data.name is not None and data.name != queue.name:
            existing = self.get_by_name(data.name, queue.company)
            if existing:
                raise DuplicateQueueError(data.name)
            queue.name = data.name

        if data.description is not None:
            queue.description = data.description

        if data.filters is not None:
            queue.filters = data.filters

        if data.sort_by is not None:
            queue.sort_by = data.sort_by

        if data.sort_direction is not None:
            queue.sort_direction = data.sort_direction.upper()

        if data.is_public is not None:
            queue.is_public = data.is_public

        if data.icon is not None:
            queue.icon = data.icon

        if data.color is not None:
            queue.color = data.color

        if data.display_order is not None:
            queue.display_order = data.display_order

        if data.is_active is not None:
            queue.is_active = data.is_active

        self.db.flush()
        return queue

    def delete(self, queue_id: int) -> bool:
        """Delete a queue.

        Args:
            queue_id: The queue ID.

        Returns:
            True if deleted.

        Raises:
            QueueNotFoundError: If not found.
        """
        queue = self.get(queue_id)
        self.db.delete(queue)
        self.db.flush()
        return True

    def reorder(self, queue_ids: List[int]) -> List[SupportQueue]:
        """Reorder queues by setting display_order.

        Args:
            queue_ids: List of queue IDs in desired order.

        Returns:
            List of updated SupportQueue instances.
        """
        queues = []
        for order, queue_id in enumerate(queue_ids):
            try:
                queue = self.get(queue_id)
                queue.display_order = order
                queues.append(queue)
            except QueueNotFoundError:
                continue

        self.db.flush()
        return queues

    # -------------------------------------------------------------------------
    # Filter Execution
    # -------------------------------------------------------------------------

    def get_ticket_count(self, queue_id: int) -> int:
        """Get the count of tickets matching a queue's filters.

        Args:
            queue_id: The queue ID.

        Returns:
            Count of matching tickets.
        """
        queue = self.get(queue_id)
        query = self._build_ticket_query(queue.filters)
        return query.count()

    def get_tickets(
        self,
        queue_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UnifiedTicket]:
        """Get tickets matching a queue's filters.

        Args:
            queue_id: The queue ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching UnifiedTicket instances.
        """
        queue = self.get(queue_id)
        query = self._build_ticket_query(queue.filters)

        # Apply sorting
        sort_column = getattr(UnifiedTicket, queue.sort_by, UnifiedTicket.created_at)
        if queue.sort_direction == "DESC":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query.offset(offset).limit(limit).all()

    def _build_ticket_query(self, filters: List[Dict[str, Any]]):
        """Build a SQLAlchemy query from filter conditions.

        Filter format:
        [
            {"field": "status", "operator": "in", "value": ["open", "pending"]},
            {"field": "priority", "operator": "equals", "value": "high"},
            {"field": "assigned_to_party_id", "operator": "is_null"},
        ]

        Args:
            filters: List of filter condition dicts.

        Returns:
            SQLAlchemy query object.
        """
        query = self.db.query(UnifiedTicket)
        conditions = []

        for f in filters:
            field_name = f.get("field")
            operator = f.get("operator", "equals")
            value = f.get("value")

            # Get the column from the model
            if not hasattr(UnifiedTicket, field_name):
                continue
            column = getattr(UnifiedTicket, field_name)

            # Build condition based on operator
            if operator == "equals":
                conditions.append(column == value)
            elif operator == "not_equals":
                conditions.append(column != value)
            elif operator == "in":
                if isinstance(value, list):
                    conditions.append(column.in_(value))
            elif operator == "not_in":
                if isinstance(value, list):
                    conditions.append(~column.in_(value))
            elif operator == "is_null":
                conditions.append(column.is_(None))
            elif operator == "is_not_null":
                conditions.append(column.isnot(None))
            elif operator == "contains":
                conditions.append(column.ilike(f"%{value}%"))
            elif operator == "starts_with":
                conditions.append(column.ilike(f"{value}%"))
            elif operator == "ends_with":
                conditions.append(column.ilike(f"%{value}"))
            elif operator == "greater_than":
                conditions.append(column > value)
            elif operator == "less_than":
                conditions.append(column < value)
            elif operator == "greater_or_equal":
                conditions.append(column >= value)
            elif operator == "less_or_equal":
                conditions.append(column <= value)

        if conditions:
            query = query.filter(and_(*conditions))

        return query

    def execute_filters(
        self,
        filters: List[Dict[str, Any]],
        sort_by: str = "created_at",
        sort_direction: str = "DESC",
        limit: int = 50,
        offset: int = 0,
    ) -> List[UnifiedTicket]:
        """Execute arbitrary filters without saving as a queue.

        Args:
            filters: List of filter condition dicts.
            sort_by: Field to sort by.
            sort_direction: ASC or DESC.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching UnifiedTicket instances.
        """
        query = self._build_ticket_query(filters)

        # Apply sorting
        sort_column = getattr(UnifiedTicket, sort_by, UnifiedTicket.created_at)
        if sort_direction.upper() == "DESC":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query.offset(offset).limit(limit).all()

    # -------------------------------------------------------------------------
    # System Queues
    # -------------------------------------------------------------------------

    def ensure_system_queues(self, company: Optional[str] = None) -> List[SupportQueue]:
        """Ensure default system queues exist.

        Creates standard queues like 'All Tickets', 'Unassigned', 'My Tickets', etc.

        Args:
            company: Optional company scope.

        Returns:
            List of system SupportQueue instances.
        """
        system_queues = [
            {
                "name": "All Tickets",
                "description": "All tickets in the system",
                "filters": [],
                "icon": "inbox",
                "display_order": 1,
            },
            {
                "name": "Unassigned",
                "description": "Tickets without an assigned agent",
                "filters": [{"field": "assigned_to_party_id", "operator": "is_null"}],
                "icon": "user-x",
                "display_order": 2,
            },
            {
                "name": "Open",
                "description": "Open tickets",
                "filters": [{"field": "status", "operator": "equals", "value": "open"}],
                "icon": "folder-open",
                "display_order": 3,
            },
            {
                "name": "Pending",
                "description": "Tickets awaiting response",
                "filters": [{"field": "status", "operator": "equals", "value": "pending"}],
                "icon": "clock",
                "display_order": 4,
            },
            {
                "name": "Resolved",
                "description": "Resolved tickets",
                "filters": [{"field": "status", "operator": "equals", "value": "resolved"}],
                "icon": "check-circle",
                "display_order": 5,
            },
            {
                "name": "High Priority",
                "description": "High and urgent priority tickets",
                "filters": [{"field": "priority", "operator": "in", "value": ["high", "urgent"]}],
                "icon": "alert-triangle",
                "display_order": 6,
            },
            {
                "name": "Overdue",
                "description": "Tickets past their SLA due date",
                "filters": [{"field": "is_overdue", "operator": "equals", "value": True}],
                "icon": "alert-circle",
                "display_order": 7,
            },
        ]

        created = []
        for q_data in system_queues:
            existing = self.get_by_name(q_data["name"], company)
            if existing:
                created.append(existing)
                continue

            queue = SupportQueue(
                company=company,
                name=q_data["name"],
                description=q_data["description"],
                queue_type="SYSTEM",
                filters=q_data["filters"],
                sort_by="created_at",
                sort_direction="DESC",
                is_public=True,
                icon=q_data["icon"],
                display_order=q_data["display_order"],
                is_active=True,
            )
            self.db.add(queue)
            created.append(queue)

        self.db.flush()
        return created

    def get_queue_counts(
        self,
        queue_ids: Optional[List[int]] = None,
        company: Optional[str] = None,
    ) -> Dict[int, int]:
        """Get ticket counts for multiple queues.

        Args:
            queue_ids: List of queue IDs (or None for all).
            company: Optional company filter.

        Returns:
            Dict mapping queue_id to ticket count.
        """
        if queue_ids:
            queues = self.db.query(SupportQueue).filter(SupportQueue.id.in_(queue_ids)).all()
        else:
            queues = self.list(active_only=True, include_private=True, company=company)

        counts = {}
        for queue in queues:
            query = self._build_ticket_query(queue.filters)
            counts[queue.id] = query.count()

        return counts
