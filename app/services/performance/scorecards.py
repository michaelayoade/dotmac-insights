"""Scorecard Instance Service."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.performance import (
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    EvaluationPeriod,
    ScorecardTemplate,
    KRAResult,
    KPIResult,
    ScoreOverride,
    OverrideReason,
)
from app.models.employee import Employee
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError

from .types import ScorecardFilters


class ScorecardService:
    """Service for scorecard instance management."""

    def __init__(self, db: Session):
        self.db = db

    def list_scorecards(
        self,
        filters: ScorecardFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[EmployeeScorecardInstance]:
        """List scorecard instances with filtering and pagination."""
        query = self.db.query(EmployeeScorecardInstance)

        if filters.employee_id:
            query = query.filter(EmployeeScorecardInstance.employee_id == filters.employee_id)

        if filters.period_id:
            query = query.filter(EmployeeScorecardInstance.evaluation_period_id == filters.period_id)

        if filters.status:
            try:
                status_enum = ScorecardInstanceStatus(filters.status)
                query = query.filter(EmployeeScorecardInstance.status == status_enum)
            except ValueError:
                # Try string match
                query = query.filter(EmployeeScorecardInstance.status == filters.status)

        if filters.department:
            # Join with Employee to filter by department
            query = query.join(Employee, Employee.id == EmployeeScorecardInstance.employee_id)
            query = query.filter(Employee.department == filters.department)

        if filters.min_score is not None:
            query = query.filter(EmployeeScorecardInstance.total_weighted_score >= filters.min_score)

        if filters.max_score is not None:
            query = query.filter(EmployeeScorecardInstance.total_weighted_score <= filters.max_score)

        total = query.count()

        # Apply sorting
        sort_column = getattr(EmployeeScorecardInstance, filters.sort_by, EmployeeScorecardInstance.created_at)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        scorecards = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=scorecards, total=total)

    def get_scorecard(self, scorecard_id: int) -> EmployeeScorecardInstance:
        """Get a scorecard by ID."""
        scorecard = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.id == scorecard_id
        ).first()
        if not scorecard:
            raise NotFoundError(f"Scorecard {scorecard_id} not found")
        return scorecard

    def get_scorecard_detail(self, scorecard_id: int) -> Dict[str, Any]:
        """Get detailed scorecard information with related data."""
        scorecard = self.get_scorecard(scorecard_id)

        # Get employee info
        employee = self.db.query(Employee).filter(
            Employee.id == scorecard.employee_id
        ).first()

        # Get period info
        period = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == scorecard.evaluation_period_id
        ).first()

        # Get template info
        template = None
        if scorecard.template_id:
            template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.id == scorecard.template_id
            ).first()

        # Get KRA results
        kra_results = self.db.query(KRAResult).filter(
            KRAResult.scorecard_instance_id == scorecard_id
        ).all()

        # Get KPI results for each KRA
        kra_data = []
        for kra_result in kra_results:
            kpi_results = self.db.query(KPIResult).filter(
                KPIResult.kra_result_id == kra_result.id
            ).all()
            kra_data.append({
                "kra_result": kra_result,
                "kpi_results": kpi_results,
            })

        # Get overrides
        overrides = self.db.query(ScoreOverride).filter(
            ScoreOverride.scorecard_instance_id == scorecard_id
        ).all()

        return {
            "scorecard": scorecard,
            "employee": employee,
            "period": period,
            "template": template,
            "kra_data": kra_data,
            "overrides": overrides,
        }

    def create_scorecard(
        self,
        employee_id: int,
        period_id: int,
        template_id: Optional[int] = None,
    ) -> EmployeeScorecardInstance:
        """Create a new scorecard instance."""
        # Verify employee exists
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            raise NotFoundError(f"Employee {employee_id} not found")

        # Verify period exists
        period = self.db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
        if not period:
            raise NotFoundError(f"Period {period_id} not found")

        # Check for existing scorecard
        existing = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.employee_id == employee_id,
            EmployeeScorecardInstance.evaluation_period_id == period_id,
        ).first()
        if existing:
            raise ValidationError(f"Scorecard already exists for employee {employee_id} in period {period_id}")

        # Get template if not provided
        if template_id:
            template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.id == template_id
            ).first()
            if not template:
                raise NotFoundError(f"Template {template_id} not found")
        else:
            template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.is_default == True,
                ScorecardTemplate.is_active == True,
            ).first()
            template_id = template.id if template else None

        scorecard = EmployeeScorecardInstance(
            employee_id=employee_id,
            evaluation_period_id=period_id,
            template_id=template_id,
            status=ScorecardInstanceStatus.PENDING,
        )
        self.db.add(scorecard)
        self.db.flush()
        return scorecard

    def update_status(
        self,
        scorecard_id: int,
        new_status: str,
    ) -> EmployeeScorecardInstance:
        """Update scorecard status."""
        scorecard = self.get_scorecard(scorecard_id)

        try:
            status_enum = ScorecardInstanceStatus(new_status)
        except ValueError:
            raise ValidationError(f"Invalid status: {new_status}")

        scorecard.status = status_enum

        if status_enum == ScorecardInstanceStatus.FINALIZED:
            scorecard.finalized_at = datetime.now(timezone.utc)

        self.db.flush()
        return scorecard

    def submit_for_review(self, scorecard_id: int) -> EmployeeScorecardInstance:
        """Submit a scorecard for review."""
        scorecard = self.get_scorecard(scorecard_id)

        if scorecard.status not in [ScorecardInstanceStatus.COMPUTED, 'computed']:
            raise ValidationError("Scorecard must be computed before submitting for review")

        scorecard.status = ScorecardInstanceStatus.IN_REVIEW
        self.db.flush()
        return scorecard

    def approve(self, scorecard_id: int) -> EmployeeScorecardInstance:
        """Approve a scorecard."""
        scorecard = self.get_scorecard(scorecard_id)

        if scorecard.status not in [ScorecardInstanceStatus.IN_REVIEW, 'in_review']:
            raise ValidationError("Scorecard must be in review before approving")

        scorecard.status = ScorecardInstanceStatus.APPROVED
        self.db.flush()
        return scorecard

    def finalize(self, scorecard_id: int, user_id: Optional[int] = None) -> EmployeeScorecardInstance:
        """Finalize a scorecard."""
        scorecard = self.get_scorecard(scorecard_id)

        valid_statuses = [
            ScorecardInstanceStatus.APPROVED,
            ScorecardInstanceStatus.IN_REVIEW,
            'approved', 'in_review'
        ]

        if scorecard.status not in valid_statuses:
            raise ValidationError(f"Cannot finalize scorecard in {scorecard.status} status")

        scorecard.status = ScorecardInstanceStatus.FINALIZED
        scorecard.finalized_at = datetime.now(timezone.utc)
        if user_id:
            scorecard.finalized_by_id = user_id

        self.db.flush()
        return scorecard

    def apply_override(
        self,
        scorecard_id: int,
        override_type: str,
        target_id: Optional[int],
        new_score: float,
        reason: str,
        justification: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Apply a score override with audit trail."""
        scorecard = self.get_scorecard(scorecard_id)

        original_score = None

        if override_type == 'kpi':
            kpi_result = self.db.query(KPIResult).filter(KPIResult.id == target_id).first()
            if not kpi_result:
                raise NotFoundError("KPI result not found")
            original_score = kpi_result.final_score or kpi_result.computed_score
            kpi_result.final_score = Decimal(str(new_score))

        elif override_type == 'kra':
            kra_result = self.db.query(KRAResult).filter(KRAResult.id == target_id).first()
            if not kra_result:
                raise NotFoundError("KRA result not found")
            original_score = kra_result.final_score or kra_result.computed_score
            kra_result.final_score = Decimal(str(new_score))

        elif override_type == 'overall':
            original_score = scorecard.total_weighted_score
            scorecard.total_weighted_score = Decimal(str(new_score))

        else:
            raise ValidationError("Invalid override type")

        # Create audit record
        try:
            reason_enum = OverrideReason(reason)
        except ValueError:
            raise ValidationError(f"Invalid override reason: {reason}")

        override = ScoreOverride(
            scorecard_instance_id=scorecard_id,
            override_type=override_type,
            kpi_result_id=target_id if override_type == 'kpi' else None,
            kra_result_id=target_id if override_type == 'kra' else None,
            original_score=original_score,
            overridden_score=Decimal(str(new_score)),
            reason=reason_enum,
            justification=justification,
            overridden_by_id=user_id,
        )
        self.db.add(override)
        self.db.flush()

        return {"override_id": override.id}

    def delete_scorecard(self, scorecard_id: int) -> None:
        """Delete a scorecard (only if pending)."""
        scorecard = self.get_scorecard(scorecard_id)

        if scorecard.status not in [ScorecardInstanceStatus.PENDING, 'pending']:
            raise ValidationError("Can only delete pending scorecards")

        # Delete related results
        kra_results = self.db.query(KRAResult).filter(
            KRAResult.scorecard_instance_id == scorecard_id
        ).all()
        for kra_result in kra_results:
            self.db.query(KPIResult).filter(
                KPIResult.kra_result_id == kra_result.id
            ).delete()
        self.db.query(KRAResult).filter(
            KRAResult.scorecard_instance_id == scorecard_id
        ).delete()

        self.db.delete(scorecard)
        self.db.flush()

    def get_employee_scorecards(
        self,
        employee_id: int,
        limit: int = 10,
    ) -> List[EmployeeScorecardInstance]:
        """Get scorecards for an employee."""
        return self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.employee_id == employee_id
        ).order_by(EmployeeScorecardInstance.created_at.desc()).limit(limit).all()

    def get_pending_reviews(
        self,
        period_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[EmployeeScorecardInstance]:
        """Get scorecards pending review."""
        query = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.COMPUTED,
                ScorecardInstanceStatus.IN_REVIEW,
                'computed', 'in_review'
            ])
        )

        if period_id:
            query = query.filter(EmployeeScorecardInstance.evaluation_period_id == period_id)

        return query.order_by(EmployeeScorecardInstance.updated_at.desc()).limit(limit).all()
