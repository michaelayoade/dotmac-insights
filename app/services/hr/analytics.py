"""HR Analytics service - consolidated analytics and reporting logic.

This service encapsulates HR analytics and reporting:
- Dashboard summaries
- Organization analytics (headcount, distribution)
- Trend calculations
- Workforce metrics
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from sqlalchemy import and_, func, extract, Integer, case
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department, Designation, HDTeam, HDTeamMember
from app.models.hr_leave import (
    LeaveApplication,
    LeaveApplicationStatus,
    LeaveAllocation,
)
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_payroll import SalarySlip, SalarySlipStatus
from app.models.hr_recruitment import JobOpening, JobOpeningStatus, JobApplicant
from app.models.hr_training import TrainingEvent, TrainingEventStatus
from app.models.hr_appraisal import Appraisal, AppraisalStatus
from app.models.hr_lifecycle import (
    EmployeeOnboarding,
    EmployeeSeparation,
    BoardingStatus,
    SeparationType,
)

from .analytics_types import (
    HRDashboardSummary,
    HRDashboardData,
    HRDashboardStats,
    DepartmentStat,
    WorkAnniversary,
    NextPayroll,
    ModuleSummary,
    HeadcountByDepartment,
    DepartmentHeadcountTrend,
    DesignationDistribution,
    TeamMetrics,
    WorkforceAnalytics,
    TurnoverAnalytics,
    TrendPoint,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["HRAnalyticsService"]


class HRAnalyticsService:
    """Service for HR analytics and reporting.

    Consolidates analytics logic from API layer into reusable service.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # =========================================================================
    # Dashboard
    # =========================================================================

    def get_dashboard_data(
        self,
        company: Optional[str] = None,
        as_at: Optional[date] = None,
    ) -> HRDashboardData:
        """Get complete HR dashboard data in a single optimized call.

        Args:
            company: Filter by company name
            as_at: View data as at this date (defaults to today)
        """
        view_date = as_at or date.today()

        # Get stats with single optimized query using conditional aggregation
        stats = self._get_dashboard_stats(view_date, company)

        # Department counts (as at the view date - employees active on that date)
        department_stats = self._get_department_stats(company, view_date)

        # Recent leave requests (pending as of view date)
        recent_leave = (
            self.db.query(LeaveApplication)
            .filter(
                LeaveApplication.status == LeaveApplicationStatus.OPEN,
                LeaveApplication.posting_date <= view_date,
            )
            .order_by(LeaveApplication.posting_date.desc())
            .limit(5)
            .all()
        )

        # Work anniversaries for the view date's month
        anniversaries = self._get_work_anniversaries(view_date)

        # Next payroll due (relative to view date)
        next_payroll = self._get_next_payroll(view_date)

        return HRDashboardData(
            stats=stats,
            department_stats=department_stats,
            recent_leave_requests=recent_leave,
            anniversaries=anniversaries,
            next_payroll=next_payroll,
        )

    def _get_dashboard_stats(
        self,
        view_date: date,
        company: Optional[str] = None,
    ) -> HRDashboardStats:
        """Get dashboard stat card values using conditional aggregation.

        Args:
            view_date: The date to view stats for
            company: Optional company filter
        """
        from app.models.hr_attendance import AttendanceStatus

        # Total employees active as at view_date
        # (joined before or on view_date, not relieved before view_date)
        emp_query = self.db.query(func.count(Employee.id)).filter(
            Employee.is_deleted == False,
            Employee.status.in_([EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE]),
            Employee.date_of_joining <= view_date,
            (Employee.date_of_leaving.is_(None)) | (Employee.date_of_leaving > view_date),
        )
        if company:
            emp_query = emp_query.filter(Employee.company.ilike(f"%{company}%"))
        total_employees = emp_query.scalar() or 0

        # Attendance on view_date (present count)
        present_count = (
            self.db.query(func.count(Attendance.id))
            .filter(
                func.date(Attendance.attendance_date) == view_date,
                Attendance.status == AttendanceStatus.PRESENT,
            )
            .scalar()
            or 0
        )

        # On leave on view_date
        on_leave_count = (
            self.db.query(func.count(LeaveApplication.id))
            .filter(
                LeaveApplication.status == LeaveApplicationStatus.APPROVED,
                LeaveApplication.from_date <= view_date,
                LeaveApplication.to_date >= view_date,
            )
            .scalar()
            or 0
        )

        # Pending leave requests as at view_date
        pending_leave = (
            self.db.query(func.count(LeaveApplication.id))
            .filter(
                LeaveApplication.status == LeaveApplicationStatus.OPEN,
                LeaveApplication.posting_date <= view_date,
            )
            .scalar()
            or 0
        )

        return HRDashboardStats(
            total_employees=total_employees,
            present_today=present_count,
            on_leave_today=on_leave_count,
            pending_leave=pending_leave,
        )

    def _get_department_stats(
        self,
        company: Optional[str] = None,
        view_date: Optional[date] = None,
    ) -> List[DepartmentStat]:
        """Get employee count per department as at a specific date."""
        check_date = view_date or date.today()

        query = (
            self.db.query(
                Department.id,
                Department.department_name,
                func.count(Employee.id).label("count"),
            )
            .outerjoin(
                Employee,
                and_(
                    Employee.department_id == Department.id,
                    Employee.is_deleted == False,
                    Employee.status.in_([EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE]),
                    Employee.date_of_joining <= check_date,
                    (Employee.date_of_leaving.is_(None)) | (Employee.date_of_leaving > check_date),
                ),
            )
            .group_by(Department.id, Department.department_name)
            .order_by(func.count(Employee.id).desc())
            .limit(8)
        )

        if company:
            query = query.filter(Department.company.ilike(f"%{company}%"))

        return [
            DepartmentStat(id=row[0], name=row[1], count=row[2] or 0)
            for row in query.all()
        ]

    def _get_work_anniversaries(
        self,
        today: date,
    ) -> List[WorkAnniversary]:
        """Get employees with work anniversaries this month."""
        try:
            anniversary_employees = (
                self.db.query(Employee)
                .filter(
                    Employee.is_deleted == False,
                    Employee.status == EmploymentStatus.ACTIVE,
                    func.extract("month", Employee.date_of_joining) == today.month,
                    Employee.date_of_joining < today.replace(year=today.year),
                )
                .order_by(func.extract("day", Employee.date_of_joining))
                .limit(5)
                .all()
            )

            result: List[WorkAnniversary] = []
            for emp in anniversary_employees:
                if emp.date_of_joining:
                    years = today.year - emp.date_of_joining.year
                    if years > 0:
                        result.append(
                            WorkAnniversary(
                                id=emp.id,
                                name=emp.name or "",
                                date=emp.date_of_joining,
                                years=years,
                            )
                        )
            return result
        except Exception:
            return []

    def _get_next_payroll(self, view_date: Optional[date] = None) -> Optional[NextPayroll]:
        """Get next upcoming payroll entry relative to the view date."""
        from app.models.hr_payroll import PayrollEntry

        check_date = view_date or date.today()

        try:
            # Find payroll entries with end_date >= view_date that are still draft
            upcoming = (
                self.db.query(PayrollEntry)
                .filter(
                    PayrollEntry.docstatus == 0,
                    PayrollEntry.end_date >= check_date,
                )
                .order_by(PayrollEntry.end_date.asc())
                .first()
            )
            if upcoming:
                return NextPayroll(
                    id=upcoming.id,
                    name=f"Payroll #{upcoming.id}",
                    date=upcoming.end_date,
                )
        except Exception:
            pass
        return None

    # =========================================================================
    # Organization Analytics
    # =========================================================================

    def get_headcount_by_department(
        self,
        company: Optional[str] = None,
    ) -> List[HeadcountByDepartment]:
        """Get employee headcount breakdown by department."""
        # Get total employee count for percentage calculation
        total_query = self.db.query(func.count(Employee.id)).filter(
            Employee.is_deleted == False
        )
        if company:
            total_query = total_query.filter(Employee.company.ilike(f"%{company}%"))
        total_employees = total_query.scalar() or 0

        # Get headcount by department
        query = (
            self.db.query(
                Department.id.label("department_id"),
                Department.department_name.label("department_name"),
                func.count(Employee.id).label("total_employees"),
                func.sum(
                    case(
                        (Employee.status == EmploymentStatus.ACTIVE, 1),
                        else_=0,
                    )
                ).label("active_employees"),
                func.sum(
                    case(
                        (Employee.status == EmploymentStatus.ON_LEAVE, 1),
                        else_=0,
                    )
                ).label("on_leave"),
                func.sum(
                    case(
                        (Employee.status == EmploymentStatus.LEFT, 1),
                        else_=0,
                    )
                ).label("terminated"),
            )
            .outerjoin(Employee, Employee.department == Department.department_name)
            .filter(Employee.is_deleted == False)
            .group_by(Department.id, Department.department_name)
        )

        if company:
            query = query.filter(Department.company.ilike(f"%{company}%"))

        results = query.all()

        return [
            HeadcountByDepartment(
                department_id=row.department_id,
                department_name=row.department_name,
                total_employees=int(row.total_employees or 0),
                active_employees=int(row.active_employees or 0),
                on_leave=int(row.on_leave or 0),
                terminated=int(row.terminated or 0),
                percentage_of_total=(
                    round((row.total_employees or 0) / total_employees * 100, 2)
                    if total_employees > 0
                    else 0.0
                ),
            )
            for row in results
        ]

    def get_department_headcount_trend(
        self,
        department_id: int,
        months: int = 12,
    ) -> DepartmentHeadcountTrend:
        """Get headcount trend for a department over time.

        Uses employee date_of_joining and date_of_leaving to calculate
        historical headcount.
        """
        department = (
            self.db.query(Department).filter(Department.id == department_id).first()
        )
        if not department:
            return DepartmentHeadcountTrend(
                department_id=department_id,
                department_name="Unknown",
                data_points=[],
            )

        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)

        data_points: List[TrendPoint] = []

        # Calculate headcount for each month
        current = start_date.replace(day=1)
        while current <= end_date:
            month_end = (current.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)

            # Count employees who were active during this month
            count = (
                self.db.query(func.count(Employee.id))
                .filter(
                    Employee.department == department.department_name,
                    Employee.is_deleted == False,
                    Employee.date_of_joining <= month_end,
                    (Employee.date_of_leaving.is_(None))
                    | (Employee.date_of_leaving >= current),
                )
                .scalar()
                or 0
            )

            data_points.append(
                TrendPoint(
                    period=current.strftime("%Y-%m"),
                    value=float(count),
                    label=current.strftime("%b %Y"),
                )
            )

            # Move to next month
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        return DepartmentHeadcountTrend(
            department_id=department_id,
            department_name=department.department_name,
            data_points=data_points,
        )

    def get_designation_distribution(
        self,
        company: Optional[str] = None,
    ) -> List[DesignationDistribution]:
        """Get employee distribution by designation."""
        # Get total employee count
        total_query = self.db.query(func.count(Employee.id)).filter(
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE,
        )
        if company:
            total_query = total_query.filter(Employee.company.ilike(f"%{company}%"))
        total_employees = total_query.scalar() or 0

        # Get count by designation
        query = (
            self.db.query(
                Designation.id.label("designation_id"),
                Designation.designation_name.label("designation_name"),
                func.count(Employee.id).label("employee_count"),
            )
            .outerjoin(Employee, Employee.designation == Designation.designation_name)
            .filter(
                Employee.is_deleted == False,
                Employee.status == EmploymentStatus.ACTIVE,
            )
            .group_by(Designation.id, Designation.designation_name)
            .order_by(func.count(Employee.id).desc())
        )

        if company:
            query = query.filter(Employee.company.ilike(f"%{company}%"))

        results = query.all()

        return [
            DesignationDistribution(
                designation_id=row.designation_id,
                designation_name=row.designation_name,
                employee_count=int(row.employee_count or 0),
                percentage=(
                    round((row.employee_count or 0) / total_employees * 100, 2)
                    if total_employees > 0
                    else 0.0
                ),
            )
            for row in results
        ]

    def get_team_metrics(
        self,
        company: Optional[str] = None,
    ) -> List[TeamMetrics]:
        """Get metrics for HD teams."""
        query = (
            self.db.query(
                HDTeam.id.label("team_id"),
                HDTeam.team_name.label("team_name"),
                func.count(HDTeamMember.id).label("member_count"),
            )
            .outerjoin(HDTeamMember, HDTeamMember.parent == HDTeam.id)
            .group_by(HDTeam.id, HDTeam.team_name)
        )

        if company:
            query = query.filter(HDTeam.company.ilike(f"%{company}%"))

        results = query.all()

        return [
            TeamMetrics(
                team_id=row.team_id,
                team_name=row.team_name,
                member_count=int(row.member_count or 0),
                avg_workload=None,  # Could be calculated from ticket assignments
            )
            for row in results
        ]

    # =========================================================================
    # Workforce Analytics
    # =========================================================================

    def get_workforce_analytics(
        self,
        company: Optional[str] = None,
    ) -> WorkforceAnalytics:
        """Get comprehensive workforce analytics."""
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        # Base employee query
        base_filter = [Employee.is_deleted == False]
        if company:
            base_filter.append(Employee.company.ilike(f"%{company}%"))

        # Total headcount
        total_headcount = (
            self.db.query(func.count(Employee.id)).filter(*base_filter).scalar() or 0
        )

        # Active employees
        active_employees = (
            self.db.query(func.count(Employee.id))
            .filter(*base_filter, Employee.status == EmploymentStatus.ACTIVE)
            .scalar()
            or 0
        )

        # On leave
        on_leave = (
            self.db.query(func.count(Employee.id))
            .filter(*base_filter, Employee.status == EmploymentStatus.ON_LEAVE)
            .scalar()
            or 0
        )

        # Terminated
        terminated = (
            self.db.query(func.count(Employee.id))
            .filter(*base_filter, Employee.status == EmploymentStatus.LEFT)
            .scalar()
            or 0
        )

        # New hires in last 30 days
        new_hires_30d = (
            self.db.query(func.count(Employee.id))
            .filter(
                *base_filter,
                Employee.date_of_joining >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        # Separations in last 30 days
        separations_30d = (
            self.db.query(func.count(Employee.id))
            .filter(
                *base_filter,
                Employee.date_of_leaving >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        # Average tenure (in months)
        avg_tenure_result = (
            self.db.query(
                func.avg(
                    func.extract("epoch", func.now() - Employee.date_of_joining)
                    / (30 * 24 * 60 * 60)  # Convert seconds to months
                )
            )
            .filter(
                *base_filter,
                Employee.status == EmploymentStatus.ACTIVE,
                Employee.date_of_joining.isnot(None),
            )
            .scalar()
        )
        avg_tenure_months = float(avg_tenure_result or 0)

        # Headcount by department
        headcount_by_department = self.get_headcount_by_department(company)

        # Headcount by designation
        headcount_by_designation = self.get_designation_distribution(company)

        # Headcount trend (last 12 months)
        headcount_trend = self._calculate_headcount_trend(company, months=12)

        return WorkforceAnalytics(
            total_headcount=total_headcount,
            active_employees=active_employees,
            on_leave=on_leave,
            terminated=terminated,
            headcount_by_department=headcount_by_department,
            headcount_by_designation=headcount_by_designation,
            headcount_trend=headcount_trend,
            avg_tenure_months=round(avg_tenure_months, 1),
            new_hires_30d=new_hires_30d,
            separations_30d=separations_30d,
        )

    def _calculate_headcount_trend(
        self,
        company: Optional[str],
        months: int = 12,
    ) -> List[TrendPoint]:
        """Calculate overall headcount trend over time."""
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)

        data_points: List[TrendPoint] = []

        current = start_date.replace(day=1)
        while current <= end_date:
            month_end = (current.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)

            # Count employees active during this month
            query = self.db.query(func.count(Employee.id)).filter(
                Employee.is_deleted == False,
                Employee.date_of_joining <= month_end,
                (Employee.date_of_leaving.is_(None))
                | (Employee.date_of_leaving >= current),
            )

            if company:
                query = query.filter(Employee.company.ilike(f"%{company}%"))

            count = query.scalar() or 0

            data_points.append(
                TrendPoint(
                    period=current.strftime("%Y-%m"),
                    value=float(count),
                    label=current.strftime("%b %Y"),
                )
            )

            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        return data_points

    def get_turnover_analytics(
        self,
        from_date: date,
        to_date: date,
        company: Optional[str] = None,
    ) -> TurnoverAnalytics:
        """Get turnover analytics for a period."""
        base_filter = []
        if company:
            base_filter.append(EmployeeSeparation.company.ilike(f"%{company}%"))

        # Total separations
        total_query = (
            self.db.query(func.count(EmployeeSeparation.id))
            .filter(
                EmployeeSeparation.separation_date >= from_date,
                EmployeeSeparation.separation_date <= to_date,
                *base_filter,
            )
        )
        total_separations = total_query.scalar() or 0

        # Voluntary separations (resignation)
        voluntary_query = (
            self.db.query(func.count(EmployeeSeparation.id))
            .filter(
                EmployeeSeparation.separation_date >= from_date,
                EmployeeSeparation.separation_date <= to_date,
                EmployeeSeparation.separation_type == SeparationType.RESIGNATION,
                *base_filter,
            )
        )
        voluntary_separations = voluntary_query.scalar() or 0

        # Involuntary separations (termination)
        involuntary_separations = total_separations - voluntary_separations

        # Calculate turnover rate
        # Get average headcount during the period
        emp_filter = [Employee.is_deleted == False]
        if company:
            emp_filter.append(Employee.company.ilike(f"%{company}%"))

        avg_headcount = (
            self.db.query(func.count(Employee.id))
            .filter(
                *emp_filter,
                Employee.date_of_joining <= to_date,
                (Employee.date_of_leaving.is_(None))
                | (Employee.date_of_leaving >= from_date),
            )
            .scalar()
            or 0
        )

        turnover_rate = (
            round(total_separations / avg_headcount * 100, 2)
            if avg_headcount > 0
            else 0.0
        )

        # Average tenure at exit - not easily calculated without exit date on separation
        # Use a placeholder for now
        avg_tenure_at_exit_months = 0.0

        # Separations by department
        dept_query = (
            self.db.query(
                EmployeeSeparation.department,
                func.count(EmployeeSeparation.id).label("count"),
            )
            .filter(
                EmployeeSeparation.separation_date >= from_date,
                EmployeeSeparation.separation_date <= to_date,
                *base_filter,
            )
            .group_by(EmployeeSeparation.department)
        )

        by_department = [
            {"department": row.department, "count": int(row.count or 0)}
            for row in dept_query.all()
        ]

        return TurnoverAnalytics(
            period_start=from_date,
            period_end=to_date,
            total_separations=total_separations,
            voluntary_separations=voluntary_separations,
            involuntary_separations=involuntary_separations,
            turnover_rate=turnover_rate,
            avg_tenure_at_exit_months=avg_tenure_at_exit_months,
            by_department=by_department,
        )
