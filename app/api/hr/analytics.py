"""
HR Analytics Router

Cross-module analytics and dashboard endpoints.

Note: Most analytics endpoints use direct DB queries for complex aggregations.
Where service methods exist (get_metrics), they are used. This is consistent
with the pattern: "Direct DB reads acceptable for read-only summaries where
service doesn't have method."
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, Integer
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timedelta

from app.database import get_db
from app.auth import Require
from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus, LeaveAllocation
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_payroll import SalarySlip, SalarySlipStatus, SalarySlipEarning, SalarySlipDeduction
from app.models.hr_recruitment import JobOpening, JobOpeningStatus, JobApplicant, JobApplicantStatus
from app.models.hr_training import TrainingEvent, TrainingEventStatus
from app.models.hr_appraisal import Appraisal, AppraisalStatus
from app.models.hr_lifecycle import EmployeeOnboarding, EmployeeSeparation, BoardingStatus

# Services used where metrics methods exist
from app.services.hr.lifecycle import LifecycleService
from app.services.hr.training import TrainingService
from app.services.hr.appraisal import AppraisalService
from app.services.hr.employees import EmployeeService
from app.services.hr.employee_types import EmployeeFilters
from app.services.hr.analytics import HRAnalyticsService
from app.services.types import PaginationParams

router = APIRouter()


@router.get("/dashboard", dependencies=[Depends(Require("hr:read"))])
async def hr_dashboard(
    company: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive HR dashboard stats."""

    # Leave applications summary
    leave_query = db.query(LeaveApplication.status, func.count(LeaveApplication.id))
    if company:
        leave_query = leave_query.filter(LeaveApplication.company.ilike(f"%{company}%"))
    if from_date:
        leave_query = leave_query.filter(LeaveApplication.from_date >= from_date)
    if to_date:
        leave_query = leave_query.filter(LeaveApplication.to_date <= to_date)
    leave_results = leave_query.group_by(LeaveApplication.status).all()
    leave_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in leave_results}

    # Attendance summary
    att_query = db.query(Attendance.status, func.count(Attendance.id))
    if company:
        att_query = att_query.filter(Attendance.company.ilike(f"%{company}%"))
    if from_date:
        att_query = att_query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        att_query = att_query.filter(Attendance.attendance_date <= to_date)
    att_results = att_query.group_by(Attendance.status).all()
    attendance_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in att_results}

    # Recruitment summary
    job_query = db.query(JobOpening.status, func.count(JobOpening.id))
    if company:
        job_query = job_query.filter(JobOpening.company.ilike(f"%{company}%"))
    job_results = job_query.group_by(JobOpening.status).all()
    job_openings_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in job_results}

    applicant_query = db.query(JobApplicant.status, func.count(JobApplicant.id))
    if company:
        applicant_query = applicant_query.filter(JobApplicant.company.ilike(f"%{company}%"))
    applicant_results = applicant_query.group_by(JobApplicant.status).all()
    applicants_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in applicant_results}

    # Payroll summary
    payroll_query = db.query(
        SalarySlip.status,
        func.count(SalarySlip.id),
        func.sum(SalarySlip.net_pay),
        func.sum(SalarySlip.gross_pay),
        func.sum(SalarySlip.total_deduction),
    )
    if company:
        payroll_query = payroll_query.filter(SalarySlip.company.ilike(f"%{company}%"))
    if from_date:
        payroll_query = payroll_query.filter(SalarySlip.start_date >= from_date)
    if to_date:
        payroll_query = payroll_query.filter(SalarySlip.end_date <= to_date)
    payroll_results = payroll_query.group_by(SalarySlip.status).all()
    payroll_summary = {}
    for row in payroll_results:
        status_val = row[0].value if row[0] else None
        payroll_summary[status_val] = {
            "count": int(row[1] or 0),
            "total_net_pay": float(row[2] or 0),
            "total_gross_pay": float(row[3] or 0),
            "total_deductions": float(row[4] or 0),
        }

    # Training summary
    training_query = db.query(TrainingEvent.status, func.count(TrainingEvent.id))
    if company:
        training_query = training_query.filter(TrainingEvent.company.ilike(f"%{company}%"))
    training_results = training_query.group_by(TrainingEvent.status).all()
    training_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in training_results}

    # Appraisal summary
    appraisal_query = db.query(Appraisal.status, func.count(Appraisal.id), func.avg(Appraisal.final_score))
    if company:
        appraisal_query = appraisal_query.filter(Appraisal.company.ilike(f"%{company}%"))
    if from_date:
        appraisal_query = appraisal_query.filter(Appraisal.start_date >= from_date)
    if to_date:
        appraisal_query = appraisal_query.filter(Appraisal.end_date <= to_date)
    appraisal_results = appraisal_query.group_by(Appraisal.status).all()
    appraisal_summary = {}
    for row in appraisal_results:
        status_val = row[0].value if row[0] else None
        appraisal_summary[status_val] = {
            "count": int(row[1] or 0),
            "avg_score": float(row[2]) if row[2] else 0,
        }

    # Lifecycle summary
    onboarding_query = db.query(EmployeeOnboarding.boarding_status, func.count(EmployeeOnboarding.id))
    if company:
        onboarding_query = onboarding_query.filter(EmployeeOnboarding.company.ilike(f"%{company}%"))
    onboarding_results = onboarding_query.group_by(EmployeeOnboarding.boarding_status).all()
    onboarding_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in onboarding_results}

    separation_query = db.query(EmployeeSeparation.boarding_status, func.count(EmployeeSeparation.id))
    if company:
        separation_query = separation_query.filter(EmployeeSeparation.company.ilike(f"%{company}%"))
    separation_results = separation_query.group_by(EmployeeSeparation.boarding_status).all()
    separation_summary = {row[0].value if row[0] else None: int(row[1] or 0) for row in separation_results}

    return {
        "leave": leave_summary,
        "attendance": attendance_summary,
        "recruitment": {
            "job_openings": job_openings_summary,
            "applicants": applicants_summary,
        },
        "payroll": payroll_summary,
        "training": training_summary,
        "appraisal": appraisal_summary,
        "lifecycle": {
            "onboarding": onboarding_summary,
            "separation": separation_summary,
        },
    }


@router.get("/overview", dependencies=[Depends(Require("hr:read"))])
async def hr_overview(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Overview snapshot used by HR analytics dashboard."""
    dashboard = await hr_dashboard(company=company, from_date=None, to_date=None, db=db)
    payroll_breakdown = dashboard.get("payroll", {})
    payroll_30d = {
        "net_total": sum(val.get("total_net_pay", 0) for val in payroll_breakdown.values()),
        "gross_total": sum(val.get("total_gross_pay", 0) for val in payroll_breakdown.values()),
        "slip_count": sum(val.get("count", 0) for val in payroll_breakdown.values()),
    }
    return {
        "leave_by_status": dashboard.get("leave", {}),
        "attendance_status_30d": dashboard.get("attendance", {}),
        "payroll_30d": payroll_30d,
        "recruitment": dashboard.get("recruitment", {}),
        "training": dashboard.get("training", {}),
        "appraisal": dashboard.get("appraisal", {}),
        "lifecycle": dashboard.get("lifecycle", {}),
    }


@router.get("/leave-trend", dependencies=[Depends(Require("hr:read"))])
async def leave_trend(
    company: Optional[str] = None,
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Leave application volume by month."""
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=months * 30)

    query = db.query(
        extract("year", LeaveApplication.from_date).label("year"),
        extract("month", LeaveApplication.from_date).label("month"),
        func.count(LeaveApplication.id).label("count"),
    ).filter(
        LeaveApplication.from_date >= start_dt,
        LeaveApplication.from_date <= end_dt,
    )
    if company:
        query = query.filter(LeaveApplication.company.ilike(f"%{company}%"))

    results = query.group_by(
        extract("year", LeaveApplication.from_date),
        extract("month", LeaveApplication.from_date),
    ).order_by(
        extract("year", LeaveApplication.from_date),
        extract("month", LeaveApplication.from_date),
    ).all()

    return [
        {
            "year": int(r.year),
            "month_num": int(r.month),
            "month": f"{int(r.year)}-{int(r.month):02d}",
            "count": int(r._mapping.get("count") or 0),
        }
        for r in results
    ]


@router.get("/attendance-trend", dependencies=[Depends(Require("hr:read"))])
async def attendance_trend(
    company: Optional[str] = None,
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Attendance records by day."""
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=days)

    query = db.query(
        Attendance.attendance_date,
        func.count(Attendance.id).label("count"),
    ).filter(
        Attendance.attendance_date >= start_dt,
        Attendance.attendance_date <= end_dt,
    )
    if company:
        query = query.filter(Attendance.company.ilike(f"%{company}%"))

    results = query.group_by(Attendance.attendance_date).order_by(Attendance.attendance_date).all()

    return [
        {
            "date": r.attendance_date.isoformat() if r.attendance_date else None,
            "total": int(r._mapping.get("count") or 0),
        }
        for r in results
    ]


@router.get("/payroll-trend", dependencies=[Depends(Require("hr:read"))])
async def payroll_trend(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Monthly payroll totals."""
    query = db.query(
        extract("year", SalarySlip.posting_date).label("year"),
        extract("month", SalarySlip.posting_date).label("month"),
        func.sum(SalarySlip.net_pay).label("net_total"),
        func.sum(SalarySlip.gross_pay).label("gross_total"),
        func.count(SalarySlip.id).label("slip_count"),
    ).filter(
        SalarySlip.status.in_([SalarySlipStatus.SUBMITTED, SalarySlipStatus.PAID])
    )
    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))

    results = query.group_by(
        extract("year", SalarySlip.posting_date),
        extract("month", SalarySlip.posting_date),
    ).order_by(
        extract("year", SalarySlip.posting_date),
        extract("month", SalarySlip.posting_date),
    ).all()

    return [
        {
            "year": int(r.year),
            "month_num": int(r.month),
            "month": f"{int(r.year)}-{int(r.month):02d}",
            "net_total": float(r.net_total or 0),
            "gross_total": float(r.gross_total or 0),
            "slip_count": int(r.slip_count or 0),
        }
        for r in results
    ]


@router.get("/payroll-components", dependencies=[Depends(Require("hr:read"))])
async def payroll_components(
    company: Optional[str] = None,
    component_type: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Aggregate payroll components (earnings and deductions)."""
    earnings_query = db.query(
        SalarySlipEarning.salary_component.label("component"),
        func.sum(SalarySlipEarning.amount).label("amount"),
        func.count(SalarySlipEarning.id).label("count"),
    ).join(SalarySlip, SalarySlip.id == SalarySlipEarning.salary_slip_id)
    if company:
        earnings_query = earnings_query.filter(SalarySlip.company.ilike(f"%{company}%"))
    earnings = earnings_query.group_by(SalarySlipEarning.salary_component).all()

    deductions_query = db.query(
        SalarySlipDeduction.salary_component.label("component"),
        func.sum(SalarySlipDeduction.amount).label("amount"),
        func.count(SalarySlipDeduction.id).label("count"),
    ).join(SalarySlip, SalarySlip.id == SalarySlipDeduction.salary_slip_id)
    if company:
        deductions_query = deductions_query.filter(SalarySlip.company.ilike(f"%{company}%"))
    deductions = deductions_query.group_by(SalarySlipDeduction.salary_component).all()

    rows: List[Dict[str, Any]] = []
    for row in earnings:
        rows.append({
            "salary_component": row.component,
            "component_type": "earning",
            "amount": float(row.amount or 0),
            "count": int(row._mapping.get("count") or 0),
        })
    for row in deductions:
        rows.append({
            "salary_component": row.component,
            "component_type": "deduction",
            "amount": float(row.amount or 0),
            "count": int(row._mapping.get("count") or 0),
        })

    # Respect limit to avoid overly long responses
    return rows[:limit]


@router.get("/leave-balance", dependencies=[Depends(Require("hr:read"))])
async def leave_balance_report(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    year: Optional[int] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave balance report for employees."""
    query = db.query(
        LeaveAllocation.employee_id,
        LeaveAllocation.employee_name,
        LeaveAllocation.leave_type,
        func.sum(LeaveAllocation.total_leaves_allocated).label("total_allocated"),
        func.sum(LeaveAllocation.unused_leaves).label("unused_leaves"),
    )

    if employee_id:
        query = query.filter(LeaveAllocation.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveAllocation.leave_type_id == leave_type_id)
    if year:
        query = query.filter(func.extract("year", LeaveAllocation.from_date) == year)
    if company:
        query = query.filter(LeaveAllocation.company.ilike(f"%{company}%"))

    query = query.group_by(
        LeaveAllocation.employee_id,
        LeaveAllocation.employee_name,
        LeaveAllocation.leave_type,
    )

    total = query.count()
    results = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "employee_id": row[0],
                "employee_name": row[1],
                "leave_type": row[2],
                "total_allocated": float(row[3] or 0),
                "unused_leaves": float(row[4] or 0),
            }
            for row in results
        ],
    }


@router.get("/attendance-summary", dependencies=[Depends(Require("hr:read"))])
async def attendance_summary_report(
    employee_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance summary report grouped by employee."""
    query = db.query(
        Attendance.employee_id,
        Attendance.employee_name,
        func.count(Attendance.id).label("total_days"),
        func.sum(func.cast(Attendance.status == AttendanceStatus.PRESENT, Integer())).label("present_days"),
        func.sum(func.cast(Attendance.status == AttendanceStatus.ABSENT, Integer())).label("absent_days"),
        func.sum(func.cast(Attendance.late_entry == True, Integer())).label("late_entries"),
        func.sum(Attendance.working_hours).label("total_working_hours"),
    )

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if from_date:
        query = query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        query = query.filter(Attendance.attendance_date <= to_date)
    if company:
        query = query.filter(Attendance.company.ilike(f"%{company}%"))

    query = query.group_by(Attendance.employee_id, Attendance.employee_name)

    results = query.offset(offset).limit(limit).all()

    return {
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "employee_id": row[0],
                "employee_name": row[1],
                "total_days": int(row[2] or 0),
                "present_days": int(row[3] or 0),
                "absent_days": int(row[4] or 0),
                "late_entries": int(row[5] or 0),
                "total_working_hours": float(row[6] or 0),
            }
            for row in results
        ],
    }


@router.get("/payroll-summary", dependencies=[Depends(Require("hr:read"))])
async def payroll_summary_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payroll summary with totals."""
    query = db.query(
        func.count(SalarySlip.id).label("total_slips"),
        func.sum(SalarySlip.gross_pay).label("total_gross"),
        func.sum(SalarySlip.total_deduction).label("total_deductions"),
        func.sum(SalarySlip.net_pay).label("total_net"),
    )

    if from_date:
        query = query.filter(SalarySlip.start_date >= from_date)
    if to_date:
        query = query.filter(SalarySlip.end_date <= to_date)
    if company:
        query = query.filter(SalarySlip.company.ilike(f"%{company}%"))

    query = query.filter(SalarySlip.status == SalarySlipStatus.SUBMITTED)

    result = query.first()
    totals = result._mapping if result else {}

    summary = {
        "total_slips": int(totals.get("total_slips") or 0),
        "total_gross": float(totals.get("total_gross") or 0),
        "total_deductions": float(totals.get("total_deductions") or 0),
        "total_net": float(totals.get("total_net") or 0),
    }
    summary.update(
        {
            "slip_count": summary["total_slips"],
            "gross_total": summary["total_gross"],
            "deduction_total": summary["total_deductions"],
            "net_total": summary["total_net"],
        }
    )
    return summary


@router.get("/recruitment-funnel", dependencies=[Depends(Require("hr:read"))])
async def recruitment_funnel(
    job_opening_id: Optional[int] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get recruitment funnel metrics."""
    # Total job openings
    openings_query = db.query(func.count(JobOpening.id))
    if company:
        openings_query = openings_query.filter(JobOpening.company.ilike(f"%{company}%"))
    total_openings = openings_query.scalar() or 0

    # Active job openings
    active_openings_query = db.query(func.count(JobOpening.id)).filter(
        JobOpening.status == JobOpeningStatus.OPEN
    )
    if company:
        active_openings_query = active_openings_query.filter(JobOpening.company.ilike(f"%{company}%"))
    active_openings = active_openings_query.scalar() or 0

    # Applicants by status
    applicant_query = db.query(JobApplicant.status, func.count(JobApplicant.id))
    if job_opening_id:
        applicant_query = applicant_query.filter(JobApplicant.job_opening_id == job_opening_id)
    if company:
        applicant_query = applicant_query.filter(JobApplicant.company.ilike(f"%{company}%"))
    applicant_results = applicant_query.group_by(JobApplicant.status).all()

    applicant_breakdown = {row[0].value if row[0] else None: int(row[1] or 0) for row in applicant_results}
    total_applicants = sum(applicant_breakdown.values())

    return {
        "total_openings": total_openings,
        "active_openings": active_openings,
        "total_applicants": total_applicants,
        "applicant_breakdown": applicant_breakdown,
        "openings": {"total": total_openings, "active": active_openings},
        "applicants": applicant_breakdown,
        "offers": {},
        "conversion_rates": {
            "applied_to_replied": (
                applicant_breakdown.get("replied", 0) / total_applicants * 100
                if total_applicants > 0 else 0
            ),
            "replied_to_accepted": (
                applicant_breakdown.get("accepted", 0) / applicant_breakdown.get("replied", 1) * 100
                if applicant_breakdown.get("replied", 0) > 0 else 0
            ),
        },
    }


@router.get("/appraisal-status", dependencies=[Depends(Require("hr:read"))])
async def appraisal_status(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return appraisal status breakdown."""
    dashboard = await hr_dashboard(company=company, db=db)
    return {"status_counts": dashboard.get("appraisal", {})}


@router.get("/lifecycle-events", dependencies=[Depends(Require("hr:read"))])
async def lifecycle_events(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return onboarding/separation/promotion/transfer counts."""
    dashboard = await hr_dashboard(company=company, db=db)
    lifecycle = dashboard.get("lifecycle", {}) or {}
    return {
        "onboarding": lifecycle.get("onboarding", {}),
        "separation": lifecycle.get("separation", {}),
        "promotion": {},
        "transfer": {},
    }


@router.get("/training-completion", dependencies=[Depends(Require("hr:read"))])
async def training_completion_report(
    company: Optional[str] = None,
    from_time: Optional[date] = None,
    to_time: Optional[date] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training completion statistics."""
    query = db.query(TrainingEvent.status, func.count(TrainingEvent.id))

    if company:
        query = query.filter(TrainingEvent.company.ilike(f"%{company}%"))
    if from_time:
        query = query.filter(TrainingEvent.start_time >= from_time)
    if to_time:
        query = query.filter(TrainingEvent.end_time <= to_time)

    results = query.group_by(TrainingEvent.status).all()
    status_breakdown = {row[0].value if row[0] else None: int(row[1] or 0) for row in results}

    total = sum(status_breakdown.values())
    completed = status_breakdown.get("completed", 0)

    return {
        "total_events": total,
        "status_breakdown": status_breakdown,
        "completion_rate": completed / total * 100 if total > 0 else 0,
    }


# =============================================================================
# EMPLOYEES LIST (for lookups)
# =============================================================================

@router.get("/employees", dependencies=[Depends(Require("hr:read"))])
async def list_employees(
    search: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employees for lookups and selection fields."""
    from app.models.employee import EmploymentStatus

    service = EmployeeService(db)

    # Build filters
    status_enum = None
    if status:
        try:
            status_enum = EmploymentStatus(status)
        except ValueError:
            pass

    filters = EmployeeFilters(
        search=search,
        status=status_enum,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_employees(filters, pagination)

    # Filter by department text if provided (service doesn't support this)
    items = result.items
    if department:
        items = [e for e in items if e.department and department.lower() in e.department.lower()]

    return {
        "items": [
            {
                "id": e.id,
                "name": e.name,
                "email": e.email,
                "employee_number": e.employee_number,
                "department": e.department,
                "designation": e.designation,
                "status": e.status.value if e.status else None,
            }
            for e in items
        ],
        "total": result.total,
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# ORGANIZATION ANALYTICS
# =============================================================================


@router.get("/organization/headcount", dependencies=[Depends(Require("hr:read"))])
async def organization_headcount(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get headcount breakdown by department."""
    service = HRAnalyticsService(db)
    result = service.get_headcount_by_department(company)
    return {
        "data": [
            {
                "department_id": h.department_id,
                "department_name": h.department_name,
                "total_employees": h.total_employees,
                "active_employees": h.active_employees,
                "on_leave": h.on_leave,
                "terminated": h.terminated,
                "percentage_of_total": h.percentage_of_total,
            }
            for h in result
        ]
    }


@router.get("/organization/headcount-trend/{department_id}", dependencies=[Depends(Require("hr:read"))])
async def department_headcount_trend(
    department_id: int,
    months: int = Query(default=12, ge=1, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get headcount trend for a department over time."""
    service = HRAnalyticsService(db)
    result = service.get_department_headcount_trend(department_id, months)
    return {
        "department_id": result.department_id,
        "department_name": result.department_name,
        "data_points": [
            {"period": p.period, "value": p.value, "label": p.label}
            for p in result.data_points
        ],
    }


@router.get("/organization/designations", dependencies=[Depends(Require("hr:read"))])
async def designation_distribution(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get employee distribution by designation."""
    service = HRAnalyticsService(db)
    result = service.get_designation_distribution(company)
    return {
        "data": [
            {
                "designation_id": d.designation_id,
                "designation_name": d.designation_name,
                "employee_count": d.employee_count,
                "percentage": d.percentage,
            }
            for d in result
        ]
    }


@router.get("/organization/teams", dependencies=[Depends(Require("hr:read"))])
async def team_metrics(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get metrics for HD teams."""
    service = HRAnalyticsService(db)
    result = service.get_team_metrics(company)
    return {
        "data": [
            {
                "team_id": t.team_id,
                "team_name": t.team_name,
                "member_count": t.member_count,
                "avg_workload": t.avg_workload,
            }
            for t in result
        ]
    }


@router.get("/workforce", dependencies=[Depends(Require("hr:read"))])
async def workforce_analytics(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive workforce analytics."""
    service = HRAnalyticsService(db)
    result = service.get_workforce_analytics(company)
    return {
        "total_headcount": result.total_headcount,
        "active_employees": result.active_employees,
        "on_leave": result.on_leave,
        "terminated": result.terminated,
        "avg_tenure_months": result.avg_tenure_months,
        "new_hires_30d": result.new_hires_30d,
        "separations_30d": result.separations_30d,
        "headcount_by_department": [
            {
                "department_id": h.department_id,
                "department_name": h.department_name,
                "total_employees": h.total_employees,
                "percentage_of_total": h.percentage_of_total,
            }
            for h in result.headcount_by_department
        ],
        "headcount_by_designation": [
            {
                "designation_id": d.designation_id,
                "designation_name": d.designation_name,
                "employee_count": d.employee_count,
                "percentage": d.percentage,
            }
            for d in result.headcount_by_designation
        ],
        "headcount_trend": [
            {"period": p.period, "value": p.value, "label": p.label}
            for p in result.headcount_trend
        ],
    }


@router.get("/turnover", dependencies=[Depends(Require("hr:read"))])
async def turnover_analytics(
    from_date: date = Query(..., description="Start date for analysis"),
    to_date: date = Query(..., description="End date for analysis"),
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get turnover analytics for a period."""
    service = HRAnalyticsService(db)
    result = service.get_turnover_analytics(from_date, to_date, company)
    return {
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "total_separations": result.total_separations,
        "voluntary_separations": result.voluntary_separations,
        "involuntary_separations": result.involuntary_separations,
        "turnover_rate": result.turnover_rate,
        "avg_tenure_at_exit_months": result.avg_tenure_at_exit_months,
        "by_department": result.by_department,
    }
