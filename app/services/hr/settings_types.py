"""Type definitions for HR settings service.

These dataclasses define the contract for HR settings operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.models.hr_settings import (
    AppraisalFrequency,
    AttendanceMarkingMode,
    EmployeeIDFormat,
    EmploymentType,
    GratuityCalculation,
    LeaveAccountingFrequency,
    OvertimeCalculation,
    PayrollFrequency,
    ProRataMethod,
    WeekDay,
)

__all__ = [
    # HR Settings
    "HRSettingsData",
    "HRSettingsUpdateData",
    # Leave Encashment
    "LeaveEncashmentPolicyData",
    "LeaveEncashmentPolicyUpdateData",
    # Holiday Calendar
    "HolidayCalendarFilters",
    "HolidayCalendarCreateData",
    "HolidayCalendarUpdateData",
    "HolidayData",
    # Salary Band
    "SalaryBandFilters",
    "SalaryBandCreateData",
    "SalaryBandUpdateData",
    # Document Checklist
    "ChecklistTemplateFilters",
    "ChecklistTemplateCreateData",
    "ChecklistTemplateUpdateData",
    # Employment Type Deduction Config
    "DeductionConfigFilters",
    "DeductionConfigCreateData",
    "DeductionConfigUpdateData",
]


# ==============================================================================
# HR Settings Types
# ==============================================================================


@dataclass
class HRSettingsData:
    """HR Settings configuration data."""

    # Leave Policy Settings
    leave_accounting_frequency: LeaveAccountingFrequency = LeaveAccountingFrequency.ANNUAL
    pro_rata_method: ProRataMethod = ProRataMethod.WORKING_DAYS
    max_carryforward_days: int = 5
    carryforward_expiry_months: int = 3
    min_leave_notice_days: int = 1
    allow_negative_leave_balance: bool = False
    allow_leave_overlap: bool = False
    sick_leave_auto_approve_days: int = 2
    medical_certificate_required_after_days: int = 2

    # Attendance Settings
    attendance_marking_mode: AttendanceMarkingMode = AttendanceMarkingMode.MANUAL
    allow_backdated_attendance: bool = False
    backdated_attendance_days: int = 3
    auto_mark_absent_enabled: bool = True
    late_entry_grace_minutes: int = 15
    early_exit_grace_minutes: int = 15
    half_day_hours_threshold: Decimal = Decimal("4.00")
    full_day_hours_threshold: Decimal = Decimal("8.00")
    require_checkout: bool = True
    geolocation_required: bool = False
    geolocation_radius_meters: int = 100

    # Shift Settings
    default_shift_id: Optional[int] = None
    max_weekly_hours: int = 48
    night_shift_allowance_percent: Decimal = Decimal("10.00")
    shift_change_notice_days: int = 3

    # Payroll Settings
    payroll_frequency: PayrollFrequency = PayrollFrequency.MONTHLY
    salary_payment_day: int = 28
    payroll_cutoff_day: int = 25
    allow_salary_advance: bool = True
    max_advance_percent: Decimal = Decimal("50.00")
    max_advance_months: int = 2
    salary_currency: str = "NGN"

    # Overtime Settings
    overtime_enabled: bool = True
    overtime_calculation: OvertimeCalculation = OvertimeCalculation.HOURLY_RATE
    overtime_multiplier_weekday: Decimal = Decimal("1.50")
    overtime_multiplier_weekend: Decimal = Decimal("2.00")
    overtime_multiplier_holiday: Decimal = Decimal("2.50")
    min_overtime_hours: Decimal = Decimal("1.00")
    require_overtime_approval: bool = True

    # Benefits & Compensation
    gratuity_enabled: bool = True
    gratuity_calculation: GratuityCalculation = GratuityCalculation.LAST_SALARY
    gratuity_eligibility_years: int = 5
    gratuity_days_per_year: int = 15
    pf_enabled: bool = False
    pf_employer_percent: Decimal = Decimal("12.00")
    pf_employee_percent: Decimal = Decimal("12.00")
    pension_enabled: bool = True
    pension_employer_percent: Decimal = Decimal("10.00")
    pension_employee_percent: Decimal = Decimal("8.00")
    nhf_enabled: bool = True
    nhf_percent: Decimal = Decimal("2.50")

    # Employee Lifecycle
    default_probation_months: int = 3
    max_probation_extension_months: int = 3
    default_notice_period_days: int = 30
    require_exit_interview: bool = True
    final_settlement_days: int = 30
    require_clearance_before_settlement: bool = True

    # Recruitment Settings
    job_posting_validity_days: int = 30
    offer_validity_days: int = 7
    default_interview_duration_minutes: int = 60
    require_background_check: bool = False
    document_submission_days: int = 7
    allow_offer_negotiation: bool = True
    offer_negotiation_window_days: int = 3

    # Performance Appraisal
    appraisal_frequency: AppraisalFrequency = AppraisalFrequency.ANNUAL
    appraisal_cycle_start_month: int = 1
    appraisal_rating_scale: int = 5
    require_self_review: bool = True
    require_peer_review: bool = False
    enable_360_feedback: bool = False
    min_rating_for_promotion: Decimal = Decimal("4.0")

    # Training
    mandatory_training_hours_yearly: int = 40
    require_training_approval: bool = True
    training_completion_threshold_percent: int = 80

    # Compliance
    work_week_days: List[str] = field(
        default_factory=lambda: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
    )
    standard_work_hours_per_day: Decimal = Decimal("8.00")
    max_work_hours_per_day: int = 12

    # Display & Formatting
    employee_id_format: EmployeeIDFormat = EmployeeIDFormat.NUMERIC
    employee_id_prefix: str = "EMP"
    employee_id_min_digits: int = 4

    # Notifications
    notify_leave_balance_below: int = 3
    notify_appraisal_due_days: int = 7
    notify_probation_end_days: int = 14
    notify_contract_expiry_days: int = 30
    notify_document_expiry_days: int = 30


@dataclass
class HRSettingsUpdateData:
    """Data for updating HR settings (all fields optional)."""

    # All fields are optional for partial updates
    leave_accounting_frequency: Optional[LeaveAccountingFrequency] = None
    pro_rata_method: Optional[ProRataMethod] = None
    max_carryforward_days: Optional[int] = None
    carryforward_expiry_months: Optional[int] = None
    min_leave_notice_days: Optional[int] = None
    allow_negative_leave_balance: Optional[bool] = None
    allow_leave_overlap: Optional[bool] = None
    sick_leave_auto_approve_days: Optional[int] = None
    medical_certificate_required_after_days: Optional[int] = None

    attendance_marking_mode: Optional[AttendanceMarkingMode] = None
    allow_backdated_attendance: Optional[bool] = None
    backdated_attendance_days: Optional[int] = None
    auto_mark_absent_enabled: Optional[bool] = None
    late_entry_grace_minutes: Optional[int] = None
    early_exit_grace_minutes: Optional[int] = None
    half_day_hours_threshold: Optional[Decimal] = None
    full_day_hours_threshold: Optional[Decimal] = None
    require_checkout: Optional[bool] = None
    geolocation_required: Optional[bool] = None
    geolocation_radius_meters: Optional[int] = None

    default_shift_id: Optional[int] = None
    max_weekly_hours: Optional[int] = None
    night_shift_allowance_percent: Optional[Decimal] = None
    shift_change_notice_days: Optional[int] = None

    payroll_frequency: Optional[PayrollFrequency] = None
    salary_payment_day: Optional[int] = None
    payroll_cutoff_day: Optional[int] = None
    allow_salary_advance: Optional[bool] = None
    max_advance_percent: Optional[Decimal] = None
    max_advance_months: Optional[int] = None
    salary_currency: Optional[str] = None

    overtime_enabled: Optional[bool] = None
    overtime_calculation: Optional[OvertimeCalculation] = None
    overtime_multiplier_weekday: Optional[Decimal] = None
    overtime_multiplier_weekend: Optional[Decimal] = None
    overtime_multiplier_holiday: Optional[Decimal] = None
    min_overtime_hours: Optional[Decimal] = None
    require_overtime_approval: Optional[bool] = None

    gratuity_enabled: Optional[bool] = None
    gratuity_calculation: Optional[GratuityCalculation] = None
    gratuity_eligibility_years: Optional[int] = None
    gratuity_days_per_year: Optional[int] = None
    pf_enabled: Optional[bool] = None
    pf_employer_percent: Optional[Decimal] = None
    pf_employee_percent: Optional[Decimal] = None
    pension_enabled: Optional[bool] = None
    pension_employer_percent: Optional[Decimal] = None
    pension_employee_percent: Optional[Decimal] = None
    nhf_enabled: Optional[bool] = None
    nhf_percent: Optional[Decimal] = None

    default_probation_months: Optional[int] = None
    max_probation_extension_months: Optional[int] = None
    default_notice_period_days: Optional[int] = None
    require_exit_interview: Optional[bool] = None
    final_settlement_days: Optional[int] = None
    require_clearance_before_settlement: Optional[bool] = None

    job_posting_validity_days: Optional[int] = None
    offer_validity_days: Optional[int] = None
    default_interview_duration_minutes: Optional[int] = None
    require_background_check: Optional[bool] = None
    document_submission_days: Optional[int] = None
    allow_offer_negotiation: Optional[bool] = None
    offer_negotiation_window_days: Optional[int] = None

    appraisal_frequency: Optional[AppraisalFrequency] = None
    appraisal_cycle_start_month: Optional[int] = None
    appraisal_rating_scale: Optional[int] = None
    require_self_review: Optional[bool] = None
    require_peer_review: Optional[bool] = None
    enable_360_feedback: Optional[bool] = None
    min_rating_for_promotion: Optional[Decimal] = None

    mandatory_training_hours_yearly: Optional[int] = None
    require_training_approval: Optional[bool] = None
    training_completion_threshold_percent: Optional[int] = None

    work_week_days: Optional[List[str]] = None
    standard_work_hours_per_day: Optional[Decimal] = None
    max_work_hours_per_day: Optional[int] = None

    employee_id_format: Optional[EmployeeIDFormat] = None
    employee_id_prefix: Optional[str] = None
    employee_id_min_digits: Optional[int] = None

    notify_leave_balance_below: Optional[int] = None
    notify_appraisal_due_days: Optional[int] = None
    notify_probation_end_days: Optional[int] = None
    notify_contract_expiry_days: Optional[int] = None
    notify_document_expiry_days: Optional[int] = None


# ==============================================================================
# Leave Encashment Policy Types
# ==============================================================================


@dataclass
class LeaveEncashmentPolicyData:
    """Data for leave encashment policy."""

    leave_type_id: int
    company: Optional[str] = None
    is_encashable: bool = False
    max_encashment_days_yearly: int = 0
    min_balance_to_encash: int = 0
    encashment_rate_percent: Decimal = Decimal("100.00")
    allow_partial_encashment: bool = True
    encash_on_separation: bool = True
    taxable: bool = True
    is_active: bool = True


@dataclass
class LeaveEncashmentPolicyUpdateData:
    """Data for updating leave encashment policy (all fields optional)."""

    is_encashable: Optional[bool] = None
    max_encashment_days_yearly: Optional[int] = None
    min_balance_to_encash: Optional[int] = None
    encashment_rate_percent: Optional[Decimal] = None
    allow_partial_encashment: Optional[bool] = None
    encash_on_separation: Optional[bool] = None
    taxable: Optional[bool] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Holiday Calendar Types
# ==============================================================================


@dataclass
class HolidayData:
    """Individual holiday data."""

    name: str
    date: date
    is_optional: bool = False
    is_recurring: bool = False
    description: Optional[str] = None


@dataclass
class HolidayCalendarFilters:
    """Filters for listing holiday calendars."""

    company: Optional[str] = None
    location: Optional[str] = None
    year: Optional[int] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None


@dataclass
class HolidayCalendarCreateData:
    """Data for creating a holiday calendar."""

    name: str
    year: int
    company: Optional[str] = None
    location: Optional[str] = None
    is_default: bool = False
    holidays: List[HolidayData] = field(default_factory=list)


@dataclass
class HolidayCalendarUpdateData:
    """Data for updating a holiday calendar (all fields optional)."""

    name: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    holidays: Optional[List[HolidayData]] = None


# ==============================================================================
# Salary Band Types
# ==============================================================================


@dataclass
class SalaryBandFilters:
    """Filters for listing salary bands."""

    company: Optional[str] = None
    grade: Optional[str] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None


@dataclass
class SalaryBandCreateData:
    """Data for creating a salary band."""

    name: str
    min_salary: Decimal
    max_salary: Decimal
    company: Optional[str] = None
    grade: Optional[str] = None
    currency: str = "NGN"
    mid_salary: Optional[Decimal] = None


@dataclass
class SalaryBandUpdateData:
    """Data for updating a salary band (all fields optional)."""

    name: Optional[str] = None
    grade: Optional[str] = None
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None
    mid_salary: Optional[Decimal] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Document Checklist Template Types
# ==============================================================================


@dataclass
class ChecklistTemplateFilters:
    """Filters for listing checklist templates."""

    company: Optional[str] = None
    template_type: Optional[str] = None  # ONBOARDING, SEPARATION, CONFIRMATION
    is_active: Optional[bool] = None
    search: Optional[str] = None


@dataclass
class ChecklistTemplateCreateData:
    """Data for creating a checklist template."""

    name: str
    template_type: str  # ONBOARDING, SEPARATION, CONFIRMATION
    company: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ChecklistTemplateUpdateData:
    """Data for updating a checklist template (all fields optional)."""

    name: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Employment Type Deduction Config Types
# ==============================================================================


@dataclass
class DeductionConfigFilters:
    """Filters for listing deduction configs."""

    company: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    is_active: Optional[bool] = None


@dataclass
class DeductionConfigCreateData:
    """Data for creating a deduction config."""

    employment_type: EmploymentType
    display_name: str
    company: Optional[str] = None
    description: Optional[str] = None
    paye_applicable: bool = True
    pension_applicable: bool = True
    nhf_applicable: bool = True
    nhis_applicable: bool = True
    nsitf_applicable: bool = True
    itf_applicable: bool = True
    pension_min_service_months: int = 0
    counts_for_itf_headcount: bool = True
    gratuity_eligible: bool = True
    gratuity_min_service_years: int = 5
    is_payroll_employee: bool = True


@dataclass
class DeductionConfigUpdateData:
    """Data for updating a deduction config (all fields optional)."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    paye_applicable: Optional[bool] = None
    pension_applicable: Optional[bool] = None
    nhf_applicable: Optional[bool] = None
    nhis_applicable: Optional[bool] = None
    nsitf_applicable: Optional[bool] = None
    itf_applicable: Optional[bool] = None
    pension_min_service_months: Optional[int] = None
    counts_for_itf_headcount: Optional[bool] = None
    gratuity_eligible: Optional[bool] = None
    gratuity_min_service_years: Optional[int] = None
    is_payroll_employee: Optional[bool] = None
    is_active: Optional[bool] = None
