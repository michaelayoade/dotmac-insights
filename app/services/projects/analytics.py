"""Analytics service for project analytics and dashboard.

This service handles:
- Dashboard metrics computation
- Status trends over time
- Task distribution analysis
- Project performance metrics
- Department summaries
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from app.models.project import (
    Project,
    ProjectStatus,
)
from app.models.task import Task, TaskStatus

from app.models.project import Milestone, MilestoneStatus

from .analytics_types import (
    AnalyticsFilters,
    AssigneeTaskStats,
    BudgetPerformance,
    DashboardData,
    DashboardStats,
    DepartmentSummary,
    PerformanceMetrics,
    ProfitabilityMetrics,
    StatusDistribution,
    StatusTrendPoint,
    TaskDistribution,
    TimelinePerformance,
    TopProject,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ProjectsAnalyticsService"]


class ProjectsAnalyticsService:
    """Service for computing project analytics and dashboard metrics.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for scoping if needed).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Dashboard Methods
    # -------------------------------------------------------------------------

    def get_dashboard_stats(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> DashboardStats:
        """Get comprehensive dashboard statistics.

        Args:
            filters: Optional filters for company/date range

        Returns:
            DashboardStats with project, task, and financial metrics
        """
        if filters is None:
            filters = AnalyticsFilters()

        # Build base query
        project_query = self.db.query(Project).filter(Project.is_deleted == False)
        if filters.company:
            project_query = project_query.filter(Project.company == filters.company)

        # Project counts by status
        project_by_status = self.db.query(
            Project.status,
            func.count(Project.id).label("count"),
        ).filter(Project.is_deleted == False)
        if filters.company:
            project_by_status = project_by_status.filter(
                Project.company == filters.company
            )
        project_by_status = project_by_status.group_by(Project.status).all()

        status_counts: Dict[str, int] = {
            row.status.value: int(row.count or 0) for row in project_by_status
        }
        total_projects = sum(status_counts.values())
        active_projects = status_counts.get("open", 0)

        # Projects by priority
        by_priority = (
            self.db.query(
                Project.priority,
                func.count(Project.id).label("count"),
            )
            .filter(
                Project.status == ProjectStatus.OPEN,
                Project.is_deleted == False,
            )
        )
        if filters.company:
            by_priority = by_priority.filter(Project.company == filters.company)
        by_priority = by_priority.group_by(Project.priority).all()

        priority_counts: Dict[str, int] = {
            row.priority.value: int(row.count or 0) for row in by_priority
        }

        # Task counts by status
        task_query = self.db.query(
            Task.status,
            func.count(Task.id).label("count"),
        )
        if filters.company:
            task_query = task_query.join(Project).filter(
                Project.company == filters.company
            )
        task_by_status = task_query.group_by(Task.status).all()

        task_status_counts: Dict[str, int] = {
            row.status.value: int(row.count or 0) for row in task_by_status
        }
        total_tasks = sum(task_status_counts.values())
        open_tasks = task_status_counts.get("open", 0) + task_status_counts.get(
            "working", 0
        )

        # Overdue tasks
        today = date.today()
        overdue_query = self.db.query(func.count(Task.id)).filter(
            Task.exp_end_date < today,
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
        )
        if filters.company:
            overdue_query = overdue_query.join(Project).filter(
                Project.company == filters.company
            )
        overdue_tasks = overdue_query.scalar() or 0

        # Project financials
        financials_base = self.db.query(Project).filter(Project.is_deleted == False)
        if filters.company:
            financials_base = financials_base.filter(Project.company == filters.company)

        total_estimated = (
            self.db.query(func.sum(Project.estimated_costing))
            .filter(Project.is_deleted == False)
        )
        if filters.company:
            total_estimated = total_estimated.filter(Project.company == filters.company)
        total_estimated = total_estimated.scalar() or Decimal("0")

        total_actual = (
            self.db.query(func.sum(Project.total_costing_amount))
            .filter(Project.is_deleted == False)
        )
        if filters.company:
            total_actual = total_actual.filter(Project.company == filters.company)
        total_actual = total_actual.scalar() or Decimal("0")

        total_billed = (
            self.db.query(func.sum(Project.total_billed_amount))
            .filter(Project.is_deleted == False)
        )
        if filters.company:
            total_billed = total_billed.filter(Project.company == filters.company)
        total_billed = total_billed.scalar() or Decimal("0")

        # Average completion
        avg_query = self.db.query(func.avg(Project.percent_complete)).filter(
            Project.status == ProjectStatus.OPEN,
            Project.is_deleted == False,
        )
        if filters.company:
            avg_query = avg_query.filter(Project.company == filters.company)
        avg_completion = avg_query.scalar() or Decimal("0")

        # Projects due this week
        week_end = datetime.now(timezone.utc) + timedelta(days=7)
        due_query = self.db.query(func.count(Project.id)).filter(
            Project.expected_end_date <= week_end,
            Project.expected_end_date >= datetime.now(timezone.utc),
            Project.status == ProjectStatus.OPEN,
            Project.is_deleted == False,
        )
        if filters.company:
            due_query = due_query.filter(Project.company == filters.company)
        due_this_week = due_query.scalar() or 0

        return DashboardStats(
            total_projects=total_projects,
            active_projects=active_projects,
            completed_projects=status_counts.get("completed", 0),
            on_hold_projects=status_counts.get("on_hold", 0),
            cancelled_projects=status_counts.get("cancelled", 0),
            by_priority=priority_counts,
            total_tasks=total_tasks,
            open_tasks=open_tasks,
            completed_tasks=task_status_counts.get("completed", 0),
            overdue_tasks=overdue_tasks,
            total_estimated=float(total_estimated),
            total_actual_cost=float(total_actual),
            total_billed=float(total_billed),
            variance=float(total_estimated - total_actual),
            avg_completion_percent=round(float(avg_completion), 1),
            due_this_week=due_this_week,
            overdue_projects=0,  # Will be calculated in get_dashboard_data
            total_open_tasks=open_tasks,
        )

    def get_status_distribution(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[StatusDistribution]:
        """Get project count distribution by status.

        Args:
            filters: Optional filters for company/date range.

        Returns:
            List of StatusDistribution with status and count.
        """
        if filters is None:
            filters = AnalyticsFilters()

        query = self.db.query(
            Project.status,
            func.count(Project.id).label("count"),
        ).filter(Project.is_deleted == False)

        if filters.company:
            query = query.filter(Project.company == filters.company)

        results = query.group_by(Project.status).all()

        return [
            StatusDistribution(status=row.status.value, count=int(row.count or 0))
            for row in results
        ]

    def get_dashboard_data(
        self,
        recent_limit: int = 10,
        upcoming_days: int = 7,
        overdue_limit: int = 5,
    ) -> DashboardData:
        """Get complete dashboard data including stats and lists.

        This is the primary method for the projects dashboard page - it returns
        everything needed in a single call.

        Args:
            recent_limit: Max number of recent projects to return.
            upcoming_days: Days ahead to look for upcoming milestones.
            overdue_limit: Max number of overdue tasks to return.

        Returns:
            DashboardData with stats, status distribution, and lists.
        """
        today = date.today()
        week_from_now = today + timedelta(days=upcoming_days)

        # Get dashboard stats
        stats = self.get_dashboard_stats()

        # Status distribution
        status_distribution = self.get_status_distribution()

        # Recent projects
        recent_projects = (
            self.db.query(Project)
            .filter(Project.is_deleted == False)
            .order_by(Project.updated_at.desc())
            .limit(recent_limit)
            .all()
        )

        # Upcoming milestones
        upcoming_milestones = (
            self.db.query(Milestone)
            .filter(
                Milestone.is_deleted == False,
                Milestone.planned_end_date >= today,
                Milestone.planned_end_date <= week_from_now,
                Milestone.status != MilestoneStatus.COMPLETED,
            )
            .order_by(Milestone.planned_end_date)
            .limit(5)
            .all()
        )

        # Overdue tasks
        overdue_tasks = (
            self.db.query(Task)
            .filter(
                Task.exp_end_date < today,
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
            .order_by(Task.exp_end_date)
            .limit(overdue_limit)
            .all()
        )

        return DashboardData(
            stats=stats,
            status_distribution=status_distribution,
            recent_projects=recent_projects,
            upcoming_milestones=upcoming_milestones,
            overdue_tasks=overdue_tasks,
        )

    # -------------------------------------------------------------------------
    # Trend Analysis
    # -------------------------------------------------------------------------

    def get_status_trend(
        self,
        months: int = 12,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[StatusTrendPoint]:
        """Get monthly project creation and completion trend.

        Args:
            months: Number of months to analyze (max 24)
            filters: Optional filters

        Returns:
            List of StatusTrendPoint with monthly data
        """
        if filters is None:
            filters = AnalyticsFilters()

        months = min(months, 24)
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=months * 30)

        # Created projects by month
        created_query = self.db.query(
            extract("year", Project.created_at).label("year"),
            extract("month", Project.created_at).label("month"),
            func.count(Project.id).label("created"),
        ).filter(Project.created_at >= start_dt)
        if filters.company:
            created_query = created_query.filter(Project.company == filters.company)
        created = (
            created_query.group_by(
                extract("year", Project.created_at),
                extract("month", Project.created_at),
            ).all()
        )

        # Completed projects by month
        completed_query = self.db.query(
            extract("year", Project.actual_end_date).label("year"),
            extract("month", Project.actual_end_date).label("month"),
            func.count(Project.id).label("completed"),
        ).filter(
            Project.actual_end_date >= start_dt,
            Project.status == ProjectStatus.COMPLETED,
        )
        if filters.company:
            completed_query = completed_query.filter(Project.company == filters.company)
        completed = (
            completed_query.group_by(
                extract("year", Project.actual_end_date),
                extract("month", Project.actual_end_date),
            ).all()
        )

        # Merge data
        data_map: Dict[str, Dict[str, int]] = {}
        for c in created:
            key = f"{int(c.year)}-{int(c.month):02d}"
            data_map[key] = {
                "year": int(c.year),
                "month": int(c.month),
                "created": c.created,
                "completed": 0,
            }
        for c in completed:
            key = f"{int(c.year)}-{int(c.month):02d}"
            if key in data_map:
                data_map[key]["completed"] = c.completed
            else:
                data_map[key] = {
                    "year": int(c.year),
                    "month": int(c.month),
                    "created": 0,
                    "completed": c.completed,
                }

        # Convert to sorted list
        result = []
        for key in sorted(data_map.keys()):
            d = data_map[key]
            result.append(
                StatusTrendPoint(
                    period=key,
                    year=d["year"],
                    month=d["month"],
                    created=d["created"],
                    completed=d["completed"],
                )
            )
        return result

    # -------------------------------------------------------------------------
    # Task Distribution
    # -------------------------------------------------------------------------

    def get_task_distribution(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> TaskDistribution:
        """Get task distribution by status, priority, and assignee.

        Args:
            filters: Optional filters

        Returns:
            TaskDistribution with breakdown by status, priority, and assignee
        """
        if filters is None:
            filters = AnalyticsFilters()

        # By status
        status_query = self.db.query(
            Task.status,
            func.count(Task.id).label("count"),
        )
        if filters.company:
            status_query = status_query.join(Project).filter(
                Project.company == filters.company
            )
        by_status = status_query.group_by(Task.status).all()

        # By priority
        priority_query = self.db.query(
            Task.priority,
            func.count(Task.id).label("count"),
        )
        if filters.company:
            priority_query = priority_query.join(Project).filter(
                Project.company == filters.company
            )
        by_priority = priority_query.group_by(Task.priority).all()

        # By assignee (top 10)
        assignee_query = self.db.query(
            Task.assigned_to,
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label(
                "completed"
            ),
        ).filter(Task.assigned_to.isnot(None))
        if filters.company:
            assignee_query = assignee_query.join(Project).filter(
                Project.company == filters.company
            )
        by_assignee = (
            assignee_query.group_by(Task.assigned_to)
            .order_by(func.count(Task.id).desc())
            .limit(10)
            .all()
        )

        return TaskDistribution(
            by_status=[
                StatusDistribution(status=s.status.value, count=s.count)
                for s in by_status
            ],
            by_priority=[
                StatusDistribution(status=p.priority.value, count=p.count)
                for p in by_priority
            ],
            by_assignee=[
                AssigneeTaskStats(
                    assignee=a.assigned_to,
                    total=a.total,
                    completed=a.completed or 0,
                    completion_rate=(
                        round(a.completed / a.total * 100, 1)
                        if a.total > 0 and a.completed
                        else 0.0
                    ),
                )
                for a in by_assignee
            ],
        )

    # -------------------------------------------------------------------------
    # Performance Metrics
    # -------------------------------------------------------------------------

    def get_project_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> PerformanceMetrics:
        """Get project performance metrics including budget and timeline adherence.

        Args:
            filters: Optional filters

        Returns:
            PerformanceMetrics with budget, timeline, and profitability data
        """
        if filters is None:
            filters = AnalyticsFilters()

        # Budget performance (projects with both estimated and actual costs)
        budget_query = self.db.query(
            func.count(Project.id).label("total"),
            func.sum(
                case(
                    (Project.total_costing_amount <= Project.estimated_costing, 1),
                    else_=0,
                )
            ).label("under_budget"),
            func.sum(
                case(
                    (Project.total_costing_amount > Project.estimated_costing, 1),
                    else_=0,
                )
            ).label("over_budget"),
        ).filter(
            Project.estimated_costing > 0,
            Project.total_costing_amount > 0,
        )
        if filters.company:
            budget_query = budget_query.filter(Project.company == filters.company)
        budget_data = budget_query.first()

        # Timeline performance (completed projects)
        timeline_query = self.db.query(
            func.count(Project.id).label("total"),
            func.sum(
                case(
                    (Project.actual_end_date <= Project.expected_end_date, 1),
                    else_=0,
                )
            ).label("on_time"),
            func.sum(
                case(
                    (Project.actual_end_date > Project.expected_end_date, 1),
                    else_=0,
                )
            ).label("delayed"),
        ).filter(
            Project.status == ProjectStatus.COMPLETED,
            Project.expected_end_date.isnot(None),
            Project.actual_end_date.isnot(None),
        )
        if filters.company:
            timeline_query = timeline_query.filter(Project.company == filters.company)
        timeline_data = timeline_query.first()

        # Average project margin
        margin_query = self.db.query(func.avg(Project.per_gross_margin)).filter(
            Project.total_billed_amount > 0
        )
        if filters.company:
            margin_query = margin_query.filter(Project.company == filters.company)
        avg_margin = margin_query.scalar() or 0

        # Top profitable projects
        top_query = (
            self.db.query(Project)
            .filter(Project.gross_margin > 0)
        )
        if filters.company:
            top_query = top_query.filter(Project.company == filters.company)
        top_projects = (
            top_query.order_by(Project.gross_margin.desc())
            .limit(5)
            .all()
        )

        # Build budget performance
        budget_total = budget_data.total if budget_data else 0
        budget_under = budget_data.under_budget if budget_data else 0
        budget_over = budget_data.over_budget if budget_data else 0

        budget = BudgetPerformance(
            total_analyzed=budget_total,
            under_budget=budget_under or 0,
            over_budget=budget_over or 0,
            adherence_rate=(
                round(budget_under / budget_total * 100, 1)
                if budget_total > 0 and budget_under
                else 0.0
            ),
        )

        # Build timeline performance
        timeline_total = timeline_data.total if timeline_data else 0
        timeline_on_time = timeline_data.on_time if timeline_data else 0
        timeline_delayed = timeline_data.delayed if timeline_data else 0

        timeline = TimelinePerformance(
            total_analyzed=timeline_total,
            on_time=timeline_on_time or 0,
            delayed=timeline_delayed or 0,
            on_time_rate=(
                round(timeline_on_time / timeline_total * 100, 1)
                if timeline_total > 0 and timeline_on_time
                else 0.0
            ),
        )

        # Build profitability metrics
        profitability = ProfitabilityMetrics(
            avg_margin_percent=round(float(avg_margin), 1),
            top_projects=[
                TopProject(
                    id=p.id,
                    project_name=p.project_name,
                    gross_margin=float(p.gross_margin),
                    margin_percent=float(p.per_gross_margin),
                )
                for p in top_projects
            ],
        )

        return PerformanceMetrics(
            budget=budget,
            timeline=timeline,
            profitability=profitability,
        )

    # -------------------------------------------------------------------------
    # Department Summary
    # -------------------------------------------------------------------------

    def get_department_summary(
        self,
        limit: int = 15,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[DepartmentSummary]:
        """Get project and task summary by department.

        Args:
            limit: Maximum number of departments to return
            filters: Optional filters

        Returns:
            List of DepartmentSummary with metrics per department
        """
        if filters is None:
            filters = AnalyticsFilters()

        summary_query = self.db.query(
            Project.department,
            func.count(Project.id).label("project_count"),
            func.sum(Project.estimated_costing).label("total_estimated"),
            func.sum(Project.total_billed_amount).label("total_billed"),
            func.avg(Project.percent_complete).label("avg_completion"),
        ).filter(
            Project.department.isnot(None),
            Project.is_deleted == False,
        )
        if filters.company:
            summary_query = summary_query.filter(Project.company == filters.company)

        summary = (
            summary_query.group_by(Project.department)
            .order_by(func.count(Project.id).desc())
            .limit(limit)
            .all()
        )

        result = []
        for s in summary:
            # Get task counts for this department
            task_query = (
                self.db.query(func.count(Task.id))
                .join(Project)
                .filter(Project.department == s.department)
            )
            if filters.company:
                task_query = task_query.filter(Project.company == filters.company)
            task_count = task_query.scalar() or 0

            result.append(
                DepartmentSummary(
                    department=s.department,
                    project_count=s.project_count,
                    task_count=task_count,
                    total_estimated=float(s.total_estimated or 0),
                    total_billed=float(s.total_billed or 0),
                    avg_completion=round(float(s.avg_completion or 0), 1),
                )
            )

        return result
