"""Nurture sequence service - business logic for drip campaigns.

This service encapsulates nurture sequence operations:
- CRUD for sequences and steps
- Enrollment management
- Step execution and progression
- Metrics and analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.crm_engagement import (
    NurtureSequence,
    NurtureSequenceStatus,
    NurtureSequenceStep,
    NurtureStepType,
    NurtureEnrollment,
    NurtureEnrollmentStatus,
)
from app.models.party import Party
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.utils.datetime_utils import utc_now

from .nurture_types import (
    NurtureSequenceFilters,
    NurtureSequenceCreateData,
    NurtureSequenceUpdateData,
    NurtureStepCreateData,
    NurtureStepUpdateData,
    EnrollmentCreateData,
    NurtureSequenceSummary,
    NurtureSequenceMetrics,
    EnrollmentProgress,
)

if TYPE_CHECKING:
    from app.auth import Principal


class NurtureSequenceService:
    """Service for nurture sequence management.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Sequence CRUD
    # -------------------------------------------------------------------------

    def list_sequences(
        self,
        filters: Optional[NurtureSequenceFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[NurtureSequence]:
        """List nurture sequences with optional filters and pagination."""
        query = self.db.query(NurtureSequence).options(
            joinedload(NurtureSequence.steps)
        )

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(NurtureSequence.name.ilike(like))

            if filters.status:
                try:
                    status_enum = NurtureSequenceStatus(filters.status)
                    query = query.filter(NurtureSequence.status == status_enum)
                except ValueError:
                    pass

            if filters.campaign_id:
                query = query.filter(NurtureSequence.campaign_id == filters.campaign_id)

            if filters.created_by:
                query = query.filter(NurtureSequence.created_by == filters.created_by)

        query = query.order_by(NurtureSequence.created_at.desc())
        return paginate(query, pagination)

    def get_sequence(self, sequence_id: int) -> NurtureSequence:
        """Get a nurture sequence by ID."""
        sequence = (
            self.db.query(NurtureSequence)
            .options(joinedload(NurtureSequence.steps))
            .filter(NurtureSequence.id == sequence_id)
            .first()
        )
        if not sequence:
            raise NotFoundError(f"Nurture sequence {sequence_id} not found")
        return sequence

    def create_sequence(self, data: NurtureSequenceCreateData) -> NurtureSequence:
        """Create a new nurture sequence."""
        if not data.name:
            raise ValidationError("Sequence name is required")

        sequence = NurtureSequence(
            name=data.name,
            description=data.description,
            status=NurtureSequenceStatus.DRAFT,
            target_segment_id=data.target_segment_id,
            entry_trigger=data.entry_trigger,
            entry_conditions=data.entry_conditions or {},
            allow_reentry=data.allow_reentry,
            exit_on_reply=data.exit_on_reply,
            exit_on_conversion=data.exit_on_conversion,
            respect_contact_preferences=data.respect_contact_preferences,
            timezone_aware=data.timezone_aware,
            send_window_start=data.send_window_start,
            send_window_end=data.send_window_end,
            exclude_weekends=data.exclude_weekends,
            campaign_id=data.campaign_id,
            created_by=self.principal.party_id if self.principal else None,
        )
        self.db.add(sequence)
        self.db.flush()
        return sequence

    def update_sequence(
        self,
        sequence_id: int,
        data: NurtureSequenceUpdateData,
    ) -> NurtureSequence:
        """Update a nurture sequence."""
        sequence = self.get_sequence(sequence_id)

        if data.name is not None:
            sequence.name = data.name
        if data.description is not None:
            sequence.description = data.description
        if data.status is not None:
            try:
                sequence.status = NurtureSequenceStatus(data.status)
            except ValueError:
                raise ValidationError(f"Invalid status: {data.status}")
        if data.target_segment_id is not None:
            sequence.target_segment_id = data.target_segment_id
        if data.entry_trigger is not None:
            sequence.entry_trigger = data.entry_trigger
        if data.entry_conditions is not None:
            sequence.entry_conditions = data.entry_conditions
        if data.allow_reentry is not None:
            sequence.allow_reentry = data.allow_reentry
        if data.exit_on_reply is not None:
            sequence.exit_on_reply = data.exit_on_reply
        if data.exit_on_conversion is not None:
            sequence.exit_on_conversion = data.exit_on_conversion
        if data.respect_contact_preferences is not None:
            sequence.respect_contact_preferences = data.respect_contact_preferences
        if data.timezone_aware is not None:
            sequence.timezone_aware = data.timezone_aware
        if data.send_window_start is not None:
            sequence.send_window_start = data.send_window_start
        if data.send_window_end is not None:
            sequence.send_window_end = data.send_window_end
        if data.exclude_weekends is not None:
            sequence.exclude_weekends = data.exclude_weekends

        return sequence

    def delete_sequence(self, sequence_id: int) -> None:
        """Delete a nurture sequence."""
        sequence = self.get_sequence(sequence_id)
        self.db.delete(sequence)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def activate_sequence(self, sequence_id: int) -> NurtureSequence:
        """Activate a nurture sequence."""
        sequence = self.get_sequence(sequence_id)

        if not sequence.steps:
            raise ValidationError("Cannot activate sequence without steps")

        sequence.status = NurtureSequenceStatus.ACTIVE
        return sequence

    def pause_sequence(self, sequence_id: int) -> NurtureSequence:
        """Pause a nurture sequence."""
        sequence = self.get_sequence(sequence_id)
        sequence.status = NurtureSequenceStatus.PAUSED
        return sequence

    def complete_sequence(self, sequence_id: int) -> NurtureSequence:
        """Mark a sequence as completed."""
        sequence = self.get_sequence(sequence_id)
        sequence.status = NurtureSequenceStatus.COMPLETED
        return sequence

    # -------------------------------------------------------------------------
    # Step Management
    # -------------------------------------------------------------------------

    def add_step(
        self,
        sequence_id: int,
        data: NurtureStepCreateData,
    ) -> NurtureSequenceStep:
        """Add a step to a nurture sequence."""
        sequence = self.get_sequence(sequence_id)

        try:
            step_type = NurtureStepType(data.step_type)
        except ValueError:
            raise ValidationError(f"Invalid step type: {data.step_type}")

        step = NurtureSequenceStep(
            sequence_id=sequence_id,
            step_order=data.step_order,
            step_type=step_type,
            name=data.name,
            delay_days=data.delay_days,
            delay_hours=data.delay_hours,
            delay_minutes=data.delay_minutes,
            subject=data.subject,
            content=data.content,
            template_id=data.template_id,
            condition_field=data.condition_field,
            condition_operator=data.condition_operator,
            condition_value=data.condition_value,
            true_step_id=data.true_step_id,
            false_step_id=data.false_step_id,
            task_type=data.task_type,
            task_assignee_id=data.task_assignee_id,
            task_priority=data.task_priority,
            webhook_url=data.webhook_url,
            webhook_method=data.webhook_method,
            webhook_headers=data.webhook_headers or {},
            webhook_payload=data.webhook_payload,
            is_ab_test=data.is_ab_test,
            ab_variant=data.ab_variant,
            ab_weight=data.ab_weight,
        )
        self.db.add(step)
        self.db.flush()
        return step

    def update_step(
        self,
        step_id: int,
        data: NurtureStepUpdateData,
    ) -> NurtureSequenceStep:
        """Update a nurture sequence step."""
        step = self.db.query(NurtureSequenceStep).filter(
            NurtureSequenceStep.id == step_id
        ).first()
        if not step:
            raise NotFoundError(f"Step {step_id} not found")

        if data.name is not None:
            step.name = data.name
        if data.step_order is not None:
            step.step_order = data.step_order
        if data.delay_days is not None:
            step.delay_days = data.delay_days
        if data.delay_hours is not None:
            step.delay_hours = data.delay_hours
        if data.delay_minutes is not None:
            step.delay_minutes = data.delay_minutes
        if data.subject is not None:
            step.subject = data.subject
        if data.content is not None:
            step.content = data.content
        if data.template_id is not None:
            step.template_id = data.template_id
        if data.is_active is not None:
            step.is_active = data.is_active

        return step

    def remove_step(self, step_id: int) -> None:
        """Remove a step from a sequence."""
        step = self.db.query(NurtureSequenceStep).filter(
            NurtureSequenceStep.id == step_id
        ).first()
        if step:
            self.db.delete(step)

    def reorder_steps(self, sequence_id: int, step_order: List[int]) -> None:
        """Reorder steps in a sequence."""
        for order, step_id in enumerate(step_order, 1):
            self.db.query(NurtureSequenceStep).filter(
                NurtureSequenceStep.id == step_id,
                NurtureSequenceStep.sequence_id == sequence_id,
            ).update({"step_order": order})

    # -------------------------------------------------------------------------
    # Enrollment
    # -------------------------------------------------------------------------

    def enroll_contact(
        self,
        sequence_id: int,
        data: EnrollmentCreateData,
    ) -> NurtureEnrollment:
        """Enroll a contact in a nurture sequence."""
        sequence = self.get_sequence(sequence_id)

        if sequence.status != NurtureSequenceStatus.ACTIVE:
            raise ValidationError("Cannot enroll in inactive sequence")

        # Check if already enrolled
        existing = (
            self.db.query(NurtureEnrollment)
            .filter(
                NurtureEnrollment.sequence_id == sequence_id,
                NurtureEnrollment.party_id == data.party_id,
                NurtureEnrollment.status == NurtureEnrollmentStatus.ACTIVE,
            )
            .first()
        )

        if existing and not sequence.allow_reentry:
            raise ValidationError("Contact already enrolled in this sequence")

        # Check contact preferences
        if sequence.respect_contact_preferences:
            party = self.db.query(Party).filter(Party.id == data.party_id).first()
            if party and party.do_not_contact:
                raise ValidationError("Contact has opted out of communications")

        # Get first step
        first_step = (
            self.db.query(NurtureSequenceStep)
            .filter(
                NurtureSequenceStep.sequence_id == sequence_id,
                NurtureSequenceStep.is_active == True,
            )
            .order_by(NurtureSequenceStep.step_order)
            .first()
        )

        # Calculate next step time
        now = utc_now()
        next_step_at = now
        if first_step:
            next_step_at = now + timedelta(
                days=first_step.delay_days,
                hours=first_step.delay_hours,
                minutes=first_step.delay_minutes,
            )

        enrollment = NurtureEnrollment(
            sequence_id=sequence_id,
            party_id=data.party_id,
            status=NurtureEnrollmentStatus.ACTIVE,
            current_step_id=first_step.id if first_step else None,
            next_step_at=next_step_at,
            source=data.source,
            source_id=data.source_id,
        )
        self.db.add(enrollment)
        self.db.flush()

        # Update sequence metrics
        sequence.total_enrolled += 1

        return enrollment

    def pause_enrollment(self, enrollment_id: int) -> NurtureEnrollment:
        """Pause an enrollment."""
        enrollment = self._get_enrollment(enrollment_id)
        enrollment.status = NurtureEnrollmentStatus.PAUSED
        return enrollment

    def resume_enrollment(self, enrollment_id: int) -> NurtureEnrollment:
        """Resume a paused enrollment."""
        enrollment = self._get_enrollment(enrollment_id)
        if enrollment.status != NurtureEnrollmentStatus.PAUSED:
            raise ValidationError("Can only resume paused enrollments")
        enrollment.status = NurtureEnrollmentStatus.ACTIVE
        return enrollment

    def complete_enrollment(
        self,
        enrollment_id: int,
        converted: bool = False,
    ) -> NurtureEnrollment:
        """Complete an enrollment."""
        enrollment = self._get_enrollment(enrollment_id)
        enrollment.status = (
            NurtureEnrollmentStatus.CONVERTED if converted
            else NurtureEnrollmentStatus.COMPLETED
        )
        enrollment.completed_at = utc_now()

        # Update sequence metrics
        sequence = self.get_sequence(enrollment.sequence_id)
        sequence.total_completed += 1
        if converted:
            sequence.total_converted += 1

        return enrollment

    def unsubscribe_enrollment(
        self,
        enrollment_id: int,
        reason: Optional[str] = None,
    ) -> NurtureEnrollment:
        """Unsubscribe from a sequence."""
        enrollment = self._get_enrollment(enrollment_id)
        enrollment.status = NurtureEnrollmentStatus.UNSUBSCRIBED
        enrollment.exit_reason = reason or "unsubscribed"
        enrollment.completed_at = utc_now()

        # Update sequence metrics
        sequence = self.get_sequence(enrollment.sequence_id)
        sequence.total_unsubscribed += 1

        return enrollment

    def _get_enrollment(self, enrollment_id: int) -> NurtureEnrollment:
        """Get an enrollment by ID."""
        enrollment = self.db.query(NurtureEnrollment).filter(
            NurtureEnrollment.id == enrollment_id
        ).first()
        if not enrollment:
            raise NotFoundError(f"Enrollment {enrollment_id} not found")
        return enrollment

    # -------------------------------------------------------------------------
    # Progression
    # -------------------------------------------------------------------------

    def get_pending_steps(self, limit: int = 100) -> List[NurtureEnrollment]:
        """Get enrollments with pending steps to execute."""
        now = utc_now()
        return (
            self.db.query(NurtureEnrollment)
            .filter(
                NurtureEnrollment.status == NurtureEnrollmentStatus.ACTIVE,
                NurtureEnrollment.next_step_at <= now,
            )
            .order_by(NurtureEnrollment.next_step_at)
            .limit(limit)
            .all()
        )

    def advance_to_next_step(self, enrollment_id: int) -> NurtureEnrollment:
        """Advance enrollment to the next step."""
        enrollment = self._get_enrollment(enrollment_id)
        current_step = self.db.query(NurtureSequenceStep).filter(
            NurtureSequenceStep.id == enrollment.current_step_id
        ).first()

        if not current_step:
            # No more steps, complete the sequence
            return self.complete_enrollment(enrollment_id)

        # Find next step
        next_step = (
            self.db.query(NurtureSequenceStep)
            .filter(
                NurtureSequenceStep.sequence_id == enrollment.sequence_id,
                NurtureSequenceStep.step_order > current_step.step_order,
                NurtureSequenceStep.is_active == True,
            )
            .order_by(NurtureSequenceStep.step_order)
            .first()
        )

        if not next_step:
            # No more steps, complete
            return self.complete_enrollment(enrollment_id)

        # Calculate next execution time
        now = utc_now()
        next_step_at = now + timedelta(
            days=next_step.delay_days,
            hours=next_step.delay_hours,
            minutes=next_step.delay_minutes,
        )

        enrollment.current_step_id = next_step.id
        enrollment.next_step_at = next_step_at
        enrollment.steps_completed += 1

        return enrollment

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self) -> NurtureSequenceSummary:
        """Get summary of all nurture sequences."""
        total = self.db.query(func.count(NurtureSequence.id)).scalar() or 0
        active = (
            self.db.query(func.count(NurtureSequence.id))
            .filter(NurtureSequence.status == NurtureSequenceStatus.ACTIVE)
            .scalar() or 0
        )
        draft = (
            self.db.query(func.count(NurtureSequence.id))
            .filter(NurtureSequence.status == NurtureSequenceStatus.DRAFT)
            .scalar() or 0
        )
        paused = (
            self.db.query(func.count(NurtureSequence.id))
            .filter(NurtureSequence.status == NurtureSequenceStatus.PAUSED)
            .scalar() or 0
        )

        total_enrolled = (
            self.db.query(func.sum(NurtureSequence.total_enrolled)).scalar() or 0
        )
        total_completed = (
            self.db.query(func.sum(NurtureSequence.total_completed)).scalar() or 0
        )
        total_converted = (
            self.db.query(func.sum(NurtureSequence.total_converted)).scalar() or 0
        )

        avg_conversion = (
            (total_converted / total_completed * 100) if total_completed > 0 else 0.0
        )

        return NurtureSequenceSummary(
            total_sequences=total,
            active_sequences=active,
            draft_sequences=draft,
            paused_sequences=paused,
            total_enrolled=total_enrolled,
            total_completed=total_completed,
            avg_conversion_rate=avg_conversion,
        )

    def get_sequence_metrics(self, sequence_id: int) -> NurtureSequenceMetrics:
        """Get detailed metrics for a sequence."""
        sequence = self.get_sequence(sequence_id)

        active_enrolled = (
            self.db.query(func.count(NurtureEnrollment.id))
            .filter(
                NurtureEnrollment.sequence_id == sequence_id,
                NurtureEnrollment.status == NurtureEnrollmentStatus.ACTIVE,
            )
            .scalar() or 0
        )

        conversion_rate = (
            (sequence.total_converted / sequence.total_completed * 100)
            if sequence.total_completed > 0 else 0.0
        )
        completion_rate = (
            (sequence.total_completed / sequence.total_enrolled * 100)
            if sequence.total_enrolled > 0 else 0.0
        )

        # Step metrics
        step_metrics = []
        for step in sequence.steps:
            open_rate = (step.open_count / step.sent_count * 100) if step.sent_count > 0 else 0.0
            click_rate = (step.click_count / step.sent_count * 100) if step.sent_count > 0 else 0.0
            step_metrics.append({
                "step_id": step.id,
                "step_order": step.step_order,
                "name": step.name,
                "type": step.step_type.value,
                "sent_count": step.sent_count,
                "open_count": step.open_count,
                "click_count": step.click_count,
                "reply_count": step.reply_count,
                "open_rate": open_rate,
                "click_rate": click_rate,
            })

        return NurtureSequenceMetrics(
            sequence_id=sequence.id,
            sequence_name=sequence.name,
            status=sequence.status.value,
            total_steps=len(sequence.steps),
            total_enrolled=sequence.total_enrolled,
            active_enrolled=active_enrolled,
            completed=sequence.total_completed,
            converted=sequence.total_converted,
            unsubscribed=sequence.total_unsubscribed,
            conversion_rate=conversion_rate,
            completion_rate=completion_rate,
            avg_time_to_complete_days=None,  # Would need timestamp analysis
            step_metrics=step_metrics,
        )

    def get_enrollment_progress(self, party_id: int) -> List[EnrollmentProgress]:
        """Get all enrollment progress for a contact."""
        enrollments = (
            self.db.query(NurtureEnrollment)
            .filter(NurtureEnrollment.party_id == party_id)
            .all()
        )

        results = []
        for enrollment in enrollments:
            sequence = self.get_sequence(enrollment.sequence_id)
            party = self.db.query(Party).filter(Party.id == party_id).first()
            total_steps = len(sequence.steps)
            progress = (
                (enrollment.steps_completed / total_steps * 100)
                if total_steps > 0 else 0.0
            )
            open_rate = (
                (enrollment.emails_opened / enrollment.emails_sent * 100)
                if enrollment.emails_sent > 0 else 0.0
            )

            results.append(EnrollmentProgress(
                enrollment_id=enrollment.id,
                party_id=party_id,
                party_name=party.name if party else "",
                sequence_id=sequence.id,
                sequence_name=sequence.name,
                status=enrollment.status.value,
                current_step=enrollment.steps_completed + 1,
                total_steps=total_steps,
                progress_percent=progress,
                next_step_at=enrollment.next_step_at,
                emails_sent=enrollment.emails_sent,
                emails_opened=enrollment.emails_opened,
                open_rate=open_rate,
                enrolled_at=enrollment.enrolled_at,
                completed_at=enrollment.completed_at,
            ))

        return results
