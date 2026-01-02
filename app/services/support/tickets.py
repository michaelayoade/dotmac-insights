"""Ticket service - business logic for help desk tickets.

This service encapsulates ticket-related business logic:
- Core CRUD operations (Segment 1)
- Comments and activities (Segment 2)
- Tags, watchers, assignment (Segment 3)
- Dependencies, communications, merge/split (Segment 4)

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.ticket import (
    HDTicketActivity,
    HDTicketComment,
    HDTicketDependency,
    Ticket,
    TicketCommunication,
    TicketPriority,
    TicketStatus,
)
from app.models.support_tags import TicketCustomField, TicketTag
from app.models.auth import User
from app.models.agent import Agent, Team, TeamMember
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .ticket_types import (
    ActivityData,
    AssignmentData,
    BulkResult,
    BulkUpdateData,
    CommentData,
    CommunicationData,
    DependencyData,
    MergeData,
    SLAUpdateData,
    SplitData,
    TicketCreateData,
    TicketFilters,
    TicketUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TicketService"]


def _generate_ticket_number() -> str:
    """Generate a unique local ticket number."""
    import uuid
    return f"TKT-{uuid.uuid4().hex[:8].upper()}"


class TicketService:
    """Service for ticket business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def validate_tags(self, tags: Optional[List[str]]) -> List[str]:
        """Validate that tags exist and are active.

        Args:
            tags: List of tag names.

        Returns:
            Deduplicated list of valid tag names.

        Raises:
            ValidationError: If any tag is unknown or inactive.
        """
        if not tags:
            return []

        clean = [t.strip() for t in tags if t and t.strip()]
        clean = list(dict.fromkeys(clean))  # dedupe preserving order

        if not clean:
            return []

        existing = (
            self.db.query(TicketTag)
            .filter(TicketTag.name.in_(clean), TicketTag.is_active == True)
            .all()
        )
        found = {t.name for t in existing}
        missing = [t for t in clean if t not in found]

        if missing:
            raise ValidationError(f"Unknown or inactive tags: {missing}")

        return clean

    def validate_watchers(self, watcher_ids: Optional[List[int]]) -> List[int]:
        """Validate that watcher user IDs exist.

        Args:
            watcher_ids: List of user IDs.

        Returns:
            Deduplicated list of valid user IDs.

        Raises:
            ValidationError: If any user ID is unknown.
        """
        if not watcher_ids:
            return []

        unique_ids = list(dict.fromkeys([wid for wid in watcher_ids if wid is not None]))
        if not unique_ids:
            return []

        rows = self.db.query(User.id).filter(User.id.in_(unique_ids)).all()
        found_ids = {row.id for row in rows}
        missing = [wid for wid in unique_ids if wid not in found_ids]

        if missing:
            raise ValidationError(f"Unknown watcher user_ids: {missing}")

        return unique_ids

    def validate_custom_fields(self, custom_fields: Optional[dict]) -> dict:
        """Validate custom fields against definitions.

        Args:
            custom_fields: Dict of field_key -> value.

        Returns:
            Sanitized dict of valid custom fields.

        Raises:
            ValidationError: If any field is unknown, inactive, or has invalid value.
        """
        if custom_fields is None:
            return {}
        if not isinstance(custom_fields, dict):
            raise ValidationError("custom_fields must be an object")

        keys = list(custom_fields.keys())
        if not keys:
            return {}

        defs = (
            self.db.query(TicketCustomField)
            .filter(
                TicketCustomField.field_key.in_(keys),
                TicketCustomField.is_active == True,
            )
            .all()
        )
        def_map = {f.field_key: f for f in defs}

        if len(def_map) != len(keys):
            missing = [k for k in keys if k not in def_map]
            raise ValidationError(f"Unknown or inactive custom_fields: {missing}")

        # Basic validation - just ensure keys exist
        # Full type validation is done in routes for now
        return {k: v for k, v in custom_fields.items() if k in def_map}

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_tickets(
        self,
        filters: Optional[TicketFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Ticket]:
        """List tickets with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing tickets and total count.
        """
        if filters is None:
            filters = TicketFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Ticket).filter(Ticket.is_deleted == False)
        query = scoped_query(query, self.principal)

        if filters.status:
            query = query.filter(Ticket.status == filters.status)

        if filters.priority:
            query = query.filter(Ticket.priority == filters.priority)

        if filters.customer_account_id:
            query = query.filter(Ticket.customer_account_id == filters.customer_account_id)

        if filters.party_id:
            query = query.filter(Ticket.party_id == filters.party_id)

        if filters.ticket_type:
            query = query.filter(Ticket.ticket_type == filters.ticket_type)

        if filters.assigned_to:
            query = query.filter(Ticket.assigned_to.ilike(f"%{filters.assigned_to}%"))

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Ticket.subject.ilike(search_term),
                    Ticket.ticket_number.ilike(search_term),
                    Ticket.customer_name.ilike(search_term),
                )
            )

        if filters.overdue_only:
            query = query.filter(
                Ticket.resolution_by.isnot(None),
                Ticket.resolution_by < func.current_timestamp(),
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD]),
            )

        if filters.unassigned_only:
            query = query.filter(
                Ticket.assigned_to.is_(None),
                Ticket.assigned_employee_id.is_(None),
            )

        if filters.start_date:
            query = query.filter(Ticket.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(Ticket.created_at <= filters.end_date)

        # Default ordering
        query = query.order_by(Ticket.created_at.desc())

        return paginate(query, pagination)

    def get_ticket(self, ticket_id: int, include_children: bool = False) -> Ticket:
        """Get a ticket by ID.

        Args:
            ticket_id: The ticket ID.
            include_children: If True, eager load comments, activities, etc.

        Returns:
            The Ticket object.

        Raises:
            NotFoundError: If ticket not found or deleted.
        """
        query = self.db.query(Ticket)

        if include_children:
            query = query.options(
                joinedload(Ticket.customer),
                selectinload(Ticket.comments),
                selectinload(Ticket.activities),
                selectinload(Ticket.communications),
                selectinload(Ticket.depends_on),
                selectinload(Ticket.expenses),
            )

        ticket = query.filter(
            Ticket.id == ticket_id,
            Ticket.is_deleted == False,
        ).first()

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        return ticket

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_ticket(self, data: TicketCreateData) -> Ticket:
        """Create a new ticket.

        Args:
            data: Ticket creation data.

        Returns:
            The created Ticket (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        valid_tags = self.validate_tags(data.tags)
        valid_watchers = self.validate_watchers(data.watchers)
        valid_custom_fields = self.validate_custom_fields(data.custom_fields)

        ticket = Ticket(
            ticket_number=_generate_ticket_number(),
            subject=data.subject,
            description=data.description,
            status=data.status,
            priority=data.priority,
            ticket_type=data.ticket_type,
            issue_type=data.issue_type,
            customer_account_id=data.customer_account_id,
            party_id=data.party_id,
            project_id=data.project_id,
            assigned_to=data.assigned_to,
            assigned_employee_id=data.assigned_employee_id,
            resolution_by=data.resolution_by,
            response_by=data.response_by,
            resolution_team=data.resolution_team,
            customer_email=data.customer_email,
            customer_phone=data.customer_phone,
            customer_name=data.customer_name,
            region=data.region,
            base_station=data.base_station,
            tags=valid_tags,
            watchers=valid_watchers,
            custom_fields=valid_custom_fields,
            parent_ticket_id=data.parent_ticket_id,
            origin_system="local",
            write_back_status="pending",
            created_by_id=self.principal.id if self.principal else None,
            updated_by_id=self.principal.id if self.principal else None,
            opening_date=datetime.now(timezone.utc),
        )

        self.db.add(ticket)
        self.db.flush()  # Get ticket.id

        # Update tag usage counts
        if valid_tags:
            for tag in (
                self.db.query(TicketTag)
                .filter(TicketTag.name.in_(valid_tags), TicketTag.is_active == True)
                .all()
            ):
                tag.usage_count = (tag.usage_count or 0) + 1

        return ticket

    def update_ticket(self, ticket_id: int, data: TicketUpdateData) -> Ticket:
        """Update an existing ticket.

        Args:
            ticket_id: The ticket ID.
            data: Fields to update.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If validation fails.
        """
        ticket = self.get_ticket(ticket_id)

        # Handle tags with usage count updates
        if data.tags is not None:
            new_tags = self.validate_tags(data.tags)
            current_tags = ticket.tags or []
            added = [t for t in new_tags if t not in current_tags]
            removed = [t for t in current_tags if t not in new_tags]

            if added:
                for tag in (
                    self.db.query(TicketTag)
                    .filter(TicketTag.name.in_(added), TicketTag.is_active == True)
                    .all()
                ):
                    tag.usage_count = (tag.usage_count or 0) + 1

            if removed:
                for tag in self.db.query(TicketTag).filter(TicketTag.name.in_(removed)).all():
                    if tag.usage_count and tag.usage_count > 0:
                        tag.usage_count = tag.usage_count - 1

            ticket.tags = new_tags

        if data.watchers is not None:
            ticket.watchers = self.validate_watchers(data.watchers)

        if data.custom_fields is not None:
            ticket.custom_fields = self.validate_custom_fields(data.custom_fields)

        # Update simple fields
        simple_fields = [
            "subject", "description", "ticket_type", "issue_type", "customer_account_id", "party_id",
            "project_id", "assigned_to", "assigned_employee_id", "resolution_by",
            "response_by", "resolution_team", "resolution", "resolution_details",
            "resolution_date", "customer_email", "customer_phone",
            "customer_name", "region", "base_station", "parent_ticket_id", "merged_into_id",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(ticket, field_name, value)

        # Handle status with auto resolution_date
        if data.status is not None:
            ticket.status = data.status
            if data.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                if ticket.resolution_date is None:
                    ticket.resolution_date = datetime.now(timezone.utc)

        if data.priority is not None:
            ticket.priority = data.priority

        ticket.updated_by_id = self.principal.id if self.principal else None
        ticket.updated_at = datetime.now(timezone.utc)

        return ticket

    def delete_ticket(self, ticket_id: int) -> None:
        """Soft delete a ticket.

        Args:
            ticket_id: The ticket ID.

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        ticket.is_deleted = True
        ticket.deleted_at = datetime.now(timezone.utc)
        ticket.deleted_by_id = self.principal.id if self.principal else None
        ticket.updated_at = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Comments (Segment 2)
    # -------------------------------------------------------------------------

    def add_comment(self, ticket_id: int, data: CommentData) -> HDTicketComment:
        """Add a comment to a ticket.

        Args:
            ticket_id: The ticket ID.
            data: Comment data.

        Returns:
            The created HDTicketComment (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        # Get next idx
        max_idx = (
            self.db.query(func.max(HDTicketComment.idx))
            .filter(HDTicketComment.ticket_id == ticket_id)
            .scalar()
        )
        next_idx = (max_idx or 0) + 1

        comment = HDTicketComment(
            ticket_id=ticket_id,
            comment=data.comment,
            comment_type=data.comment_type,
            commented_by=data.commented_by,
            commented_by_name=data.commented_by_name,
            is_public=data.is_public,
            comment_date=data.comment_date or datetime.now(timezone.utc),
            idx=next_idx,
        )

        self.db.add(comment)
        self.db.flush()

        return comment

    def update_comment(
        self, ticket_id: int, comment_id: int, data: CommentData
    ) -> HDTicketComment:
        """Update a ticket comment.

        Args:
            ticket_id: The ticket ID.
            comment_id: The comment ID.
            data: Fields to update.

        Returns:
            The updated HDTicketComment.

        Raises:
            NotFoundError: If ticket or comment not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        comment = (
            self.db.query(HDTicketComment)
            .filter(
                HDTicketComment.id == comment_id,
                HDTicketComment.ticket_id == ticket_id,
            )
            .first()
        )
        if not comment:
            raise NotFoundError(f"Comment {comment_id} not found")

        if data.comment:
            comment.comment = data.comment
        if data.comment_type is not None:
            comment.comment_type = data.comment_type
        if data.commented_by is not None:
            comment.commented_by = data.commented_by
        if data.commented_by_name is not None:
            comment.commented_by_name = data.commented_by_name
        if data.is_public is not None:
            comment.is_public = data.is_public
        if data.comment_date is not None:
            comment.comment_date = data.comment_date

        return comment

    def delete_comment(self, ticket_id: int, comment_id: int) -> None:
        """Delete a ticket comment.

        Args:
            ticket_id: The ticket ID.
            comment_id: The comment ID.

        Raises:
            NotFoundError: If ticket or comment not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        comment = (
            self.db.query(HDTicketComment)
            .filter(
                HDTicketComment.id == comment_id,
                HDTicketComment.ticket_id == ticket_id,
            )
            .first()
        )
        if not comment:
            raise NotFoundError(f"Comment {comment_id} not found")

        self.db.delete(comment)

    # -------------------------------------------------------------------------
    # Activities (Segment 2)
    # -------------------------------------------------------------------------

    def add_activity(self, ticket_id: int, data: ActivityData) -> HDTicketActivity:
        """Add an activity to a ticket.

        Args:
            ticket_id: The ticket ID.
            data: Activity data.

        Returns:
            The created HDTicketActivity (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        # Get next idx
        max_idx = (
            self.db.query(func.max(HDTicketActivity.idx))
            .filter(HDTicketActivity.ticket_id == ticket_id)
            .scalar()
        )
        next_idx = (max_idx or 0) + 1

        activity = HDTicketActivity(
            ticket_id=ticket_id,
            activity=data.activity,
            activity_type=data.activity_type,
            owner=data.owner,
            from_status=data.from_status,
            to_status=data.to_status,
            activity_date=data.activity_date or datetime.now(timezone.utc),
            idx=next_idx,
        )

        self.db.add(activity)
        self.db.flush()

        return activity

    def update_activity(
        self, ticket_id: int, activity_id: int, data: ActivityData
    ) -> HDTicketActivity:
        """Update a ticket activity.

        Args:
            ticket_id: The ticket ID.
            activity_id: The activity ID.
            data: Fields to update.

        Returns:
            The updated HDTicketActivity.

        Raises:
            NotFoundError: If ticket or activity not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        activity = (
            self.db.query(HDTicketActivity)
            .filter(
                HDTicketActivity.id == activity_id,
                HDTicketActivity.ticket_id == ticket_id,
            )
            .first()
        )
        if not activity:
            raise NotFoundError(f"Activity {activity_id} not found")

        if data.activity:
            activity.activity = data.activity
        if data.activity_type is not None:
            activity.activity_type = data.activity_type
        if data.owner is not None:
            activity.owner = data.owner
        if data.from_status is not None:
            activity.from_status = data.from_status
        if data.to_status is not None:
            activity.to_status = data.to_status
        if data.activity_date is not None:
            activity.activity_date = data.activity_date

        return activity

    def delete_activity(self, ticket_id: int, activity_id: int) -> None:
        """Delete a ticket activity.

        Args:
            ticket_id: The ticket ID.
            activity_id: The activity ID.

        Raises:
            NotFoundError: If ticket or activity not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        activity = (
            self.db.query(HDTicketActivity)
            .filter(
                HDTicketActivity.id == activity_id,
                HDTicketActivity.ticket_id == ticket_id,
            )
            .first()
        )
        if not activity:
            raise NotFoundError(f"Activity {activity_id} not found")

        self.db.delete(activity)

    # -------------------------------------------------------------------------
    # Tags Management (Segment 3)
    # -------------------------------------------------------------------------

    def add_tags(self, ticket_id: int, tags: List[str]) -> Ticket:
        """Add tags to a ticket.

        Args:
            ticket_id: The ticket ID.
            tags: List of tag names to add.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If any tag is unknown or inactive.
        """
        ticket = self.get_ticket(ticket_id)
        validated_tags = self.validate_tags(tags)

        current_tags = ticket.tags or []
        new_tags = list(dict.fromkeys(current_tags + validated_tags))

        # Update usage counts for newly added tags
        added_tags = [t for t in validated_tags if t not in current_tags]
        if added_tags:
            for tag in (
                self.db.query(TicketTag)
                .filter(TicketTag.name.in_(added_tags), TicketTag.is_active == True)
                .all()
            ):
                tag.usage_count = (tag.usage_count or 0) + 1

        ticket.tags = new_tags
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    def remove_tag(self, ticket_id: int, tag_name: str) -> Ticket:
        """Remove a tag from a ticket.

        Args:
            ticket_id: The ticket ID.
            tag_name: The tag name to remove.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found or tag not on ticket.
        """
        ticket = self.get_ticket(ticket_id)

        current_tags = ticket.tags or []
        if tag_name not in current_tags:
            raise NotFoundError(f"Tag '{tag_name}' not found on this ticket")

        # Update usage count
        tag = self.db.query(TicketTag).filter(TicketTag.name == tag_name).first()
        if tag and tag.usage_count and tag.usage_count > 0:
            tag.usage_count = tag.usage_count - 1

        ticket.tags = [t for t in current_tags if t != tag_name]
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    # -------------------------------------------------------------------------
    # Watchers Management (Segment 3)
    # -------------------------------------------------------------------------

    def add_watchers(self, ticket_id: int, user_ids: List[int]) -> Ticket:
        """Add watchers to a ticket.

        Args:
            ticket_id: The ticket ID.
            user_ids: List of user IDs to add as watchers.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If any user ID is unknown.
        """
        ticket = self.get_ticket(ticket_id)
        validated_watchers = self.validate_watchers(user_ids)

        current_watchers = ticket.watchers or []
        new_watchers = list(dict.fromkeys(current_watchers + validated_watchers))

        ticket.watchers = new_watchers
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    def remove_watcher(self, ticket_id: int, user_id: int) -> Ticket:
        """Remove a watcher from a ticket.

        Args:
            ticket_id: The ticket ID.
            user_id: The user ID to remove.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found or watcher not on ticket.
        """
        ticket = self.get_ticket(ticket_id)

        current_watchers = ticket.watchers or []
        if user_id not in current_watchers:
            raise NotFoundError(f"Watcher {user_id} not found on this ticket")

        ticket.watchers = [w for w in current_watchers if w != user_id]
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    # -------------------------------------------------------------------------
    # Assignment & SLA (Segment 3)
    # -------------------------------------------------------------------------

    def assign_ticket(self, ticket_id: int, data: AssignmentData) -> Ticket:
        """Assign a ticket to an agent or team.

        Args:
            ticket_id: The ticket ID.
            data: Assignment data.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If team/member/agent ID is invalid.
        """
        ticket = self.get_ticket(ticket_id)

        team = None
        if data.team_id:
            team = self.db.query(Team).filter(Team.id == data.team_id).first()
            if not team:
                raise ValidationError(f"Team {data.team_id} does not exist")

        member = None
        if data.member_id:
            member = self.db.query(TeamMember).filter(TeamMember.id == data.member_id).first()
            if not member:
                raise ValidationError(f"Team member {data.member_id} does not exist")
            if data.team_id and member.team_id != data.team_id:
                raise ValidationError("Member does not belong to specified team")

        agent = None
        if data.agent_id:
            agent = self.db.query(Agent).filter(Agent.id == data.agent_id).first()
            if not agent:
                raise ValidationError(f"Agent {data.agent_id} does not exist")

        # Resolve agent from member if not explicitly provided
        if member and member.agent_id and not agent:
            agent = self.db.query(Agent).filter(Agent.id == member.agent_id).first()

        # Set employee ID from agent or explicit value
        if agent and agent.employee_id:
            ticket.assigned_employee_id = agent.employee_id
        elif data.employee_id:
            ticket.assigned_employee_id = data.employee_id

        # Set assigned_to from agent or explicit value
        if agent:
            ticket.assigned_to = data.assigned_to or agent.display_name or agent.email
        elif data.assigned_to:
            ticket.assigned_to = data.assigned_to

        # Set resolution team from team
        if team:
            ticket.resolution_team = team.name

        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    def update_sla(self, ticket_id: int, data: SLAUpdateData) -> Ticket:
        """Update ticket SLA dates.

        Args:
            ticket_id: The ticket ID.
            data: SLA update data.

        Returns:
            The updated Ticket (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        if data.response_by is not None:
            ticket.response_by = data.response_by
        if data.resolution_by is not None:
            ticket.resolution_by = data.resolution_by

        if data.reason:
            existing = ticket.resolution_details or ""
            note = f"[SLA override] {data.reason}"
            ticket.resolution_details = (existing + "\n" + note).strip() if existing else note

        ticket.updated_at = datetime.now(timezone.utc)
        ticket.updated_by_id = self.principal.id if self.principal else None

        return ticket

    # -------------------------------------------------------------------------
    # Dependencies (Segment 4)
    # -------------------------------------------------------------------------

    def add_dependency(self, ticket_id: int, data: DependencyData) -> HDTicketDependency:
        """Add a blocking/depends-on relationship to a ticket.

        Args:
            ticket_id: The ticket ID.
            data: Dependency data.

        Returns:
            The created HDTicketDependency (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If depends_on_ticket_id is invalid.
        """
        ticket = self.get_ticket(ticket_id)

        if data.depends_on_ticket_id:
            target = (
                self.db.query(Ticket.id)
                .filter(Ticket.id == data.depends_on_ticket_id, Ticket.is_deleted == False)
                .first()
            )
            if not target:
                raise ValidationError(f"depends_on_ticket_id {data.depends_on_ticket_id} does not exist")

        # Get next idx
        max_idx = (
            self.db.query(func.max(HDTicketDependency.idx))
            .filter(HDTicketDependency.ticket_id == ticket_id)
            .scalar()
        )
        next_idx = (max_idx or 0) + 1

        dependency = HDTicketDependency(
            ticket_id=ticket.id,
            depends_on_ticket_id=data.depends_on_ticket_id,
            depends_on_erpnext_id=data.depends_on_erpnext_id,
            depends_on_subject=data.depends_on_subject,
            depends_on_status=data.depends_on_status,
            idx=next_idx,
        )
        self.db.add(dependency)
        self.db.flush()

        return dependency

    def update_dependency(
        self, ticket_id: int, dependency_id: int, data: DependencyData
    ) -> HDTicketDependency:
        """Update a ticket dependency.

        Args:
            ticket_id: The ticket ID.
            dependency_id: The dependency ID.
            data: Fields to update.

        Returns:
            The updated HDTicketDependency.

        Raises:
            NotFoundError: If ticket or dependency not found.
            ValidationError: If depends_on_ticket_id is invalid.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        dependency = (
            self.db.query(HDTicketDependency)
            .filter(
                HDTicketDependency.id == dependency_id,
                HDTicketDependency.ticket_id == ticket_id,
            )
            .first()
        )
        if not dependency:
            raise NotFoundError(f"Dependency {dependency_id} not found")

        if data.depends_on_ticket_id is not None:
            if data.depends_on_ticket_id:
                target = (
                    self.db.query(Ticket.id)
                    .filter(Ticket.id == data.depends_on_ticket_id, Ticket.is_deleted == False)
                    .first()
                )
                if not target:
                    raise ValidationError(f"depends_on_ticket_id {data.depends_on_ticket_id} does not exist")
            dependency.depends_on_ticket_id = data.depends_on_ticket_id

        if data.depends_on_erpnext_id is not None:
            dependency.depends_on_erpnext_id = data.depends_on_erpnext_id
        if data.depends_on_subject is not None:
            dependency.depends_on_subject = data.depends_on_subject
        if data.depends_on_status is not None:
            dependency.depends_on_status = data.depends_on_status

        return dependency

    def delete_dependency(self, ticket_id: int, dependency_id: int) -> None:
        """Delete a ticket dependency.

        Args:
            ticket_id: The ticket ID.
            dependency_id: The dependency ID.

        Raises:
            NotFoundError: If ticket or dependency not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        dependency = (
            self.db.query(HDTicketDependency)
            .filter(
                HDTicketDependency.id == dependency_id,
                HDTicketDependency.ticket_id == ticket_id,
            )
            .first()
        )
        if not dependency:
            raise NotFoundError(f"Dependency {dependency_id} not found")

        self.db.delete(dependency)

    # -------------------------------------------------------------------------
    # Communications (Segment 4)
    # -------------------------------------------------------------------------

    def add_communication(self, ticket_id: int, data: CommunicationData) -> TicketCommunication:
        """Add a communication log entry to a ticket.

        Args:
            ticket_id: The ticket ID.
            data: Communication data.

        Returns:
            The created TicketCommunication (not yet committed).

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.get_ticket(ticket_id)

        comm = TicketCommunication(
            ticket_id=ticket.id,
            communication_type=data.communication_type,
            communication_medium=data.communication_medium,
            subject=data.subject,
            content=data.content,
            sender=data.sender,
            sender_full_name=data.sender_full_name,
            recipients=data.recipients,
            cc=data.cc,
            bcc=data.bcc,
            sent_or_received=data.sent_or_received,
            read_receipt=data.read_receipt,
            delivery_status=data.delivery_status,
            communication_date=data.communication_date or datetime.now(timezone.utc),
        )
        self.db.add(comm)
        self.db.flush()

        return comm

    def update_communication(
        self, ticket_id: int, communication_id: int, data: CommunicationData
    ) -> TicketCommunication:
        """Update a ticket communication.

        Args:
            ticket_id: The ticket ID.
            communication_id: The communication ID.
            data: Fields to update.

        Returns:
            The updated TicketCommunication.

        Raises:
            NotFoundError: If ticket or communication not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        comm = (
            self.db.query(TicketCommunication)
            .filter(
                TicketCommunication.id == communication_id,
                TicketCommunication.ticket_id == ticket_id,
            )
            .first()
        )
        if not comm:
            raise NotFoundError(f"Communication {communication_id} not found")

        fields = [
            "communication_type", "communication_medium", "subject", "content",
            "sender", "sender_full_name", "recipients", "cc", "bcc",
            "sent_or_received", "read_receipt", "delivery_status", "communication_date",
        ]
        for field_name in fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(comm, field_name, value)

        return comm

    def delete_communication(self, ticket_id: int, communication_id: int) -> None:
        """Delete a ticket communication.

        Args:
            ticket_id: The ticket ID.
            communication_id: The communication ID.

        Raises:
            NotFoundError: If ticket or communication not found.
        """
        # Verify ticket exists
        self.get_ticket(ticket_id)

        comm = (
            self.db.query(TicketCommunication)
            .filter(
                TicketCommunication.id == communication_id,
                TicketCommunication.ticket_id == ticket_id,
            )
            .first()
        )
        if not comm:
            raise NotFoundError(f"Communication {communication_id} not found")

        self.db.delete(comm)

    # -------------------------------------------------------------------------
    # Merge / Split (Segment 4)
    # -------------------------------------------------------------------------

    def merge_tickets(self, target_ticket_id: int, data: MergeData) -> Ticket:
        """Merge source tickets into a target ticket.

        Args:
            target_ticket_id: The target ticket ID.
            data: Merge data containing source ticket IDs.

        Returns:
            The updated target Ticket (not yet committed).

        Raises:
            NotFoundError: If target ticket not found.
            ValidationError: If target ticket is closed.
        """
        target = self.get_ticket(target_ticket_id)

        if target.status == TicketStatus.CLOSED:
            raise ValidationError("Cannot merge into a closed ticket")

        merged_ids = target.merged_tickets or []
        merged_count = 0

        for source_id in data.source_ticket_ids:
            if source_id == target_ticket_id:
                continue

            source = (
                self.db.query(Ticket)
                .filter(Ticket.id == source_id, Ticket.is_deleted == False)
                .first()
            )
            if not source:
                continue

            # Copy comments from source to target
            for comment in source.comments:
                max_idx = (
                    self.db.query(func.max(HDTicketComment.idx))
                    .filter(HDTicketComment.ticket_id == target_ticket_id)
                    .scalar()
                )
                new_comment = HDTicketComment(
                    ticket_id=target.id,
                    comment=f"[Merged from #{source.ticket_number}] {comment.comment}",
                    comment_type=comment.comment_type,
                    commented_by=comment.commented_by,
                    commented_by_name=comment.commented_by_name,
                    is_public=comment.is_public,
                    comment_date=comment.comment_date,
                    idx=(max_idx or 0) + 1,
                )
                self.db.add(new_comment)

            # Merge tags
            if source.tags:
                target_tags = target.tags or []
                added = [t for t in source.tags if t not in target_tags]
                target.tags = list(set(target_tags + source.tags))
                # Update usage counts for newly added tags
                if added:
                    for tag in (
                        self.db.query(TicketTag)
                        .filter(TicketTag.name.in_(added), TicketTag.is_active == True)
                        .all()
                    ):
                        tag.usage_count = (tag.usage_count or 0) + 1

            # Link source to target
            source.merged_into_id = target.id

            if data.close_source_tickets:
                source.status = TicketStatus.CLOSED
                source.resolution = f"Merged into ticket #{target.ticket_number}"
                source.resolution_date = datetime.now(timezone.utc)

            merged_ids.append(source_id)
            merged_count += 1

            # Add activity
            max_idx = (
                self.db.query(func.max(HDTicketActivity.idx))
                .filter(HDTicketActivity.ticket_id == target_ticket_id)
                .scalar()
            )
            activity = HDTicketActivity(
                ticket_id=target.id,
                activity_type="merge",
                activity=f"Merged ticket #{source.ticket_number} into this ticket",
                owner=self.principal.email if self.principal else None,
                activity_date=datetime.now(timezone.utc),
                idx=(max_idx or 0) + 1,
            )
            self.db.add(activity)

        target.merged_tickets = merged_ids
        target.updated_at = datetime.now(timezone.utc)
        target.updated_by_id = self.principal.id if self.principal else None

        return target

    def split_ticket(self, parent_ticket_id: int, data: SplitData) -> Ticket:
        """Create a sub-ticket (child) from a parent ticket.

        Args:
            parent_ticket_id: The parent ticket ID.
            data: Split data.

        Returns:
            The created child Ticket (not yet committed).

        Raises:
            NotFoundError: If parent ticket not found.
        """
        parent = self.get_ticket(parent_ticket_id)

        child = Ticket(
            ticket_number=_generate_ticket_number(),
            subject=data.subject,
            description=data.description or f"Sub-ticket of #{parent.ticket_number}",
            status=TicketStatus.OPEN,
            priority=parent.priority,
            ticket_type=parent.ticket_type,
            issue_type=parent.issue_type,
            customer_account_id=parent.customer_account_id,
            party_id=parent.party_id,
            project_id=parent.project_id,
            resolution_team=parent.resolution_team,
            customer_email=parent.customer_email,
            customer_phone=parent.customer_phone,
            customer_name=parent.customer_name,
            region=parent.region,
            base_station=parent.base_station,
            parent_ticket_id=parent.id,
            origin_system="local",
            write_back_status="pending",
            created_by_id=self.principal.id if self.principal else None,
            updated_by_id=self.principal.id if self.principal else None,
            opening_date=datetime.now(timezone.utc),
        )

        if data.copy_tags and parent.tags:
            child.tags = parent.tags.copy()

        if data.copy_custom_fields and parent.custom_fields:
            child.custom_fields = parent.custom_fields.copy()

        self.db.add(child)
        self.db.flush()

        # Add activity to parent
        max_idx = (
            self.db.query(func.max(HDTicketActivity.idx))
            .filter(HDTicketActivity.ticket_id == parent_ticket_id)
            .scalar()
        )
        activity = HDTicketActivity(
            ticket_id=parent.id,
            activity_type="split",
            activity=f"Created sub-ticket: {data.subject}",
            owner=self.principal.email if self.principal else None,
            activity_date=datetime.now(timezone.utc),
            idx=(max_idx or 0) + 1,
        )
        self.db.add(activity)

        parent.updated_at = datetime.now(timezone.utc)
        parent.updated_by_id = self.principal.id if self.principal else None

        return child

    def list_sub_tickets(self, parent_ticket_id: int) -> List[Ticket]:
        """List all sub-tickets of a parent ticket.

        Args:
            parent_ticket_id: The parent ticket ID.

        Returns:
            List of child tickets.

        Raises:
            NotFoundError: If parent ticket not found.
        """
        # Verify parent exists
        self.get_ticket(parent_ticket_id)

        return (
            self.db.query(Ticket)
            .filter(
                Ticket.parent_ticket_id == parent_ticket_id,
                Ticket.is_deleted == False,
            )
            .order_by(Ticket.created_at.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update(self, data: BulkUpdateData) -> BulkResult:
        """Bulk update multiple tickets.

        Updates the specified fields on all tickets matching the provided IDs.
        Sets audit fields (updated_by_id, updated_at) on each ticket.

        Args:
            data: Bulk update data containing IDs and fields to update.

        Returns:
            BulkResult with count of updated tickets and any failures.

        Note:
            Does NOT commit. Caller is responsible for committing.
        """
        if not data.ids:
            return BulkResult()

        result = BulkResult()
        now = datetime.now(timezone.utc)
        user_id = self.principal.id if self.principal else None

        # Build update dict from non-None fields
        updates: dict = {}
        if data.status is not None:
            updates["status"] = data.status
        if data.priority is not None:
            updates["priority"] = data.priority
        if data.assigned_to is not None:
            updates["assigned_to"] = data.assigned_to
        if data.assigned_employee_id is not None:
            updates["assigned_employee_id"] = data.assigned_employee_id

        if not updates:
            return result

        # Add audit fields
        updates["updated_at"] = now
        updates["updated_by_id"] = user_id

        # Handle auto resolution_date for resolved/closed status
        if data.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            updates["resolution_date"] = now

        # Perform bulk update
        query = self.db.query(Ticket).filter(
            Ticket.id.in_(data.ids),
            Ticket.is_deleted == False,
        )
        result.updated_count = query.update(updates, synchronize_session=False)

        return result

    def bulk_delete(self, ids: List[int]) -> BulkResult:
        """Bulk soft-delete multiple tickets.

        Marks tickets as deleted without removing from database.
        Sets audit fields on each ticket.

        Args:
            ids: List of ticket IDs to delete.

        Returns:
            BulkResult with count of deleted tickets and any failures.

        Note:
            Does NOT commit. Caller is responsible for committing.
        """
        if not ids:
            return BulkResult()

        result = BulkResult()
        now = datetime.now(timezone.utc)
        user_id = self.principal.id if self.principal else None

        # Perform bulk soft delete
        query = self.db.query(Ticket).filter(
            Ticket.id.in_(ids),
            Ticket.is_deleted == False,
        )
        result.deleted_count = query.update(
            {
                "is_deleted": True,
                "deleted_at": now,
                "deleted_by_id": user_id,
                "updated_at": now,
                "updated_by_id": user_id,
            },
            synchronize_session=False,
        )

        return result

    def update_field(
        self, ticket_id: int, field: str, value: str
    ) -> Ticket:
        """Update a single field on a ticket (for inline editing).

        Validates the field is allowed for inline editing and updates it.

        Args:
            ticket_id: The ticket ID.
            field: The field name to update (status, priority).
            value: The new value as string.

        Returns:
            The updated Ticket.

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If field is not allowed or value is invalid.
        """
        # Allowed fields for inline editing
        allowed_fields = {"status", "priority"}
        if field not in allowed_fields:
            raise ValidationError(f"Field '{field}' is not allowed for inline editing")

        ticket = self.get_ticket(ticket_id)

        # Parse and validate value based on field
        if field == "status":
            try:
                status = TicketStatus(value)
                ticket.status = status
                # Auto-set resolution date for resolved/closed
                if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                    if ticket.resolution_date is None:
                        ticket.resolution_date = datetime.now(timezone.utc)
            except ValueError:
                raise ValidationError(f"Invalid status value: {value}")

        elif field == "priority":
            try:
                ticket.priority = TicketPriority(value)
            except ValueError:
                raise ValidationError(f"Invalid priority value: {value}")

        # Set audit fields
        ticket.updated_by_id = self.principal.id if self.principal else None
        ticket.updated_at = datetime.now(timezone.utc)

        return ticket

    # -------------------------------------------------------------------------
    # Dashboard Statistics
    # -------------------------------------------------------------------------

    def get_dashboard_stats(self) -> dict:
        """Get support dashboard statistics.

        Returns:
            Dict containing:
                - total_open: Count of open tickets
                - urgent_tickets: Count of urgent priority open tickets
                - resolved_today: Count resolved today
                - resolved_week: Count resolved this week
                - created_today: Count created today
                - status_distribution: Dict of status -> count
                - priority_distribution: Dict of priority -> count
        """
        from datetime import timedelta

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)

        # Open statuses
        open_statuses = [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING,
            TicketStatus.REOPENED,
        ]

        # Total open tickets
        total_open = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.is_deleted == False,
                Ticket.status.in_(open_statuses),
            )
            .scalar()
            or 0
        )

        # Urgent tickets (open only)
        urgent_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.is_deleted == False,
                Ticket.priority == TicketPriority.URGENT,
                Ticket.status.in_(open_statuses),
            )
            .scalar()
            or 0
        )

        # Resolved today
        resolved_today = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.is_deleted == False,
                Ticket.status == TicketStatus.RESOLVED,
                Ticket.updated_at >= today,
            )
            .scalar()
            or 0
        )

        # Resolved this week
        resolved_week = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.is_deleted == False,
                Ticket.status == TicketStatus.RESOLVED,
                Ticket.updated_at >= week_ago,
            )
            .scalar()
            or 0
        )

        # Created today
        created_today = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.is_deleted == False,
                Ticket.created_at >= today,
            )
            .scalar()
            or 0
        )

        # Status distribution
        status_rows = (
            self.db.query(Ticket.status, func.count(Ticket.id).label("count"))
            .filter(Ticket.is_deleted == False)
            .group_by(Ticket.status)
            .all()
        )
        status_distribution = {
            row.status.value if hasattr(row.status, "value") else row.status: row.count
            for row in status_rows
        }

        # Priority distribution (open tickets only)
        priority_rows = (
            self.db.query(Ticket.priority, func.count(Ticket.id).label("count"))
            .filter(
                Ticket.is_deleted == False,
                Ticket.status.in_(open_statuses),
            )
            .group_by(Ticket.priority)
            .all()
        )
        priority_distribution = {
            row.priority.value if hasattr(row.priority, "value") else row.priority: row.count
            for row in priority_rows
        }

        return {
            "total_open": total_open,
            "urgent_tickets": urgent_tickets,
            "resolved_today": resolved_today,
            "resolved_week": resolved_week,
            "created_today": created_today,
            "status_distribution": status_distribution,
            "priority_distribution": priority_distribution,
        }

    def get_agent_stats(self, limit: int = 10) -> List[dict]:
        """Get agent workload statistics.

        Uses a single aggregate query instead of N+1 queries.

        Args:
            limit: Maximum number of agents to return.

        Returns:
            List of dicts with agent id, name, email, and open_tickets count.
        """
        # Subquery for open ticket counts per agent
        open_statuses = [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING,
            TicketStatus.REOPENED,
        ]

        open_tickets_subq = (
            self.db.query(
                Ticket.assigned_to_id,
                func.count(Ticket.id).label("open_count"),
            )
            .filter(
                Ticket.is_deleted == False,
                Ticket.status.in_(open_statuses),
            )
            .group_by(Ticket.assigned_to_id)
            .subquery()
        )

        # Join agents with their ticket counts
        agents_with_counts = (
            self.db.query(
                Agent.id,
                Agent.display_name,
                Agent.email,
                Agent.employee_id,
                func.coalesce(open_tickets_subq.c.open_count, 0).label("open_tickets"),
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

    def get_recent_tickets(
        self,
        limit: int = 10,
        status_filter: Optional[List[TicketStatus]] = None,
    ) -> List[Ticket]:
        """Get recent tickets, optionally filtered by status.

        Args:
            limit: Maximum number of tickets to return.
            status_filter: Optional list of statuses to filter by.

        Returns:
            List of Ticket instances.
        """
        query = self.db.query(Ticket).filter(Ticket.is_deleted == False)

        if status_filter:
            query = query.filter(Ticket.status.in_(status_filter))

        return query.order_by(Ticket.created_at.desc()).limit(limit).all()

    def get_unassigned_tickets(self, limit: int = 10) -> List[Ticket]:
        """Get unassigned open tickets.

        Args:
            limit: Maximum number of tickets to return.

        Returns:
            List of unassigned Ticket instances.
        """
        open_statuses = [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING,
            TicketStatus.REOPENED,
        ]

        return (
            self.db.query(Ticket)
            .filter(
                Ticket.is_deleted == False,
                Ticket.assigned_to_id.is_(None),
                Ticket.status.in_(open_statuses),
            )
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .all()
        )
