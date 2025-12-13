"""HR Settings API Endpoints

Endpoints for managing HR configuration including leave policies, attendance,
payroll settings, holiday calendars, and salary bands.
"""
from datetime import date, time
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require
from app.models.hr_settings import (
    HRSettings, LeaveEncashmentPolicy, HolidayCalendar, HRHoliday,
    SalaryBand, DocumentChecklistTemplate,
    LeaveAccountingFrequency, ProRataMethod, PayrollFrequency,
    OvertimeCalculation, GratuityCalculation, EmployeeIDFormat,
    AttendanceMarkingMode, AppraisalFrequency
)

router = APIRouter(prefix="/hr/settings", tags=["hr-settings"])


# =============================================================================
# SCHEMAS
# =============================================================================

class HRSettingsResponse(BaseModel):
    id: int
    company: Optional[str]

    # Leave Policy
    leave_accounting_frequency: str
    pro_rata_method: str
    max_carryforward_days: int
    carryforward_expiry_months: int
    min_leave_notice_days: int
    allow_negative_leave_balance: bool
    allow_leave_overlap: bool
    sick_leave_auto_approve_days: int
    medical_certificate_required_after_days: int

    # Attendance
    attendance_marking_mode: AttendanceMarkingMode
    allow_backdated_attendance: bool
    backdated_attendance_days: int
    auto_mark_absent_enabled: bool
    late_entry_grace_minutes: int
    early_exit_grace_minutes: int
    half_day_hours_threshold: Decimal
    full_day_hours_threshold: Decimal
    require_checkout: bool
    geolocation_required: bool
    geolocation_radius_meters: int

    # Shift
    default_shift_id: Optional[int]
    max_weekly_hours: int
    night_shift_allowance_percent: Decimal
    shift_change_notice_days: int

    # Payroll
    payroll_frequency: PayrollFrequency
    salary_payment_day: int
    payroll_cutoff_day: int
    allow_salary_advance: bool
    max_advance_percent: Decimal
    max_advance_months: int
    salary_currency: str

    # Overtime
    overtime_enabled: bool
    overtime_calculation: OvertimeCalculation
    overtime_multiplier_weekday: Decimal
    overtime_multiplier_weekend: Decimal
    overtime_multiplier_holiday: Decimal
    min_overtime_hours: Decimal
    require_overtime_approval: bool

    # Benefits
    gratuity_enabled: bool
    gratuity_calculation: GratuityCalculation
    gratuity_eligibility_years: int
    gratuity_days_per_year: int
    pf_enabled: bool
    pf_employer_percent: Decimal
    pf_employee_percent: Decimal
    pension_enabled: bool
    pension_employer_percent: Decimal
    pension_employee_percent: Decimal
    nhf_enabled: bool
    nhf_percent: Decimal

    # Lifecycle
    default_probation_months: int
    max_probation_extension_months: int
    default_notice_period_days: int
    require_exit_interview: bool
    final_settlement_days: int
    require_clearance_before_settlement: bool

    # Recruitment
    job_posting_validity_days: int
    offer_validity_days: int
    default_interview_duration_minutes: int
    require_background_check: bool
    document_submission_days: int
    allow_offer_negotiation: bool
    offer_negotiation_window_days: int

    # Appraisal
    appraisal_frequency: AppraisalFrequency
    appraisal_cycle_start_month: int
    appraisal_rating_scale: int
    require_self_review: bool
    require_peer_review: bool
    enable_360_feedback: bool
    min_rating_for_promotion: Decimal

    # Training
    mandatory_training_hours_yearly: int
    require_training_approval: bool
    training_completion_threshold_percent: int

    # Compliance
    work_week_days: List[str]
    standard_work_hours_per_day: Decimal
    max_work_hours_per_day: int

    # Display
    employee_id_format: EmployeeIDFormat
    employee_id_prefix: str
    employee_id_min_digits: int

    # Notifications
    notify_leave_balance_below: int
    notify_appraisal_due_days: int
    notify_probation_end_days: int
    notify_contract_expiry_days: int
    notify_document_expiry_days: int

    class Config:
        from_attributes = True


class HRSettingsUpdate(BaseModel):
    # Leave Policy
    leave_accounting_frequency: Optional[str] = None
    pro_rata_method: Optional[str] = None
    max_carryforward_days: Optional[int] = Field(None, ge=0)
    carryforward_expiry_months: Optional[int] = Field(None, ge=0)
    min_leave_notice_days: Optional[int] = Field(None, ge=0)
    allow_negative_leave_balance: Optional[bool] = None
    allow_leave_overlap: Optional[bool] = None
    sick_leave_auto_approve_days: Optional[int] = Field(None, ge=0)
    medical_certificate_required_after_days: Optional[int] = Field(None, ge=0)

    # Attendance
    attendance_marking_mode: Optional[AttendanceMarkingMode] = None
    allow_backdated_attendance: Optional[bool] = None
    backdated_attendance_days: Optional[int] = Field(None, ge=0)
    auto_mark_absent_enabled: Optional[bool] = None
    late_entry_grace_minutes: Optional[int] = Field(None, ge=0)
    early_exit_grace_minutes: Optional[int] = Field(None, ge=0)
    half_day_hours_threshold: Optional[Decimal] = Field(None, ge=0)
    full_day_hours_threshold: Optional[Decimal] = Field(None, ge=0)
    require_checkout: Optional[bool] = None
    geolocation_required: Optional[bool] = None
    geolocation_radius_meters: Optional[int] = Field(None, ge=0)

    # Shift
    default_shift_id: Optional[int] = None
    max_weekly_hours: Optional[int] = Field(None, ge=1, le=168)
    night_shift_allowance_percent: Optional[Decimal] = Field(None, ge=0)
    shift_change_notice_days: Optional[int] = Field(None, ge=0)

    # Payroll
    payroll_frequency: Optional[PayrollFrequency] = None
    salary_payment_day: Optional[int] = Field(None, ge=0, le=31)
    payroll_cutoff_day: Optional[int] = Field(None, ge=1, le=31)
    allow_salary_advance: Optional[bool] = None
    max_advance_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    max_advance_months: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, min_length=3, max_length=3)

    # Overtime
    overtime_enabled: Optional[bool] = None
    overtime_calculation: Optional[OvertimeCalculation] = None
    overtime_multiplier_weekday: Optional[Decimal] = Field(None, ge=1)
    overtime_multiplier_weekend: Optional[Decimal] = Field(None, ge=1)
    overtime_multiplier_holiday: Optional[Decimal] = Field(None, ge=1)
    min_overtime_hours: Optional[Decimal] = Field(None, ge=0)
    require_overtime_approval: Optional[bool] = None

    # Benefits
    gratuity_enabled: Optional[bool] = None
    gratuity_calculation: Optional[GratuityCalculation] = None
    gratuity_eligibility_years: Optional[int] = Field(None, ge=0)
    gratuity_days_per_year: Optional[int] = Field(None, ge=0)
    pf_enabled: Optional[bool] = None
    pf_employer_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    pf_employee_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    pension_enabled: Optional[bool] = None
    pension_employer_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    pension_employee_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    nhf_enabled: Optional[bool] = None
    nhf_percent: Optional[Decimal] = Field(None, ge=0, le=100)

    # Lifecycle
    default_probation_months: Optional[int] = Field(None, ge=0)
    max_probation_extension_months: Optional[int] = Field(None, ge=0)
    default_notice_period_days: Optional[int] = Field(None, ge=0)
    require_exit_interview: Optional[bool] = None
    final_settlement_days: Optional[int] = Field(None, ge=0)
    require_clearance_before_settlement: Optional[bool] = None

    # Recruitment
    job_posting_validity_days: Optional[int] = Field(None, ge=1)
    offer_validity_days: Optional[int] = Field(None, ge=1)
    default_interview_duration_minutes: Optional[int] = Field(None, ge=15)
    require_background_check: Optional[bool] = None
    document_submission_days: Optional[int] = Field(None, ge=1)
    allow_offer_negotiation: Optional[bool] = None
    offer_negotiation_window_days: Optional[int] = Field(None, ge=0)

    # Appraisal
    appraisal_frequency: Optional[AppraisalFrequency] = None
    appraisal_cycle_start_month: Optional[int] = Field(None, ge=1, le=12)
    appraisal_rating_scale: Optional[int] = Field(None, ge=3, le=10)
    require_self_review: Optional[bool] = None
    require_peer_review: Optional[bool] = None
    enable_360_feedback: Optional[bool] = None
    min_rating_for_promotion: Optional[Decimal] = Field(None, ge=0)

    # Training
    mandatory_training_hours_yearly: Optional[int] = Field(None, ge=0)
    require_training_approval: Optional[bool] = None
    training_completion_threshold_percent: Optional[int] = Field(None, ge=0, le=100)

    # Compliance
    work_week_days: Optional[List[str]] = None
    standard_work_hours_per_day: Optional[Decimal] = Field(None, ge=0)
    max_work_hours_per_day: Optional[int] = Field(None, ge=1, le=24)

    # Display
    employee_id_format: Optional[EmployeeIDFormat] = None
    employee_id_prefix: Optional[str] = Field(None, max_length=10)
    employee_id_min_digits: Optional[int] = Field(None, ge=1, le=10)

    # Notifications
    notify_leave_balance_below: Optional[int] = Field(None, ge=0)
    notify_appraisal_due_days: Optional[int] = Field(None, ge=0)
    notify_probation_end_days: Optional[int] = Field(None, ge=0)
    notify_contract_expiry_days: Optional[int] = Field(None, ge=0)
    notify_document_expiry_days: Optional[int] = Field(None, ge=0)


# Holiday Calendar Schemas
class HolidayCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date: date
    is_optional: bool = False
    is_recurring: bool = False
    description: Optional[str] = None


class HolidayResponse(BaseModel):
    id: int
    name: str
    date: date
    is_optional: bool
    is_recurring: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class HolidayCalendarCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = None
    location: Optional[str] = None
    year: int
    is_default: bool = False
    holidays: List[HolidayCreate] = []


class HolidayCalendarResponse(BaseModel):
    id: int
    name: str
    company: Optional[str]
    location: Optional[str]
    year: int
    is_default: bool
    is_active: bool
    holidays: List[HolidayResponse]

    class Config:
        from_attributes = True


# Salary Band Schemas
class SalaryBandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    grade: Optional[str] = None
    currency: str = "NGN"
    min_salary: Decimal
    max_salary: Decimal
    mid_salary: Optional[Decimal] = None


class SalaryBandUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    grade: Optional[str] = None
    currency: Optional[str] = None
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None
    mid_salary: Optional[Decimal] = None


class SalaryBandResponse(BaseModel):
    id: int
    company: Optional[str]
    name: str
    grade: Optional[str]
    currency: str
    min_salary: Decimal
    max_salary: Decimal
    mid_salary: Optional[Decimal]
    is_active: bool

    class Config:
        from_attributes = True


# Leave Encashment Policy Schemas
class LeaveEncashmentPolicyCreate(BaseModel):
    leave_type_id: int
    is_encashable: bool = False
    max_encashment_days_yearly: int = Field(0, ge=0)
    min_balance_to_encash: int = Field(0, ge=0)
    encashment_rate_percent: Decimal = Field(Decimal("100.00"), ge=0, le=100)
    allow_partial_encashment: bool = True
    encash_on_separation: bool = True
    taxable: bool = True


class LeaveEncashmentPolicyResponse(BaseModel):
    id: int
    company: Optional[str]
    leave_type_id: int
    is_encashable: bool
    max_encashment_days_yearly: int
    min_balance_to_encash: int
    encashment_rate_percent: Decimal
    allow_partial_encashment: bool
    encash_on_separation: bool
    taxable: bool
    is_active: bool

    class Config:
        from_attributes = True


# Document Checklist Template Schemas
class ChecklistTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    template_type: str = Field(..., pattern="^(ONBOARDING|SEPARATION|CONFIRMATION)$")
    items: List[dict] = []  # [{"item": "ID Card", "required": true}, ...]


class ChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    template_type: Optional[str] = Field(None, pattern="^(ONBOARDING|SEPARATION|CONFIRMATION)$")
    items: Optional[List[dict]] = None


class ChecklistTemplateResponse(BaseModel):
    id: int
    company: Optional[str]
    name: str
    template_type: str
    items: List[dict]
    is_active: bool

    class Config:
        from_attributes = True


# =============================================================================
# HR SETTINGS ENDPOINTS
# =============================================================================

@router.get("", response_model=HRSettingsResponse, dependencies=[Depends(Require("hr:read"))])
def get_hr_settings(
    company: Optional[str] = Query(None, description="Company name (null for global settings)"),
    db: Session = Depends(get_db)
):
    """Get HR settings for company or global defaults"""
    settings = db.query(HRSettings).filter(HRSettings.company == company).first()

    if not settings:
        # Return global settings if company-specific not found
        settings = db.query(HRSettings).filter(HRSettings.company.is_(None)).first()

    if not settings:
        raise HTTPException(status_code=404, detail="HR settings not found. Run seed-defaults first.")

    return settings


@router.put("", response_model=HRSettingsResponse, dependencies=[Depends(Require("hr:admin"))])
def update_hr_settings(
    data: HRSettingsUpdate,
    company: Optional[str] = Query(None, description="Company name (null for global settings)"),
    db: Session = Depends(get_db)
):
    """Update HR settings"""
    settings = db.query(HRSettings).filter(HRSettings.company == company).first()

    if not settings:
        raise HTTPException(status_code=404, detail="HR settings not found")

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.post("/seed-defaults", dependencies=[Depends(Require("hr:admin"))])
def seed_hr_defaults(db: Session = Depends(get_db)):
    """Seed default HR settings if not exists"""
    existing = db.query(HRSettings).filter(HRSettings.company.is_(None)).first()
    if existing:
        return {"message": "Default HR settings already exist", "id": existing.id}

    settings = HRSettings(company=None)
    db.add(settings)
    db.commit()
    db.refresh(settings)

    return {"message": "Default HR settings created", "id": settings.id}


# =============================================================================
# HOLIDAY CALENDAR ENDPOINTS
# =============================================================================

@router.get("/holiday-calendars", response_model=List[HolidayCalendarResponse], dependencies=[Depends(Require("hr:read"))])
def list_holiday_calendars(
    company: Optional[str] = None,
    year: Optional[int] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List holiday calendars"""
    query = db.query(HolidayCalendar)

    if company is not None:
        query = query.filter(HolidayCalendar.company == company)
    if year is not None:
        query = query.filter(HolidayCalendar.year == year)
    if is_active is not None:
        query = query.filter(HolidayCalendar.is_active == is_active)

    return query.order_by(HolidayCalendar.year.desc(), HolidayCalendar.name).all()


@router.post("/holiday-calendars", response_model=HolidayCalendarResponse, dependencies=[Depends(Require("hr:write"))])
def create_holiday_calendar(data: HolidayCalendarCreate, db: Session = Depends(get_db)):
    """Create a new holiday calendar"""
    calendar = HolidayCalendar(
        name=data.name,
        company=data.company,
        location=data.location,
        year=data.year,
        is_default=data.is_default
    )
    db.add(calendar)
    db.flush()

    # Add holidays
    for h in data.holidays:
        holiday = HRHoliday(
            calendar_id=calendar.id,
            name=h.name,
            date=h.date,
            is_optional=h.is_optional,
            is_recurring=h.is_recurring,
            description=h.description
        )
        db.add(holiday)

    db.commit()
    db.refresh(calendar)
    return calendar


@router.get("/holiday-calendars/{calendar_id}", response_model=HolidayCalendarResponse, dependencies=[Depends(Require("hr:read"))])
def get_holiday_calendar(calendar_id: int, db: Session = Depends(get_db)):
    """Get a specific holiday calendar"""
    calendar = db.query(HolidayCalendar).filter(HolidayCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Holiday calendar not found")
    return calendar


@router.post("/holiday-calendars/{calendar_id}/holidays", response_model=HolidayResponse, dependencies=[Depends(Require("hr:write"))])
def add_holiday(calendar_id: int, data: HolidayCreate, db: Session = Depends(get_db)):
    """Add a holiday to a calendar"""
    calendar = db.query(HolidayCalendar).filter(HolidayCalendar.id == calendar_id).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Holiday calendar not found")

    holiday = HRHoliday(
        calendar_id=calendar_id,
        name=data.name,
        date=data.date,
        is_optional=data.is_optional,
        is_recurring=data.is_recurring,
        description=data.description
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/holiday-calendars/{calendar_id}/holidays/{holiday_id}", dependencies=[Depends(Require("hr:write"))])
def remove_holiday(calendar_id: int, holiday_id: int, db: Session = Depends(get_db)):
    """Remove a holiday from a calendar"""
    holiday = db.query(HRHoliday).filter(
        HRHoliday.id == holiday_id,
        HRHoliday.calendar_id == calendar_id
    ).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    db.delete(holiday)
    db.commit()
    return {"message": "Holiday removed"}


# =============================================================================
# SALARY BAND ENDPOINTS
# =============================================================================

@router.get("/salary-bands", response_model=List[SalaryBandResponse], dependencies=[Depends(Require("hr:read"))])
def list_salary_bands(
    company: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List salary bands"""
    query = db.query(SalaryBand)

    if company is not None:
        query = query.filter(SalaryBand.company == company)
    if is_active is not None:
        query = query.filter(SalaryBand.is_active == is_active)

    return query.order_by(SalaryBand.min_salary).all()


@router.post("/salary-bands", response_model=SalaryBandResponse, dependencies=[Depends(Require("hr:admin"))])
def create_salary_band(
    data: SalaryBandCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a new salary band"""
    if data.max_salary < data.min_salary:
        raise HTTPException(status_code=400, detail="Max salary must be >= min salary")

    band = SalaryBand(
        company=company,
        name=data.name,
        grade=data.grade,
        currency=data.currency,
        min_salary=data.min_salary,
        max_salary=data.max_salary,
        mid_salary=data.mid_salary or ((data.min_salary + data.max_salary) / 2)
    )
    db.add(band)
    db.commit()
    db.refresh(band)
    return band


@router.put("/salary-bands/{band_id}", response_model=SalaryBandResponse, dependencies=[Depends(Require("hr:admin"))])
def update_salary_band(band_id: int, data: SalaryBandUpdate, db: Session = Depends(get_db)):
    """Update a salary band (partial updates supported)."""
    band = db.query(SalaryBand).filter(SalaryBand.id == band_id).first()
    if not band:
        raise HTTPException(status_code=404, detail="Salary band not found")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return band

    # Validate salary bounds only when provided
    min_salary = update_data.get("min_salary", band.min_salary)
    max_salary = update_data.get("max_salary", band.max_salary)
    if max_salary < min_salary:
        raise HTTPException(status_code=400, detail="Max salary must be >= min salary")

    for key, value in update_data.items():
        setattr(band, key, value)

    # Recompute mid_salary when min/max updated and no explicit mid provided
    if ("min_salary" in update_data or "max_salary" in update_data) and "mid_salary" not in update_data:
        band.mid_salary = (min_salary + max_salary) / 2

    db.commit()
    db.refresh(band)
    return band


@router.delete("/salary-bands/{band_id}", dependencies=[Depends(Require("hr:admin"))])
def delete_salary_band(band_id: int, db: Session = Depends(get_db)):
    """Deactivate a salary band"""
    band = db.query(SalaryBand).filter(SalaryBand.id == band_id).first()
    if not band:
        raise HTTPException(status_code=404, detail="Salary band not found")

    band.is_active = False
    db.commit()
    return {"message": "Salary band deactivated"}


# =============================================================================
# LEAVE ENCASHMENT POLICY ENDPOINTS
# =============================================================================

@router.get("/leave-encashment-policies", response_model=List[LeaveEncashmentPolicyResponse], dependencies=[Depends(Require("hr:read"))])
def list_leave_encashment_policies(
    company: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List leave encashment policies"""
    query = db.query(LeaveEncashmentPolicy)

    if company is not None:
        query = query.filter(LeaveEncashmentPolicy.company == company)
    if is_active is not None:
        query = query.filter(LeaveEncashmentPolicy.is_active == is_active)

    return query.all()


@router.post("/leave-encashment-policies", response_model=LeaveEncashmentPolicyResponse, dependencies=[Depends(Require("hr:admin"))])
def create_leave_encashment_policy(
    data: LeaveEncashmentPolicyCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a leave encashment policy"""
    policy = LeaveEncashmentPolicy(
        company=company,
        leave_type_id=data.leave_type_id,
        is_encashable=data.is_encashable,
        max_encashment_days_yearly=data.max_encashment_days_yearly,
        min_balance_to_encash=data.min_balance_to_encash,
        encashment_rate_percent=data.encashment_rate_percent,
        allow_partial_encashment=data.allow_partial_encashment,
        encash_on_separation=data.encash_on_separation,
        taxable=data.taxable
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


# =============================================================================
# DOCUMENT CHECKLIST TEMPLATE ENDPOINTS
# =============================================================================

@router.get("/checklist-templates", response_model=List[ChecklistTemplateResponse], dependencies=[Depends(Require("hr:read"))])
def list_checklist_templates(
    company: Optional[str] = None,
    template_type: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List document checklist templates"""
    query = db.query(DocumentChecklistTemplate)

    if company is not None:
        query = query.filter(DocumentChecklistTemplate.company == company)
    if template_type is not None:
        query = query.filter(DocumentChecklistTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(DocumentChecklistTemplate.is_active == is_active)

    return query.all()


@router.post("/checklist-templates", response_model=ChecklistTemplateResponse, dependencies=[Depends(Require("hr:admin"))])
def create_checklist_template(
    data: ChecklistTemplateCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a document checklist template"""
    template = DocumentChecklistTemplate(
        company=company,
        name=data.name,
        template_type=data.template_type,
        items=data.items
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.put("/checklist-templates/{template_id}", response_model=ChecklistTemplateResponse, dependencies=[Depends(Require("hr:admin"))])
def update_checklist_template(template_id: int, data: ChecklistTemplateUpdate, db: Session = Depends(get_db)):
    """Update a checklist template (partial updates supported)."""
    template = db.query(DocumentChecklistTemplate).filter(DocumentChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/checklist-templates/{template_id}", dependencies=[Depends(Require("hr:admin"))])
def delete_checklist_template(template_id: int, db: Session = Depends(get_db)):
    """Deactivate a checklist template"""
    template = db.query(DocumentChecklistTemplate).filter(DocumentChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = False
    db.commit()
    return {"message": "Template deactivated"}
