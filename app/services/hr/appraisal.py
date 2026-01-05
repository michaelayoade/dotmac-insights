"""Appraisal service implementation.

Handles appraisal templates, employee appraisals, and scoring.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.utils.datetime_utils import utc_now
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.hr_appraisal import (
    Appraisal,
    AppraisalGoal,
    AppraisalStatus,
    AppraisalTemplate,
    AppraisalTemplateGoal,
)
from app.services.base import PaginatedResult, Pagination, SortParam, paginate
from app.services.hr.errors import (
    AppraisalNotFoundError,
    AppraisalStatusError,
    AppraisalTemplateNotFoundError,
    ValidationError,
)
from app.services.hr.appraisal_types import (
    AppraisalCreateData,
    AppraisalFilters,
    AppraisalGoalData,
    AppraisalMetrics,
    AppraisalScoreData,
    AppraisalUpdateData,
    EmployeeAppraisalSummary,
    TeamAppraisalSummary,
    TemplateCreateData,
    TemplateFilters,
    TemplateGoalData,
    TemplateUpdateData,
)
if TYPE_CHECKING:
    from app.models.hr_settings import HRSettings
    from sqlalchemy.orm import Session

    from app.web.auth import Principal

__all__ = ["AppraisalService"]


# Valid status transitions
STATUS_TRANSITIONS = {
    AppraisalStatus.DRAFT: {
        AppraisalStatus.SUBMITTED,
        AppraisalStatus.CANCELLED,
    },
    AppraisalStatus.SUBMITTED: {
        AppraisalStatus.COMPLETED,
        AppraisalStatus.DRAFT,  # Return for corrections
        AppraisalStatus.CANCELLED,
    },
    AppraisalStatus.COMPLETED: set(),  # Terminal state
    AppraisalStatus.CANCELLED: set(),  # Terminal state
}


class AppraisalService:
    """Service for managing appraisal templates and employee appraisals.

    Uses HR settings for configurable behavior:
    - appraisal_rating_scale: Rating scale (e.g., 1-5)
    - require_self_review: Whether self-review is mandatory
    - require_peer_review: Whether peer review is mandatory
    - min_rating_for_promotion: Minimum rating required for promotion eligibility
    """

    def __init__(
        self,
        db: "Session",
        principal: Optional["Principal"] = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self._settings_cache: dict[str, "HRSettings"] = {}

    def _get_settings(self, company: Optional[str] = None) -> "HRSettings":
        """Get HR settings, using cache for repeated access within same request."""
        cache_key = company or "__default__"
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]

        from .settings import HRSettingsService

        settings_service = HRSettingsService(self.db, self.principal)
        self._settings_cache[cache_key] = settings_service.get_settings(company)
        return self._settings_cache[cache_key]

    # =========================================================================
    # Appraisal Templates
    # =========================================================================

    def list_templates(
        self,
        filters: Optional[TemplateFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[AppraisalTemplate]:
        """List appraisal templates with optional filters."""
        query = select(AppraisalTemplate).options(
            joinedload(AppraisalTemplate.goals)
        )

        if filters:
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        AppraisalTemplate.template_name.ilike(search_term),
                        AppraisalTemplate.description.ilike(search_term),
                    )
                )

        # Default sort by name
        if sort:
            col = getattr(AppraisalTemplate, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(AppraisalTemplate.template_name)

        return paginate(self.db, query, pagination)

    def get_template(self, template_id: int) -> AppraisalTemplate:
        """Get an appraisal template by ID."""
        template = self.db.scalar(
            select(AppraisalTemplate)
            .options(joinedload(AppraisalTemplate.goals))
            .where(AppraisalTemplate.id == template_id)
        )
        if not template:
            raise AppraisalTemplateNotFoundError(template_id)
        return template

    def create_template(self, data: TemplateCreateData) -> AppraisalTemplate:
        """Create a new appraisal template."""
        # Validate weightage totals 100%
        if data.goals:
            total_weight = sum(g.per_weightage for g in data.goals)
            if total_weight != Decimal("100"):
                raise ValidationError(
                    f"Goal weightages must total 100%, got {total_weight}%"
                )

        template = AppraisalTemplate(
            template_name=data.template_name,
            description=data.description,
        )

        self.db.add(template)
        self.db.flush()

        # Add goals
        for idx, goal_data in enumerate(data.goals):
            goal = AppraisalTemplateGoal(
                appraisal_template_id=template.id,
                kra=goal_data.kra,
                per_weightage=goal_data.per_weightage,
                idx=idx,
            )
            self.db.add(goal)

        self.db.flush()
        return template

    def update_template(
        self,
        template_id: int,
        data: TemplateUpdateData,
    ) -> AppraisalTemplate:
        """Update an appraisal template."""
        template = self.get_template(template_id)

        if data.template_name is not None:
            template.template_name = data.template_name
        if data.description is not None:
            template.description = data.description

        # Update goals if provided
        if data.goals is not None:
            # Validate weightage
            if data.goals:
                total_weight = sum(g.per_weightage for g in data.goals)
                if total_weight != Decimal("100"):
                    raise ValidationError(
                        f"Goal weightages must total 100%, got {total_weight}%"
                    )

            # Remove existing goals
            self.db.execute(
                AppraisalTemplateGoal.__table__.delete().where(
                    AppraisalTemplateGoal.appraisal_template_id == template_id
                )
            )

            # Add new goals
            for idx, goal_data in enumerate(data.goals):
                goal = AppraisalTemplateGoal(
                    appraisal_template_id=template_id,
                    kra=goal_data.kra,
                    per_weightage=goal_data.per_weightage,
                    idx=idx,
                )
                self.db.add(goal)

        self.db.flush()
        return template

    def delete_template(self, template_id: int) -> None:
        """Delete an appraisal template."""
        template = self.get_template(template_id)

        # Check if template is in use
        appraisal_count = self.db.scalar(
            select(func.count(Appraisal.id)).where(
                Appraisal.appraisal_template_id == template_id
            )
        )
        if appraisal_count and appraisal_count > 0:
            raise ValidationError(
                f"Cannot delete template with {appraisal_count} associated appraisals"
            )

        self.db.delete(template)
        self.db.flush()

    # =========================================================================
    # Appraisals
    # =========================================================================

    def list_appraisals(
        self,
        filters: Optional[AppraisalFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[Appraisal]:
        """List appraisals with optional filters."""
        query = select(Appraisal).options(joinedload(Appraisal.goals))

        if filters:
            conditions = []

            if filters.employee_id is not None:
                conditions.append(Appraisal.employee_id == filters.employee_id)

            if filters.appraisal_template_id is not None:
                conditions.append(
                    Appraisal.appraisal_template_id == filters.appraisal_template_id
                )

            if filters.status is not None:
                conditions.append(Appraisal.status == filters.status)

            if filters.company is not None:
                conditions.append(Appraisal.company == filters.company)

            if filters.from_date is not None:
                conditions.append(Appraisal.start_date >= filters.from_date)

            if filters.to_date is not None:
                conditions.append(Appraisal.end_date <= filters.to_date)

            if filters.search:
                conditions.append(
                    Appraisal.employee_name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by start date descending
        if sort:
            col = getattr(Appraisal, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(Appraisal.start_date.desc())

        return paginate(self.db, query, pagination)

    def get_appraisal(self, appraisal_id: int) -> Appraisal:
        """Get an appraisal by ID."""
        appraisal = self.db.scalar(
            select(Appraisal)
            .options(joinedload(Appraisal.goals))
            .where(Appraisal.id == appraisal_id)
        )
        if not appraisal:
            raise AppraisalNotFoundError(appraisal_id)
        return appraisal

    def create_appraisal(self, data: AppraisalCreateData) -> Appraisal:
        """Create a new appraisal for an employee."""
        # Check for overlapping appraisal period
        existing = self.db.scalar(
            select(Appraisal).where(
                and_(
                    Appraisal.employee_id == data.employee_id,
                    Appraisal.status != AppraisalStatus.CANCELLED,
                    or_(
                        and_(
                            Appraisal.start_date <= data.start_date,
                            Appraisal.end_date >= data.start_date,
                        ),
                        and_(
                            Appraisal.start_date <= data.end_date,
                            Appraisal.end_date >= data.end_date,
                        ),
                        and_(
                            Appraisal.start_date >= data.start_date,
                            Appraisal.end_date <= data.end_date,
                        ),
                    ),
                )
            )
        )
        if existing:
            raise ValidationError(
                f"Employee already has an appraisal for overlapping period "
                f"({existing.start_date} to {existing.end_date})"
            )

        appraisal = Appraisal(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            appraisal_template_id=data.appraisal_template_id,
            appraisal_template=data.appraisal_template,
            start_date=data.start_date,
            end_date=data.end_date,
            company=data.company,
            feedback=data.feedback,
            reflections=data.reflections,
            status=AppraisalStatus.DRAFT,
        )

        if self.principal:
            appraisal.created_by_id = self.principal.user_id

        self.db.add(appraisal)
        self.db.flush()

        # Add goals from data or from template
        goals_to_add = data.goals
        if not goals_to_add and data.appraisal_template_id:
            template = self.get_template(data.appraisal_template_id)
            goals_to_add = [
                AppraisalGoalData(
                    kra=g.kra or "",
                    per_weightage=g.per_weightage,
                    idx=g.idx,
                )
                for g in template.goals
            ]

        for goal_data in goals_to_add:
            goal = AppraisalGoal(
                appraisal_id=appraisal.id,
                kra=goal_data.kra,
                per_weightage=goal_data.per_weightage,
                goal=goal_data.goal,
                score_earned=goal_data.score_earned,
                self_score=goal_data.self_score,
                idx=goal_data.idx,
            )
            self.db.add(goal)

        self.db.flush()
        return appraisal

    def update_appraisal(
        self,
        appraisal_id: int,
        data: AppraisalUpdateData,
    ) -> Appraisal:
        """Update an appraisal."""
        appraisal = self.get_appraisal(appraisal_id)

        # Can only update draft appraisals
        if appraisal.status not in (AppraisalStatus.DRAFT, AppraisalStatus.SUBMITTED):
            raise ValidationError(
                f"Cannot update appraisal in {appraisal.status.value} status"
            )

        if data.start_date is not None:
            appraisal.start_date = data.start_date
        if data.end_date is not None:
            appraisal.end_date = data.end_date
        if data.feedback is not None:
            appraisal.feedback = data.feedback
        if data.reflections is not None:
            appraisal.reflections = data.reflections

        # Update goals if provided
        if data.goals is not None:
            # Remove existing goals
            self.db.execute(
                AppraisalGoal.__table__.delete().where(
                    AppraisalGoal.appraisal_id == appraisal_id
                )
            )

            # Add new goals
            for goal_data in data.goals:
                goal = AppraisalGoal(
                    appraisal_id=appraisal_id,
                    kra=goal_data.kra,
                    per_weightage=goal_data.per_weightage,
                    goal=goal_data.goal,
                    score_earned=goal_data.score_earned,
                    self_score=goal_data.self_score,
                    idx=goal_data.idx,
                )
                self.db.add(goal)

            # Recalculate scores
            self._recalculate_scores(appraisal, data.goals)

        if self.principal:
            appraisal.updated_by_id = self.principal.user_id

        self.db.flush()
        return appraisal

    def _recalculate_scores(
        self,
        appraisal: Appraisal,
        goals: List[AppraisalGoalData],
    ) -> None:
        """Recalculate appraisal total scores from goals."""
        total_score = Decimal("0")
        self_score = Decimal("0")

        for goal in goals:
            # Weighted score = (score_earned * per_weightage) / 100
            weighted = (goal.score_earned * goal.per_weightage / Decimal("100"))
            total_score += weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            self_weighted = (goal.self_score * goal.per_weightage / Decimal("100"))
            self_score += self_weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        appraisal.total_score = total_score
        appraisal.self_score = self_score
        # Final score is typically the reviewer's score
        appraisal.final_score = total_score

    def _validate_status_transition(
        self,
        appraisal: Appraisal,
        target_status: AppraisalStatus,
    ) -> None:
        """Validate that a status transition is allowed."""
        current = appraisal.status
        allowed = STATUS_TRANSITIONS.get(current, set())

        if target_status not in allowed:
            raise AppraisalStatusError(
                appraisal.id,
                current.value,
                target_status.value,
            )

    def submit_appraisal(self, appraisal_id: int) -> Appraisal:
        """Submit an appraisal for review."""
        appraisal = self.get_appraisal(appraisal_id)
        self._validate_status_transition(appraisal, AppraisalStatus.SUBMITTED)

        appraisal.status = AppraisalStatus.SUBMITTED
        appraisal.status_changed_at = utc_now()

        if self.principal:
            appraisal.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return appraisal

    def complete_appraisal(
        self,
        appraisal_id: int,
        score_data: Optional[AppraisalScoreData] = None,
    ) -> Appraisal:
        """Complete an appraisal with final scores."""
        appraisal = self.get_appraisal(appraisal_id)
        self._validate_status_transition(appraisal, AppraisalStatus.COMPLETED)

        # Update scores if provided
        if score_data:
            if score_data.goals:
                # Update existing goals with new scores
                for goal_data in score_data.goals:
                    for goal in appraisal.goals:
                        if goal.kra == goal_data.kra:
                            goal.score_earned = goal_data.score_earned
                            goal.self_score = goal_data.self_score
                            if goal_data.goal:
                                goal.goal = goal_data.goal
                            break

                self._recalculate_scores(appraisal, score_data.goals)

            if score_data.feedback:
                appraisal.feedback = score_data.feedback

        appraisal.status = AppraisalStatus.COMPLETED
        appraisal.status_changed_at = utc_now()

        if self.principal:
            appraisal.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return appraisal

    def cancel_appraisal(self, appraisal_id: int) -> Appraisal:
        """Cancel an appraisal."""
        appraisal = self.get_appraisal(appraisal_id)
        self._validate_status_transition(appraisal, AppraisalStatus.CANCELLED)

        appraisal.status = AppraisalStatus.CANCELLED
        appraisal.status_changed_at = utc_now()

        if self.principal:
            appraisal.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return appraisal

    def return_appraisal(self, appraisal_id: int) -> Appraisal:
        """Return a submitted appraisal to draft for corrections."""
        appraisal = self.get_appraisal(appraisal_id)
        self._validate_status_transition(appraisal, AppraisalStatus.DRAFT)

        appraisal.status = AppraisalStatus.DRAFT
        appraisal.status_changed_at = utc_now()

        if self.principal:
            appraisal.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return appraisal

    def score_goal(
        self,
        appraisal_id: int,
        goal_id: int,
        score_earned: Decimal,
        self_score: Optional[Decimal] = None,
    ) -> AppraisalGoal:
        """Score an individual goal in an appraisal."""
        appraisal = self.get_appraisal(appraisal_id)

        if appraisal.status == AppraisalStatus.COMPLETED:
            raise ValidationError("Cannot score a completed appraisal")

        goal = self.db.get(AppraisalGoal, goal_id)
        if not goal or goal.appraisal_id != appraisal_id:
            raise ValidationError(f"Goal {goal_id} not found in appraisal {appraisal_id}")

        # Validate score range (typically 0-5 or 0-100)
        if score_earned < 0 or score_earned > 100:
            raise ValidationError("Score must be between 0 and 100")

        goal.score_earned = score_earned
        if self_score is not None:
            goal.self_score = self_score

        # Recalculate appraisal totals
        goals_data = [
            AppraisalGoalData(
                kra=g.kra or "",
                per_weightage=g.per_weightage,
                score_earned=g.score_earned,
                self_score=g.self_score,
            )
            for g in appraisal.goals
        ]
        self._recalculate_scores(appraisal, goals_data)

        self.db.flush()
        return goal

    # =========================================================================
    # Metrics & Reporting
    # =========================================================================

    def get_metrics(self, company: Optional[str] = None) -> AppraisalMetrics:
        """Get appraisal metrics and statistics."""
        metrics = AppraisalMetrics()

        company_condition = Appraisal.company == company if company else True

        # Template count
        metrics.total_templates = (
            self.db.scalar(select(func.count(AppraisalTemplate.id))) or 0
        )

        # Appraisal counts by status
        metrics.total_appraisals = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(company_condition)
            )
            or 0
        )

        metrics.draft_count = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(company_condition, Appraisal.status == AppraisalStatus.DRAFT)
                )
            )
            or 0
        )

        metrics.submitted_count = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(company_condition, Appraisal.status == AppraisalStatus.SUBMITTED)
                )
            )
            or 0
        )

        metrics.completed_count = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(company_condition, Appraisal.status == AppraisalStatus.COMPLETED)
                )
            )
            or 0
        )

        metrics.cancelled_count = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(company_condition, Appraisal.status == AppraisalStatus.CANCELLED)
                )
            )
            or 0
        )

        # Average score of completed appraisals
        avg_score = self.db.scalar(
            select(func.avg(Appraisal.final_score)).where(
                and_(
                    company_condition,
                    Appraisal.status == AppraisalStatus.COMPLETED,
                )
            )
        )
        if avg_score:
            metrics.average_score = Decimal(str(avg_score)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Current period (this year)
        today = date.today()
        year_start = today.replace(month=1, day=1)
        metrics.current_period_count = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(
                        company_condition,
                        Appraisal.start_date >= year_start,
                    )
                )
            )
            or 0
        )

        return metrics

    def get_employee_summary(self, employee_id: int) -> EmployeeAppraisalSummary:
        """Get appraisal summary for an employee."""
        # Get employee name from latest appraisal
        latest = self.db.scalar(
            select(Appraisal)
            .where(Appraisal.employee_id == employee_id)
            .order_by(Appraisal.end_date.desc())
        )

        summary = EmployeeAppraisalSummary(
            employee_id=employee_id,
            employee_name=latest.employee_name if latest else "",
        )

        # Count appraisals
        summary.total_appraisals = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    Appraisal.employee_id == employee_id
                )
            )
            or 0
        )

        # Completed count
        summary.completed_appraisals = (
            self.db.scalar(
                select(func.count(Appraisal.id)).where(
                    and_(
                        Appraisal.employee_id == employee_id,
                        Appraisal.status == AppraisalStatus.COMPLETED,
                    )
                )
            )
            or 0
        )

        # Average score
        avg = self.db.scalar(
            select(func.avg(Appraisal.final_score)).where(
                and_(
                    Appraisal.employee_id == employee_id,
                    Appraisal.status == AppraisalStatus.COMPLETED,
                )
            )
        )
        if avg:
            summary.average_score = Decimal(str(avg)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Latest completed appraisal
        latest_completed = self.db.scalar(
            select(Appraisal)
            .where(
                and_(
                    Appraisal.employee_id == employee_id,
                    Appraisal.status == AppraisalStatus.COMPLETED,
                )
            )
            .order_by(Appraisal.end_date.desc())
        )
        if latest_completed:
            summary.latest_score = latest_completed.final_score
            summary.latest_appraisal_date = latest_completed.end_date

        return summary

    def get_pending_appraisals(
        self,
        company: Optional[str] = None,
        limit: int = 10,
    ) -> Sequence[Appraisal]:
        """Get appraisals pending review/completion."""
        query = (
            select(Appraisal)
            .where(
                Appraisal.status.in_([
                    AppraisalStatus.DRAFT,
                    AppraisalStatus.SUBMITTED,
                ])
            )
            .order_by(Appraisal.end_date.asc())
            .limit(limit)
        )

        if company:
            query = query.where(Appraisal.company == company)

        return self.db.scalars(query).all()

    def get_employee_appraisals(
        self,
        employee_id: int,
        include_cancelled: bool = False,
    ) -> Sequence[Appraisal]:
        """Get all appraisals for an employee."""
        query = (
            select(Appraisal)
            .options(joinedload(Appraisal.goals))
            .where(Appraisal.employee_id == employee_id)
            .order_by(Appraisal.end_date.desc())
        )

        if not include_cancelled:
            query = query.where(Appraisal.status != AppraisalStatus.CANCELLED)

        return self.db.scalars(query).unique().all()
