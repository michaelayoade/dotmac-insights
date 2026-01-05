"""Activity service - business logic for CRM activity management.

This service encapsulates activity-related business logic:
- Core CRUD for activities (calls, meetings, emails, tasks, etc.)
- Workflow (complete, cancel, reschedule)
- Timeline views
- Call logging
- Reminders

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.crm import Activity, ActivityType, ActivityStatus
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.utils.datetime_utils import utc_now

from .activity_types import (
    ActivityFilters,
    ActivityCreateData,
    ActivityUpdateData,
    CallLogData,
    ActivitySummary,
    ActivityTimeline,
)

if TYPE_CHECKING:
    from app.auth import Principal


class ActivityService:
    """Service for CRM activity management.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Activity CRUD
    # -------------------------------------------------------------------------

    def list_activities(
        self,
        filters: Optional[ActivityFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_relations: bool = True,
    ) -> PaginatedResult[Activity]:
        """List activities with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_relations: Whether to eagerly load related entities.

        Returns:
            PaginatedResult containing activities and total count.
        """
        query = scoped_query(self.db.query(Activity), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Activity.party),
                joinedload(Activity.opportunity),
                joinedload(Activity.owner),
                joinedload(Activity.assigned_to),
            )

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Activity.subject.ilike(like),
                        Activity.description.ilike(like),
                    )
                )

            if filters.activity_type:
                try:
                    type_enum = ActivityType(filters.activity_type.lower())
                    query = query.filter(Activity.activity_type == type_enum)
                except ValueError:
                    pass

            if filters.status:
                try:
                    status_enum = ActivityStatus(filters.status.lower())
                    query = query.filter(Activity.status == status_enum)
                except ValueError:
                    pass

            if filters.party_id:
                query = query.filter(Activity.party_id == filters.party_id)

            if filters.opportunity_id:
                query = query.filter(Activity.opportunity_id == filters.opportunity_id)

            if filters.owner_id:
                query = query.filter(Activity.owner_id == filters.owner_id)

            if filters.assigned_to_id:
                query = query.filter(Activity.assigned_to_id == filters.assigned_to_id)

            if filters.priority:
                query = query.filter(Activity.priority == filters.priority)

            if filters.scheduled_after:
                query = query.filter(Activity.scheduled_at >= filters.scheduled_after)

            if filters.scheduled_before:
                query = query.filter(Activity.scheduled_at <= filters.scheduled_before)

            if filters.completed_after:
                query = query.filter(Activity.completed_at >= filters.completed_after)

            if filters.completed_before:
                query = query.filter(Activity.completed_at <= filters.completed_before)

            if filters.has_reminder is True:
                query = query.filter(Activity.reminder_at.isnot(None))
            elif filters.has_reminder is False:
                query = query.filter(Activity.reminder_at.is_(None))

        query = query.order_by(Activity.scheduled_at.desc().nullsfirst())
        return paginate(query, pagination)

    def get_activity(self, activity_id: int, include_relations: bool = True) -> Activity:
        """Get an activity by ID.

        Args:
            activity_id: The activity ID.
            include_relations: Whether to eagerly load related entities.

        Returns:
            The Activity.

        Raises:
            NotFoundError: If activity not found.
        """
        query = scoped_query(self.db.query(Activity), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Activity.party),
                joinedload(Activity.opportunity),
                joinedload(Activity.owner),
                joinedload(Activity.assigned_to),
            )

        activity = query.filter(Activity.id == activity_id).first()
        if not activity:
            raise NotFoundError(f"Activity {activity_id} not found")

        return activity

    def create_activity(self, data: ActivityCreateData) -> Activity:
        """Create a new activity.

        Args:
            data: Activity creation data.

        Returns:
            The created Activity (not yet committed).
        """
        try:
            activity_type = ActivityType(data.activity_type.lower())
        except ValueError:
            raise ValidationError(f"Invalid activity type: {data.activity_type}")

        try:
            status = ActivityStatus(data.status.lower())
        except ValueError:
            status = ActivityStatus.PLANNED

        activity = Activity(
            activity_type=activity_type,
            subject=data.subject,
            description=data.description,
            status=status,
            party_id=data.party_id,
            opportunity_id=data.opportunity_id,
            scheduled_at=data.scheduled_at,
            duration_minutes=data.duration_minutes,
            owner_id=data.owner_id,
            assigned_to_id=data.assigned_to_id,
            priority=data.priority,
            reminder_at=data.reminder_at,
            call_direction=data.call_direction,
            call_outcome=data.call_outcome,
            email_message_id=data.email_message_id,
        )

        self.db.add(activity)
        self.db.flush()

        return activity

    def update_activity(self, activity_id: int, data: ActivityUpdateData) -> Activity:
        """Update an activity.

        Args:
            activity_id: The activity ID.
            data: Fields to update.

        Returns:
            The updated Activity (not yet committed).

        Raises:
            NotFoundError: If activity not found.
        """
        activity = self.get_activity(activity_id, include_relations=False)

        # Update simple fields
        simple_fields = [
            "subject", "description", "scheduled_at", "duration_minutes",
            "assigned_to_id", "priority", "reminder_at", "call_outcome",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(activity, field_name, value)

        # Handle status
        if data.status:
            try:
                activity.status = ActivityStatus(data.status.lower())
            except ValueError:
                raise ValidationError(f"Invalid status: {data.status}")

        return activity

    def delete_activity(self, activity_id: int) -> None:
        """Delete an activity.

        Args:
            activity_id: The activity ID.

        Raises:
            NotFoundError: If activity not found.
        """
        activity = self.get_activity(activity_id, include_relations=False)
        self.db.delete(activity)

    # -------------------------------------------------------------------------
    # Workflow Operations
    # -------------------------------------------------------------------------

    def complete_activity(self, activity_id: int, outcome: Optional[str] = None) -> Activity:
        """Mark an activity as completed.

        Args:
            activity_id: The activity ID.
            outcome: Optional outcome/result.

        Returns:
            The updated Activity.
        """
        activity = self.get_activity(activity_id, include_relations=False)

        if activity.status == ActivityStatus.COMPLETED:
            raise ValidationError("Activity is already completed")

        activity.status = ActivityStatus.COMPLETED
        activity.completed_at = utc_now()

        if outcome and activity.activity_type == ActivityType.CALL:
            activity.call_outcome = outcome

        return activity

    def cancel_activity(self, activity_id: int, reason: Optional[str] = None) -> Activity:
        """Cancel an activity.

        Args:
            activity_id: The activity ID.
            reason: Optional cancellation reason.

        Returns:
            The updated Activity.
        """
        activity = self.get_activity(activity_id, include_relations=False)

        if activity.status == ActivityStatus.COMPLETED:
            raise ValidationError("Cannot cancel completed activity")

        activity.status = ActivityStatus.CANCELLED

        return activity

    def reschedule_activity(self, activity_id: int, new_date: datetime) -> Activity:
        """Reschedule an activity.

        Args:
            activity_id: The activity ID.
            new_date: New scheduled datetime.

        Returns:
            The updated Activity.
        """
        activity = self.get_activity(activity_id, include_relations=False)

        if activity.status == ActivityStatus.COMPLETED:
            raise ValidationError("Cannot reschedule completed activity")

        activity.scheduled_at = new_date
        activity.status = ActivityStatus.PLANNED

        return activity

    # -------------------------------------------------------------------------
    # Timeline
    # -------------------------------------------------------------------------

    def get_timeline(
        self,
        party_id: Optional[int] = None,
        opportunity_id: Optional[int] = None,
        limit: int = 50,
    ) -> ActivityTimeline:
        """Get activity timeline for an entity.

        Args:
            party_id: Optional party ID.
            opportunity_id: Optional opportunity ID.
            limit: Maximum activities to return.

        Returns:
            ActivityTimeline with activities.
        """
        if not party_id and not opportunity_id:
            raise ValidationError("Either party_id or opportunity_id is required")

        query = self.db.query(Activity)

        if party_id:
            query = query.filter(Activity.party_id == party_id)
            entity_type = "party"
            entity_id = party_id
        else:
            query = query.filter(Activity.opportunity_id == opportunity_id)
            entity_type = "opportunity"
            entity_id = opportunity_id

        query = query.order_by(Activity.scheduled_at.desc().nullsfirst())
        activities = query.limit(limit).all()
        total = query.count()

        activity_dicts = [
            {
                "id": a.id,
                "type": a.activity_type.value,
                "subject": a.subject,
                "status": a.status.value,
                "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "priority": a.priority,
            }
            for a in activities
        ]

        return ActivityTimeline(
            entity_type=entity_type,
            entity_id=entity_id,
            activities=activity_dicts,
            total_count=total,
        )

    # -------------------------------------------------------------------------
    # Call Logging
    # -------------------------------------------------------------------------

    def log_call(self, data: CallLogData) -> Activity:
        """Log a call activity.

        Args:
            data: Call log data.

        Returns:
            Created Activity.
        """
        activity = Activity(
            activity_type=ActivityType.CALL,
            subject=data.subject,
            description=data.notes,
            status=ActivityStatus.COMPLETED,
            party_id=data.party_id,
            opportunity_id=data.opportunity_id,
            call_direction=data.direction,
            call_outcome=data.outcome,
            duration_minutes=data.duration_minutes,
            owner_id=data.owner_id,
            completed_at=utc_now(),
        )

        self.db.add(activity)
        self.db.flush()

        # Create follow-up if scheduled
        if data.scheduled_follow_up:
            follow_up = Activity(
                activity_type=ActivityType.FOLLOW_UP,
                subject=f"Follow-up: {data.subject}",
                status=ActivityStatus.PLANNED,
                party_id=data.party_id,
                opportunity_id=data.opportunity_id,
                scheduled_at=data.scheduled_follow_up,
                owner_id=data.owner_id,
            )
            self.db.add(follow_up)

        return activity

    # -------------------------------------------------------------------------
    # Reminders
    # -------------------------------------------------------------------------

    def get_upcoming_reminders(self, user_id: int, hours: int = 24) -> List[Activity]:
        """Get upcoming reminders for a user.

        Args:
            user_id: The user/employee ID.
            hours: Hours ahead to look.

        Returns:
            List of activities with reminders.
        """
        now = utc_now()
        cutoff = now + timedelta(hours=hours)

        return (
            self.db.query(Activity)
            .filter(
                Activity.reminder_at >= now,
                Activity.reminder_at <= cutoff,
                Activity.status == ActivityStatus.PLANNED,
                or_(
                    Activity.owner_id == user_id,
                    Activity.assigned_to_id == user_id,
                ),
            )
            .order_by(Activity.reminder_at)
            .all()
        )

    def get_overdue_activities(self, user_id: Optional[int] = None) -> List[Activity]:
        """Get overdue planned activities.

        Args:
            user_id: Optional user filter.

        Returns:
            List of overdue activities.
        """
        now = utc_now()

        query = (
            self.db.query(Activity)
            .filter(
                Activity.scheduled_at < now,
                Activity.status == ActivityStatus.PLANNED,
            )
        )

        if user_id:
            query = query.filter(
                or_(
                    Activity.owner_id == user_id,
                    Activity.assigned_to_id == user_id,
                )
            )

        return query.order_by(Activity.scheduled_at).all()

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self, filters: Optional[ActivityFilters] = None) -> ActivitySummary:
        """Get activity summary statistics.

        Args:
            filters: Optional filters.

        Returns:
            ActivitySummary with aggregated stats.
        """
        base_query = scoped_query(self.db.query(Activity), self.principal)

        if filters:
            if filters.scheduled_after:
                base_query = base_query.filter(Activity.scheduled_at >= filters.scheduled_after)
            if filters.scheduled_before:
                base_query = base_query.filter(Activity.scheduled_at <= filters.scheduled_before)
            if filters.owner_id:
                base_query = base_query.filter(Activity.owner_id == filters.owner_id)

        total = base_query.count()

        # By status
        planned = base_query.filter(Activity.status == ActivityStatus.PLANNED).count()
        completed = base_query.filter(Activity.status == ActivityStatus.COMPLETED).count()
        cancelled = base_query.filter(Activity.status == ActivityStatus.CANCELLED).count()

        # Overdue
        now = utc_now()
        overdue = (
            base_query.filter(
                Activity.scheduled_at < now,
                Activity.status == ActivityStatus.PLANNED,
            ).count()
        )

        # Completion rate
        non_cancelled = planned + completed
        completion_rate = (completed / non_cancelled * 100) if non_cancelled > 0 else 0.0

        # By type
        type_counts = (
            base_query.with_entities(Activity.activity_type, func.count(Activity.id))
            .group_by(Activity.activity_type)
            .all()
        )
        by_type = {t.value: cnt for t, cnt in type_counts}

        # By priority
        priority_counts = (
            base_query.with_entities(Activity.priority, func.count(Activity.id))
            .group_by(Activity.priority)
            .all()
        )
        by_priority = {p or "medium": cnt for p, cnt in priority_counts}

        # Average duration
        avg_duration = (
            base_query.filter(Activity.duration_minutes.isnot(None))
            .with_entities(func.avg(Activity.duration_minutes))
            .scalar()
        )

        return ActivitySummary(
            total_count=total,
            planned_count=planned,
            completed_count=completed,
            cancelled_count=cancelled,
            overdue_count=overdue,
            completion_rate=completion_rate,
            by_type=by_type,
            by_priority=by_priority,
            avg_duration_minutes=float(avg_duration) if avg_duration else 0.0,
        )
