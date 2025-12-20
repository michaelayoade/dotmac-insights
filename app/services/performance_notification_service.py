"""Performance Notification Service - Handles notifications for performance management.

Integrates with the main NotificationService to emit performance-related events
like scorecard generation, review requests, approvals, and scheduled reports.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, cast

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.notification import NotificationEventType
from app.models.performance import (
    EvaluationPeriod,
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    KRAResult,
)
from app.models.employee import Employee
from app.models.auth import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class PerformanceNotificationService:
    """Service for handling performance-related notifications."""

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def _get_user_id_for_employee(self, employee: Optional[Employee]) -> Optional[int]:
        """Resolve a user_id for an employee via direct link or email lookup."""
        if not employee:
            return None
        user_id = cast(Optional[int], getattr(employee, "user_id", None))
        if user_id:
            return user_id
        if employee.email:
            user = self.db.query(User).filter(User.email == employee.email).first()
            if user:
                return user.id
        return None

    def notify_period_started(self, period: EvaluationPeriod) -> Dict[str, Any]:
        """Notify all employees that an evaluation period has started."""
        # Get all active employees
        employees = self.db.query(Employee).filter(Employee.status == 'Active').all()
        user_ids = []
        for emp in employees:
            uid = self._get_user_id_for_employee(emp)
            if uid:
                user_ids.append(uid)

        if not user_ids:
            return {"success": False, "message": "No users to notify"}

        payload = {
            "period_id": period.id,
            "period_code": period.code,
            "period_name": period.name,
            "start_date": period.start_date.isoformat() if period.start_date else None,
            "end_date": period.end_date.isoformat() if period.end_date else None,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_PERIOD_STARTED,
            payload=payload,
            entity_type="evaluation_period",
            entity_id=period.id,
            user_ids=user_ids,
        )

    def notify_scorecard_generated(
        self, scorecard: EmployeeScorecardInstance, period: EvaluationPeriod
    ) -> Dict[str, Any]:
        """Notify employee that their scorecard has been generated."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORECARD_GENERATED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_scorecard_computed(
        self, scorecard: EmployeeScorecardInstance, period: EvaluationPeriod
    ) -> Dict[str, Any]:
        """Notify employee that their metrics have been calculated."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "score": float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None,
            "rating": scorecard.final_rating,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORECARD_COMPUTED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_review_requested(
        self,
        scorecard: EmployeeScorecardInstance,
        period: EvaluationPeriod,
        manager_user_id: int,
    ) -> Dict[str, Any]:
        """Notify manager that a scorecard is pending their review."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id if employee else None,
            "employee_name": employee.name if employee else "Unknown",
            "period_id": period.id,
            "period_name": period.name,
            "score": float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_REVIEW_REQUESTED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[manager_user_id],
        )

    def notify_scorecard_approved(
        self,
        scorecard: EmployeeScorecardInstance,
        period: EvaluationPeriod,
        reviewer: Optional[User],
    ) -> Dict[str, Any]:
        """Notify employee that their scorecard has been approved."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "reviewer_name": reviewer.name if reviewer else "Manager",
            "score": float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORECARD_APPROVED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_scorecard_rejected(
        self,
        scorecard: EmployeeScorecardInstance,
        period: EvaluationPeriod,
        reason: str,
    ) -> Dict[str, Any]:
        """Notify employee that their scorecard needs revision."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "reason": reason,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORECARD_REJECTED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_scorecard_finalized(
        self, scorecard: EmployeeScorecardInstance, period: EvaluationPeriod
    ) -> Dict[str, Any]:
        """Notify employee that their final rating has been assigned."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "score": float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None,
            "rating": scorecard.final_rating,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORECARD_FINALIZED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_score_overridden(
        self,
        scorecard: EmployeeScorecardInstance,
        period: EvaluationPeriod,
        old_score: float,
        new_score: float,
        reason: str,
    ) -> Dict[str, Any]:
        """Notify employee that a score on their scorecard was adjusted."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "old_score": old_score,
            "new_score": new_score,
            "reason": reason,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_SCORE_OVERRIDDEN,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    def notify_review_reminder(
        self, manager_user_id: int, pending_count: int, deadline: Optional[date] = None
    ) -> Dict[str, Any]:
        """Send reminder to manager about pending reviews."""
        payload = {
            "pending_count": pending_count,
            "deadline": deadline.isoformat() if deadline else None,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_REVIEW_REMINDER,
            payload=payload,
            user_ids=[manager_user_id],
        )

    def notify_period_closing(
        self, period: EvaluationPeriod, days_remaining: int
    ) -> Dict[str, Any]:
        """Notify users that an evaluation period is ending soon."""
        # Get managers/reviewers with pending reviews
        pending_scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period.id,
            EmployeeScorecardInstance.status.in_(['computed', 'in_review'])
        ).all()

        # Get unique reviewer IDs
        reviewer_ids = set()
        for sc in pending_scorecards:
            employee = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()
            if employee and employee.reports_to:
                manager = self.db.query(Employee).filter(
                    Employee.name == employee.reports_to
                ).first()
                manager_user_id = self._get_user_id_for_employee(manager)
                if manager_user_id:
                    reviewer_ids.add(manager_user_id)

        if not reviewer_ids:
            return {"success": False, "message": "No reviewers to notify"}

        payload = {
            "period_id": period.id,
            "period_code": period.code,
            "period_name": period.name,
            "end_date": period.end_date.isoformat() if period.end_date else None,
            "days_remaining": days_remaining,
            "pending_reviews": len(pending_scorecards),
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_PERIOD_CLOSING,
            payload=payload,
            entity_type="evaluation_period",
            entity_id=period.id,
            user_ids=list(reviewer_ids),
        )

    def send_weekly_summary(self, manager_user_id: int, period_id: int) -> Dict[str, Any]:
        """Send weekly performance summary to a manager."""
        period = self.db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
        if not period:
            return {"success": False, "message": "Period not found"}

        # Get manager's employees
        manager_user = self.db.query(User).filter(User.id == manager_user_id).first()
        if not manager_user:
            return {"success": False, "message": "Manager not found"}

        # Find employees reporting to this manager
        manager_employee = self.db.query(Employee).filter(Employee.email == manager_user.email).first()
        if not manager_employee:
            return {"success": False, "message": "Manager employee record not found"}

        team_employees = self.db.query(Employee).filter(
            Employee.reports_to == manager_employee.name,
            Employee.status == 'Active'
        ).all()

        team_employee_ids = [e.id for e in team_employees]

        # Get scorecard stats
        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.employee_id.in_(team_employee_ids)
        ).all()

        computed_count = len([s for s in scorecards if s.status in ['computed', 'in_review', 'approved', 'finalized']])
        pending_review = len([s for s in scorecards if s.status in ['computed', 'in_review']])
        finalized_count = len([s for s in scorecards if s.status == 'finalized'])

        avg_score = None
        scores = [
            float(s.total_weighted_score)
            for s in scorecards
            if s.total_weighted_score is not None
        ]
        if scores:
            avg_score = sum(scores) / len(scores)

        payload = {
            "period_id": period.id,
            "period_name": period.name,
            "team_size": len(team_employees),
            "computed_count": computed_count,
            "pending_review": pending_review,
            "finalized_count": finalized_count,
            "avg_score": round(avg_score, 2) if avg_score else None,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_WEEKLY_SUMMARY,
            payload=payload,
            entity_type="evaluation_period",
            entity_id=period.id,
            user_ids=[manager_user_id],
        )

    def notify_rating_published(
        self, scorecard: EmployeeScorecardInstance, period: EvaluationPeriod
    ) -> Dict[str, Any]:
        """Notify employee that their rating has been published and is viewable."""
        employee = self.db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        user_id = self._get_user_id_for_employee(employee)
        if not employee or not user_id:
            return {"success": False, "message": "Employee or user not found"}

        payload = {
            "scorecard_id": scorecard.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "period_id": period.id,
            "period_name": period.name,
            "score": float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None,
            "rating": scorecard.final_rating,
        }

        return self.notification_service.emit_event(
            event_type=NotificationEventType.PERF_RATING_PUBLISHED,
            payload=payload,
            entity_type="scorecard",
            entity_id=scorecard.id,
            user_ids=[user_id],
        )

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def send_bulk_review_reminders(self, period_id: int) -> Dict[str, Any]:
        """Send review reminders to all managers with pending reviews."""
        period = self.db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
        if not period:
            return {"success": False, "message": "Period not found"}

        # Get pending scorecards grouped by manager
        pending_scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_(['computed', 'in_review'])
        ).all()

        manager_counts: Dict[int, int] = {}
        for sc in pending_scorecards:
            employee = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()
            if employee and employee.reports_to:
                manager = self.db.query(Employee).filter(
                    Employee.name == employee.reports_to
                ).first()
                manager_user_id = self._get_user_id_for_employee(manager)
                if manager_user_id:
                    manager_counts[manager_user_id] = manager_counts.get(manager_user_id, 0) + 1

        errors: List[Dict[str, Any]] = []
        results: Dict[str, Any] = {
            "managers_notified": 0,
            "errors": errors,
        }

        for manager_id, count in manager_counts.items():
            try:
                self.notify_review_reminder(manager_id, count, period.review_deadline)
                results["managers_notified"] += 1
            except Exception as e:
                logger.error(f"Failed to send reminder to manager {manager_id}: {e}")
                results["errors"].append({"manager_id": manager_id, "error": str(e)})

        return results

    def generate_period_report_data(self, period_id: int) -> Dict[str, Any]:
        """Generate comprehensive report data for a period."""
        period = self.db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
        if not period:
            return {"error": "Period not found"}

        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id
        ).all()

        # Calculate stats
        total = len(scorecards)
        finalized = len([s for s in scorecards if s.status == 'finalized'])
        computed = len([s for s in scorecards if s.status in ['computed', 'in_review', 'approved', 'finalized']])

        scores = [float(s.total_weighted_score) for s in scorecards if s.total_weighted_score]
        avg_score = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 0

        # Rating distribution
        distribution = {
            "Outstanding": 0,
            "Exceeds Expectations": 0,
            "Meets Expectations": 0,
            "Below Expectations": 0,
        }
        for sc in scorecards:
            if sc.final_rating in distribution:
                distribution[sc.final_rating] += 1

        return {
            "period": {
                "id": period.id,
                "code": period.code,
                "name": period.name,
                "status": period.status.value if hasattr(period.status, 'value') else str(period.status),
                "start_date": period.start_date.isoformat() if period.start_date else None,
                "end_date": period.end_date.isoformat() if period.end_date else None,
            },
            "summary": {
                "total_scorecards": total,
                "computed": computed,
                "finalized": finalized,
                "pending": total - computed,
                "completion_rate": round((finalized / total * 100), 1) if total > 0 else 0,
            },
            "scores": {
                "average": round(avg_score, 2),
                "minimum": round(min_score, 2),
                "maximum": round(max_score, 2),
            },
            "distribution": distribution,
            "generated_at": datetime.utcnow().isoformat(),
        }
