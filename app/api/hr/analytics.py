"""
HR Analytics Router

Cross-module analytics and dashboard endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional
from datetime import date

from app.database import get_db
from app.auth import Require
from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus, LeaveAllocation
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_payroll import SalarySlip, SalarySlipStatus
from app.models.hr_recruitment import JobOpening, JobOpeningStatus, JobApplicant, JobApplicantStatus
from app.models.hr_training import TrainingEvent, TrainingEventStatus
from app.models.hr_appraisal import Appraisal, AppraisalStatus
from app.models.hr_lifecycle import EmployeeOnboarding, EmployeeSeparation, BoardingStatus

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


@router.get("/leave-balance", dependencies=[Depends(Require("hr:read"))])
async def leave_balance_report(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    year: Optional[int] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance summary report grouped by employee."""
    query = db.query(
        Attendance.employee_id,
        Attendance.employee_name,
        func.count(Attendance.id).label("total_days"),
        func.sum(func.cast(Attendance.status == AttendanceStatus.PRESENT, db.bind.dialect.type_descriptor(type(1)))).label("present_days"),
        func.sum(func.cast(Attendance.status == AttendanceStatus.ABSENT, db.bind.dialect.type_descriptor(type(1)))).label("absent_days"),
        func.sum(func.cast(Attendance.late_entry == True, db.bind.dialect.type_descriptor(type(1)))).label("late_entries"),
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

    return {
        "total_slips": int(result[0] or 0),
        "total_gross": float(result[1] or 0),
        "total_deductions": float(result[2] or 0),
        "total_net": float(result[3] or 0),
    }


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
