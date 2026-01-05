"""Evaluation Period Service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.performance import (
    EvaluationPeriod,
    EvaluationPeriodType,
    EvaluationPeriodStatus,
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
)
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError, ConflictError

from .types import PeriodFilters, PeriodCreateData, PeriodUpdateData, PeriodStats


class EvaluationPeriodService:
    """Service for evaluation period management."""

    def __init__(self, db: Session):
        self.db = db

    def list_periods(
        self,
        filters: PeriodFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[EvaluationPeriod]:
        """List evaluation periods with filtering and pagination."""
        query = self.db.query(EvaluationPeriod)

        if filters.status:
            try:
                status_enum = EvaluationPeriodStatus(filters.status)
                query = query.filter(EvaluationPeriod.status == status_enum)
            except ValueError:
                raise ValidationError(f"Invalid status: {filters.status}")

        if filters.period_type:
            try:
                type_enum = EvaluationPeriodType(filters.period_type)
                query = query.filter(EvaluationPeriod.period_type == type_enum)
            except ValueError:
                raise ValidationError(f"Invalid period type: {filters.period_type}")

        if filters.year:
            query = query.filter(
                extract('year', EvaluationPeriod.start_date) == filters.year
            )

        total = query.count()

        # Apply sorting
        sort_column = getattr(EvaluationPeriod, filters.sort_by, EvaluationPeriod.start_date)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        periods = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=periods, total=total)

    def get_period(self, period_id: int) -> EvaluationPeriod:
        """Get a period by ID."""
        period = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == period_id
        ).first()
        if not period:
            raise NotFoundError(f"Period {period_id} not found")
        return period

    def get_period_stats(self, period_id: int) -> PeriodStats:
        """Get scorecard statistics for a period."""
        scorecard_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id
        ).scalar() or 0

        computed_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.COMPUTED,
                ScorecardInstanceStatus.IN_REVIEW,
                ScorecardInstanceStatus.APPROVED,
                ScorecardInstanceStatus.FINALIZED,
                'computed', 'in_review', 'approved', 'finalized'
            ])
        ).scalar() or 0

        finalized_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([ScorecardInstanceStatus.FINALIZED, 'finalized'])
        ).scalar() or 0

        pending_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([ScorecardInstanceStatus.PENDING, 'pending'])
        ).scalar() or 0

        in_review_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([ScorecardInstanceStatus.IN_REVIEW, 'in_review'])
        ).scalar() or 0

        return PeriodStats(
            scorecard_count=scorecard_count,
            computed_count=computed_count,
            finalized_count=finalized_count,
            pending_count=pending_count,
            in_review_count=in_review_count,
        )

    def create_period(self, data: PeriodCreateData) -> EvaluationPeriod:
        """Create a new evaluation period."""
        # Check code uniqueness
        existing = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.code == data.code
        ).first()
        if existing:
            raise ConflictError(f"Period with code '{data.code}' already exists")

        try:
            period_type = EvaluationPeriodType(data.period_type)
        except ValueError:
            raise ValidationError(f"Invalid period type: {data.period_type}")

        period = EvaluationPeriod(
            code=data.code,
            name=data.name,
            period_type=period_type,
            status=EvaluationPeriodStatus.DRAFT,
            start_date=data.start_date,
            end_date=data.end_date,
            scoring_deadline=data.scoring_deadline,
            review_deadline=data.review_deadline,
        )
        self.db.add(period)
        self.db.flush()
        return period

    def update_period(self, period_id: int, data: PeriodUpdateData) -> EvaluationPeriod:
        """Update an evaluation period."""
        period = self.get_period(period_id)

        if period.status == EvaluationPeriodStatus.FINALIZED:
            raise ValidationError("Cannot update finalized period")

        if data.name is not None:
            period.name = data.name
        if data.scoring_deadline is not None:
            period.scoring_deadline = data.scoring_deadline
        if data.review_deadline is not None:
            period.review_deadline = data.review_deadline

        self.db.flush()
        return period

    def delete_period(self, period_id: int) -> None:
        """Delete a draft period."""
        period = self.get_period(period_id)

        if period.status != EvaluationPeriodStatus.DRAFT:
            raise ValidationError("Can only delete draft periods")

        # Check for existing scorecards
        scorecard_count = self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id
        ).scalar() or 0

        if scorecard_count > 0:
            raise ValidationError(f"Cannot delete period with {scorecard_count} existing scorecards")

        self.db.delete(period)
        self.db.flush()

    def activate_period(self, period_id: int) -> EvaluationPeriod:
        """Activate a draft period."""
        period = self.get_period(period_id)

        if period.status != EvaluationPeriodStatus.DRAFT:
            raise ValidationError(f"Can only activate draft periods. Current status: {period.status.value}")

        period.status = EvaluationPeriodStatus.ACTIVE
        self.db.flush()
        return period

    def start_scoring(self, period_id: int) -> EvaluationPeriod:
        """Transition period to scoring phase."""
        period = self.get_period(period_id)

        if period.status not in [EvaluationPeriodStatus.ACTIVE, EvaluationPeriodStatus.SCORING]:
            raise ValidationError(f"Can only start scoring for active periods. Current status: {period.status.value}")

        period.status = EvaluationPeriodStatus.SCORING
        self.db.flush()
        return period

    def start_review(self, period_id: int) -> EvaluationPeriod:
        """Transition period to review phase."""
        period = self.get_period(period_id)

        if period.status != EvaluationPeriodStatus.SCORING:
            raise ValidationError(f"Can only start review after scoring. Current status: {period.status.value}")

        period.status = EvaluationPeriodStatus.REVIEW
        self.db.flush()
        return period

    def finalize_period(self, period_id: int) -> Dict[str, Any]:
        """Finalize period and lock all scorecards."""
        period = self.get_period(period_id)

        if period.status != EvaluationPeriodStatus.REVIEW:
            raise ValidationError(f"Can only finalize periods in review. Current status: {period.status.value}")

        # Mark all scorecards as finalized
        updated = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.COMPUTED,
                ScorecardInstanceStatus.IN_REVIEW,
                ScorecardInstanceStatus.APPROVED,
                'computed', 'in_review', 'approved'
            ])
        ).update(
            {
                "status": ScorecardInstanceStatus.FINALIZED,
                "finalized_at": datetime.now(timezone.utc),
            },
            synchronize_session=False
        )

        period.status = EvaluationPeriodStatus.FINALIZED
        self.db.flush()

        return {"finalized_count": updated}
