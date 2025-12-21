"""
Performance Service - Business logic for performance management

Handles scorecard generation, team queries, finalization, and analytics.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.models.performance import (
    EvaluationPeriod,
    EvaluationPeriodStatus,
    ScorecardTemplate,
    ScorecardTemplateItem,
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    KRAResult,
    KPIResult,
    PerformanceSnapshot,
    BonusPolicy,
)
from app.models.employee import Employee, EmploymentStatus
from app.models.auth import User

logger = logging.getLogger(__name__)


class PerformanceService:
    """Service for performance management business logic."""

    def __init__(self, db: Session):
        self.db = db

    def generate_scorecards(
        self,
        period_id: int,
        employee_ids: Optional[List[int]] = None,
        template_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate scorecards for employees in a period.

        Args:
            period_id: Evaluation period ID
            employee_ids: Optional list of employee IDs (None = all active)
            template_id: Optional template ID (None = use default/auto-match)

        Returns:
            Dict with created, skipped counts and any errors
        """
        period = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == period_id
        ).first()

        if not period:
            return {"success": False, "error": "Period not found"}

        # Get template
        template = None
        if template_id:
            template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.id == template_id,
                ScorecardTemplate.is_active == True
            ).first()
        else:
            template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.is_default == True,
                ScorecardTemplate.is_active == True
            ).first()

        if not template:
            return {"success": False, "error": "No valid template found"}

        # Get employees
        if employee_ids:
            employees = self.db.query(Employee).filter(Employee.id.in_(employee_ids)).all()
        else:
            employees = self.db.query(Employee).filter(Employee.status == EmploymentStatus.ACTIVE).all()

        created = 0
        skipped = 0
        errors = []

        for emp in employees:
            # Check if scorecard already exists
            existing = self.db.query(EmployeeScorecardInstance).filter(
                EmployeeScorecardInstance.employee_id == emp.id,
                EmployeeScorecardInstance.evaluation_period_id == period_id
            ).first()

            if existing:
                skipped += 1
                continue

            try:
                # Try to match template by department/designation
                matched_template = self._match_template(emp, template)

                scorecard = EmployeeScorecardInstance(
                    employee_id=emp.id,
                    evaluation_period_id=period_id,
                    template_id=matched_template.id,
                    status=ScorecardInstanceStatus.PENDING,
                )
                self.db.add(scorecard)
                created += 1

            except Exception as e:
                errors.append({"employee_id": emp.id, "error": str(e)})

        self.db.commit()

        return {
            "success": True,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    def _match_template(self, employee: Employee, default_template: ScorecardTemplate) -> ScorecardTemplate:
        """
        Find best matching template for employee based on department/designation.
        Falls back to default template.
        """
        # Try to find department-specific template
        if employee.department:
            dept_template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.is_active == True,
                ScorecardTemplate.applicable_departments.contains([employee.department])
            ).first()

            if dept_template:
                return dept_template

        # Try designation-specific template
        if employee.designation:
            desig_template = self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.is_active == True,
                ScorecardTemplate.applicable_designations.contains([employee.designation])
            ).first()

            if desig_template:
                return desig_template

        return default_template

    def get_manager_review_queue(
        self,
        manager_id: int,
        period_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get scorecards pending review for a manager's direct/indirect reports.

        Args:
            manager_id: The manager's user/employee ID
            period_id: Optional period filter

        Returns:
            List of scorecard summaries for review
        """
        # TODO: Implement manager relationship lookup
        # For now, return all in_review scorecards

        query = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.COMPUTED,
                ScorecardInstanceStatus.IN_REVIEW,
                'computed',
                'in_review'
            ])
        )

        if period_id:
            query = query.filter(EmployeeScorecardInstance.evaluation_period_id == period_id)

        scorecards = query.all()

        result = []
        for sc in scorecards:
            emp = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()
            period = self.db.query(EvaluationPeriod).filter(
                EvaluationPeriod.id == sc.evaluation_period_id
            ).first()

            result.append({
                "scorecard_id": sc.id,
                "employee_id": sc.employee_id,
                "employee_name": emp.name if emp else "Unknown",
                "department": emp.department if emp else None,
                "period_name": period.name if period else "",
                "status": sc.status.value if hasattr(sc.status, 'value') else sc.status,
                "total_score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
                "submitted_at": sc.updated_at,
            })

        return result

    def apply_override(
        self,
        scorecard_id: int,
        override_type: str,  # 'kpi', 'kra', or 'overall'
        target_id: Optional[int],  # kpi_result_id or kra_result_id
        new_score: float,
        reason: str,
        justification: str,
        user: User,
    ) -> Dict[str, Any]:
        """
        Apply a score override with audit trail.
        """
        from app.models.performance import ScoreOverride, OverrideReason

        scorecard = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.id == scorecard_id
        ).first()

        if not scorecard:
            return {"success": False, "error": "Scorecard not found"}

        original_score = None

        if override_type == 'kpi':
            kpi_result = self.db.query(KPIResult).filter(KPIResult.id == target_id).first()
            if not kpi_result:
                return {"success": False, "error": "KPI result not found"}
            original_score = kpi_result.final_score or kpi_result.computed_score
            kpi_result.final_score = Decimal(str(new_score))

        elif override_type == 'kra':
            kra_result = self.db.query(KRAResult).filter(KRAResult.id == target_id).first()
            if not kra_result:
                return {"success": False, "error": "KRA result not found"}
            original_score = kra_result.final_score or kra_result.computed_score
            kra_result.final_score = Decimal(str(new_score))

        elif override_type == 'overall':
            original_score = scorecard.total_weighted_score
            scorecard.total_weighted_score = Decimal(str(new_score))

        else:
            return {"success": False, "error": "Invalid override type"}

        # Create audit record
        override = ScoreOverride(
            scorecard_instance_id=scorecard_id,
            override_type=override_type,
            kpi_result_id=target_id if override_type == 'kpi' else None,
            kra_result_id=target_id if override_type == 'kra' else None,
            original_score=original_score,
            overridden_score=Decimal(str(new_score)),
            reason=OverrideReason(reason),
            justification=justification,
            overridden_by_id=user.id if user else None,
        )
        self.db.add(override)
        self.db.commit()

        return {"success": True, "override_id": override.id}

    def finalize_scorecard(
        self,
        scorecard_id: int,
        user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Finalize a scorecard (lock it from further changes).
        """
        scorecard = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.id == scorecard_id
        ).first()

        if not scorecard:
            return {"success": False, "error": "Scorecard not found"}

        valid_statuses = [
            ScorecardInstanceStatus.APPROVED,
            'approved',
            ScorecardInstanceStatus.IN_REVIEW,
            'in_review'
        ]

        if scorecard.status not in valid_statuses:
            return {
                "success": False,
                "error": f"Cannot finalize scorecard in {scorecard.status} status"
            }

        scorecard.status = ScorecardInstanceStatus.FINALIZED
        scorecard.finalized_at = datetime.utcnow()
        if user:
            scorecard.finalized_by_id = user.id

        self.db.commit()

        return {"success": True, "scorecard_id": scorecard_id}

    def finalize_period(
        self,
        period_id: int,
        user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Finalize all scorecards in a period.
        """
        period = self.db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == period_id
        ).first()

        if not period:
            return {"success": False, "error": "Period not found"}

        # Finalize all approved/in_review scorecards
        updated = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status.in_([
                ScorecardInstanceStatus.APPROVED,
                ScorecardInstanceStatus.IN_REVIEW,
                ScorecardInstanceStatus.COMPUTED,
                'approved',
                'in_review',
                'computed'
            ])
        ).update(
            {
                "status": ScorecardInstanceStatus.FINALIZED,
                "finalized_at": datetime.utcnow(),
                "finalized_by_id": user.id if user else None,
            },
            synchronize_session=False
        )

        period.status = EvaluationPeriodStatus.FINALIZED
        self.db.commit()

        return {"success": True, "finalized_count": updated}

    def generate_snapshots(self, period_id: int) -> Dict[str, Any]:
        """
        Generate denormalized performance snapshots for analytics.
        """
        # Get all finalized scorecards
        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.FINALIZED
        ).all()

        created = 0

        for sc in scorecards:
            # Check if snapshot exists
            existing = self.db.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.employee_id == sc.employee_id,
                PerformanceSnapshot.evaluation_period_id == period_id
            ).first()

            if existing:
                continue

            emp = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()

            # Get KRA scores
            kra_results = self.db.query(KRAResult).filter(
                KRAResult.scorecard_instance_id == sc.id
            ).all()

            kra_scores = {}
            for kr in kra_results:
                from app.models.performance import KRADefinition
                kra = self.db.query(KRADefinition).filter(KRADefinition.id == kr.kra_id).first()
                if kra:
                    kra_scores[kra.code] = float(kr.final_score or kr.computed_score or 0)

            snapshot = PerformanceSnapshot(
                employee_id=sc.employee_id,
                evaluation_period_id=period_id,
                department_id=None,  # TODO: Map department string to ID
                employee_name=emp.name if emp else None,
                final_score=sc.total_weighted_score,
                final_rating=sc.final_rating,
                kra_scores=kra_scores,
            )
            self.db.add(snapshot)
            created += 1

        self.db.commit()

        return {"success": True, "snapshots_created": created}

    def get_team_members(
        self,
        manager_id: int,
        include_indirect: bool = True,
        max_depth: int = 5,
    ) -> List[Employee]:
        """
        Get all team members reporting to a manager.

        Args:
            manager_id: The manager's employee ID
            include_indirect: Include indirect reports (reports of reports)
            max_depth: Maximum hierarchy depth to traverse

        Returns:
            List of Employee objects
        """
        team_members = []
        visited = set()

        def collect_reports(emp_id: int, depth: int = 0):
            if depth >= max_depth or emp_id in visited:
                return
            visited.add(emp_id)

            direct_reports = self.db.query(Employee).filter(
                Employee.reports_to_id == emp_id,
                Employee.status == EmploymentStatus.ACTIVE
            ).all()

            for report in direct_reports:
                team_members.append(report)
                if include_indirect:
                    collect_reports(report.id, depth + 1)

        collect_reports(manager_id)
        return team_members

    def get_team_performance(
        self,
        manager_id: int,
        period_id: int,
        include_indirect: bool = True,
    ) -> Dict[str, Any]:
        """
        Get aggregated performance data for a manager's team.

        Args:
            manager_id: The manager's employee ID
            period_id: Evaluation period ID
            include_indirect: Include indirect reports

        Returns:
            Dict with team performance summary
        """
        # Get manager info
        manager = self.db.query(Employee).filter(Employee.id == manager_id).first()
        if not manager:
            return {"success": False, "error": "Manager not found"}

        # Get team members
        team_members = self.get_team_members(manager_id, include_indirect)
        team_employee_ids = [e.id for e in team_members]

        if not team_employee_ids:
            return {
                "success": True,
                "manager_id": manager_id,
                "manager_name": manager.name,
                "period_id": period_id,
                "team_size": 0,
                "message": "No direct reports found",
            }

        # Get scorecards for team
        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.employee_id.in_(team_employee_ids)
        ).all()

        # Calculate stats
        scored = [sc for sc in scorecards if sc.total_weighted_score is not None]
        scores = [float(sc.total_weighted_score) for sc in scored if sc.total_weighted_score is not None]

        status_counts = {
            "pending": 0,
            "computing": 0,
            "computed": 0,
            "in_review": 0,
            "approved": 0,
            "finalized": 0,
        }
        for sc in scorecards:
            status = sc.status.value if hasattr(sc.status, 'value') else str(sc.status)
            if status in status_counts:
                status_counts[status] += 1

        # Score distribution
        distribution = {
            "outstanding": len([s for s in scores if s >= 85]),
            "exceeds": len([s for s in scores if 70 <= s < 85]),
            "meets": len([s for s in scores if 50 <= s < 70]),
            "below": len([s for s in scores if s < 50]),
        }

        # Team member details
        team_details = []
        for sc in scorecards:
            emp = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()
            team_details.append({
                "employee_id": sc.employee_id,
                "employee_name": emp.name if emp else "Unknown",
                "department": emp.department if emp else None,
                "designation": emp.designation if emp else None,
                "scorecard_id": sc.id,
                "status": sc.status.value if hasattr(sc.status, 'value') else str(sc.status),
                "score": float(sc.total_weighted_score) if sc.total_weighted_score else None,
                "rating": sc.final_rating,
            })

        # Sort by score descending
        team_details.sort(key=lambda x: x["score"] or 0, reverse=True)  # type: ignore[arg-type, return-value]

        return {
            "success": True,
            "manager_id": manager_id,
            "manager_name": manager.name,
            "period_id": period_id,
            "team_size": len(team_employee_ids),
            "scorecards_generated": len(scorecards),
            "scorecards_scored": len(scored),
            "stats": {
                "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
                "min_score": round(min(scores), 2) if scores else None,
                "max_score": round(max(scores), 2) if scores else None,
                "median_score": round(sorted(scores)[len(scores) // 2], 2) if scores else None,
            },
            "status_counts": status_counts,
            "distribution": distribution,
            "pending_reviews": status_counts["computed"] + status_counts["in_review"],
            "team_details": team_details,
        }

    def get_manager_hierarchy(
        self,
        employee_id: int,
        max_depth: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get the reporting chain (managers) above an employee.

        Returns list from immediate manager up to top.
        """
        hierarchy = []
        current_id = employee_id
        depth = 0

        while depth < max_depth:
            emp = self.db.query(Employee).filter(Employee.id == current_id).first()
            if not emp or not emp.reports_to_id:
                break

            manager = self.db.query(Employee).filter(Employee.id == emp.reports_to_id).first()
            if not manager:
                break

            hierarchy.append({
                "level": depth + 1,
                "employee_id": manager.id,
                "name": manager.name,
                "designation": manager.designation,
                "department": manager.department,
            })

            current_id = manager.id
            depth += 1

        return hierarchy

    def get_org_tree_performance(
        self,
        root_manager_id: int,
        period_id: int,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get hierarchical org tree with performance data.

        Useful for visualizing team structures with scores.
        """
        def build_tree(emp_id: int, depth: int = 0) -> Optional[Dict[str, Any]]:
            emp = self.db.query(Employee).filter(Employee.id == emp_id).first()
            if not emp:
                return None

            # Get scorecard for this employee
            scorecard = self.db.query(EmployeeScorecardInstance).filter(
                EmployeeScorecardInstance.employee_id == emp_id,
                EmployeeScorecardInstance.evaluation_period_id == period_id
            ).first()

            node: Dict[str, Any] = {
                "employee_id": emp.id,
                "name": emp.name,
                "designation": emp.designation,
                "department": emp.department,
                "score": float(scorecard.total_weighted_score) if scorecard and scorecard.total_weighted_score else None,
                "rating": scorecard.final_rating if scorecard else None,
                "status": scorecard.status.value if scorecard and hasattr(scorecard.status, 'value') else (str(scorecard.status) if scorecard else None),
                "children": [],
            }

            if depth < max_depth:
                direct_reports = self.db.query(Employee).filter(
                    Employee.reports_to_id == emp_id,
                    Employee.status == EmploymentStatus.ACTIVE
                ).all()

                for report in direct_reports:
                    child_node = build_tree(report.id, depth + 1)
                    if child_node:
                        node["children"].append(child_node)

            # Calculate aggregate for this node
            if node["children"]:
                child_scores = [c["score"] for c in node["children"] if c["score"] is not None]
                node["team_avg"] = round(sum(child_scores) / len(child_scores), 2) if child_scores else None
                node["team_size"] = len(node["children"])

            return node

        return build_tree(root_manager_id) or {}

    def get_department_ranking(
        self,
        period_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Rank departments by average performance score.
        """
        results = self.db.query(
            Employee.department,
            func.count(EmployeeScorecardInstance.id).label('count'),
            func.avg(EmployeeScorecardInstance.total_weighted_score).label('avg_score'),
            func.min(EmployeeScorecardInstance.total_weighted_score).label('min_score'),
            func.max(EmployeeScorecardInstance.total_weighted_score).label('max_score'),
        ).join(
            EmployeeScorecardInstance, EmployeeScorecardInstance.employee_id == Employee.id
        ).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.total_weighted_score.isnot(None)
        ).group_by(Employee.department).all()

        ranked = [
            {
                "rank": 0,  # Will be set below
                "department": r.department or "Unassigned",
                "employee_count": r.count,
                "avg_score": float(r.avg_score) if r.avg_score else 0,
                "min_score": float(r.min_score) if r.min_score else 0,
                "max_score": float(r.max_score) if r.max_score else 0,
            }
            for r in results
        ]

        # Sort by avg score descending and assign rank
        ranked.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, dept in enumerate(ranked):
            dept["rank"] = i + 1

        return ranked

    def calculate_bonus_eligibility(
        self,
        period_id: int,
        policy_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate bonus eligibility based on performance and bonus policy.
        """
        # Get policy
        if policy_id:
            policy = self.db.query(BonusPolicy).filter(BonusPolicy.id == policy_id).first()
        else:
            policy = self.db.query(BonusPolicy).filter(BonusPolicy.is_active == True).first()

        if not policy:
            return []

        raw_score_bands: Any = policy.score_bands or []
        score_bands: List[Dict[str, Any]] = raw_score_bands if isinstance(raw_score_bands, list) else []

        # Get finalized scorecards
        scorecards = self.db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.evaluation_period_id == period_id,
            EmployeeScorecardInstance.status == ScorecardInstanceStatus.FINALIZED,
            EmployeeScorecardInstance.total_weighted_score.isnot(None)
        ).all()

        results = []
        for sc in scorecards:
            emp = self.db.query(Employee).filter(Employee.id == sc.employee_id).first()
            if not emp:
                continue

            score = float(sc.total_weighted_score) if sc.total_weighted_score else 0
            bonus_factor = 0
            bonus_band = "Below Threshold"

            for band in score_bands:
                if band.get('min', 0) <= score <= band.get('max', 100):
                    bonus_factor = band.get('factor', 0)
                    bonus_band = band.get('label', 'Unknown')
                    break

            results.append({
                "employee_id": sc.employee_id,
                "employee_name": emp.name,
                "department": emp.department,
                "final_score": score,
                "rating": sc.final_rating,
                "bonus_factor": bonus_factor,
                "bonus_band": bonus_band,
            })

        return results
