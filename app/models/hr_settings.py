"""HR Settings Models

Comprehensive HR configuration including leave policies, attendance rules,
payroll settings, lifecycle management, and compliance parameters.
"""
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Time,
    Numeric, Text, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class ProRataMethod(str, Enum):
    """Method for calculating pro-rata leave/benefits"""
    LINEAR = "LINEAR"  # Simple proportional calculation
    CALENDAR_DAYS = "CALENDAR_DAYS"  # Based on calendar days
    WORKING_DAYS = "WORKING_DAYS"  # Based on actual working days
    MONTHLY = "MONTHLY"  # Full month allocation


class LeaveAccountingFrequency(str, Enum):
    """When leave is credited to employees"""
    ANNUAL = "ANNUAL"  # Full allocation at year start
    MONTHLY = "MONTHLY"  # Monthly accrual
    QUARTERLY = "QUARTERLY"  # Quarterly accrual
    BIANNUAL = "BIANNUAL"  # Twice yearly


class PayrollFrequency(str, Enum):
    """How often payroll is processed"""
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    SEMIMONTHLY = "SEMIMONTHLY"  # Twice a month (1st and 15th)


class OvertimeCalculation(str, Enum):
    """How overtime is calculated"""
    HOURLY_RATE = "HOURLY_RATE"  # Based on hourly rate
    DAILY_RATE = "DAILY_RATE"  # Based on daily rate
    MONTHLY_RATE = "MONTHLY_RATE"  # Based on monthly salary


class GratuityCalculation(str, Enum):
    """How gratuity is calculated"""
    LAST_SALARY = "LAST_SALARY"  # Based on last drawn salary
    AVERAGE_SALARY = "AVERAGE_SALARY"  # Average of last X months
    BASIC_SALARY = "BASIC_SALARY"  # Based on basic salary only


class EmployeeIDFormat(str, Enum):
    """Format for generating employee IDs"""
    NUMERIC = "NUMERIC"  # EMP001, EMP002
    ALPHANUMERIC = "ALPHANUMERIC"  # EMP-A001
    YEAR_BASED = "YEAR_BASED"  # EMP-2024-001
    DEPARTMENT_BASED = "DEPARTMENT_BASED"  # IT-001, HR-002


class AttendanceMarkingMode(str, Enum):
    """How attendance can be marked"""
    MANUAL = "MANUAL"  # Manual entry only
    BIOMETRIC = "BIOMETRIC"  # Biometric devices
    GEOLOCATION = "GEOLOCATION"  # GPS-based
    HYBRID = "HYBRID"  # Multiple methods allowed


class EmploymentType(str, Enum):
    """
    Standard employment types for Nigerian organizations.

    Tax implications:
    - All types on payroll are subject to PAYE
    - Independent contractors (not on payroll) use WHT instead
    - Statutory deductions (Pension, NHF, NHIS) may vary by type
    """
    PERMANENT = "PERMANENT"  # Full-time permanent staff
    CONTRACT = "CONTRACT"  # Fixed-term contract employees
    PART_TIME = "PART_TIME"  # Part-time employees
    INTERN = "INTERN"  # Interns/Industrial trainees (SIWES)
    NYSC = "NYSC"  # National Youth Service Corps members
    PROBATION = "PROBATION"  # Probationary employees
    CASUAL = "CASUAL"  # Casual/daily workers
    CONSULTANT = "CONSULTANT"  # In-house consultants (on payroll)
    EXPATRIATE = "EXPATRIATE"  # Foreign/expatriate staff


class AppraisalFrequency(str, Enum):
    """How often performance appraisals occur"""
    ANNUAL = "ANNUAL"
    SEMIANNUAL = "SEMIANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


class WeekDay(str, Enum):
    """Days of the week"""
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


# =============================================================================
# HR SETTINGS MODEL
# =============================================================================

class HRSettings(Base):
    """Company-wide HR configuration settings"""
    __tablename__ = "hr_settings"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, unique=True, index=True)

    # -------------------------------------------------------------------------
    # LEAVE POLICY SETTINGS
    # -------------------------------------------------------------------------
    leave_accounting_frequency: Mapped[LeaveAccountingFrequency] = mapped_column(
        SAEnum(LeaveAccountingFrequency, name="leaveaccountingfrequency"),
        nullable=False, default=LeaveAccountingFrequency.ANNUAL
    )
    pro_rata_method: Mapped[ProRataMethod] = mapped_column(
        SAEnum(ProRataMethod, name="proratamethod"),
        nullable=False, default=ProRataMethod.WORKING_DAYS
    )
    max_carryforward_days = Column(Integer, nullable=False, default=5)
    carryforward_expiry_months = Column(Integer, nullable=False, default=3)  # Months after year start
    min_leave_notice_days = Column(Integer, nullable=False, default=1)
    allow_negative_leave_balance = Column(Boolean, nullable=False, default=False)
    allow_leave_overlap = Column(Boolean, nullable=False, default=False)
    sick_leave_auto_approve_days = Column(Integer, nullable=False, default=2)  # Auto-approve if <= X days
    medical_certificate_required_after_days = Column(Integer, nullable=False, default=2)

    # -------------------------------------------------------------------------
    # ATTENDANCE SETTINGS
    # -------------------------------------------------------------------------
    attendance_marking_mode: Mapped[AttendanceMarkingMode] = mapped_column(
        SAEnum(AttendanceMarkingMode, name="attendancemarkingmode"),
        nullable=False, default=AttendanceMarkingMode.MANUAL
    )
    allow_backdated_attendance = Column(Boolean, nullable=False, default=False)
    backdated_attendance_days = Column(Integer, nullable=False, default=3)
    auto_mark_absent_enabled = Column(Boolean, nullable=False, default=True)
    auto_absent_cutoff_time = Column(Time, nullable=True)  # Mark absent after this time
    late_entry_grace_minutes = Column(Integer, nullable=False, default=15)
    early_exit_grace_minutes = Column(Integer, nullable=False, default=15)
    half_day_hours_threshold = Column(Numeric(4, 2), nullable=False, default=Decimal("4.00"))
    full_day_hours_threshold = Column(Numeric(4, 2), nullable=False, default=Decimal("8.00"))
    require_checkout = Column(Boolean, nullable=False, default=True)
    geolocation_required = Column(Boolean, nullable=False, default=False)
    geolocation_radius_meters = Column(Integer, nullable=False, default=100)

    # -------------------------------------------------------------------------
    # SHIFT SETTINGS
    # -------------------------------------------------------------------------
    default_shift_id = Column(Integer, nullable=True)  # FK to shift_types.id - not enforced in model
    max_weekly_hours = Column(Integer, nullable=False, default=48)
    night_shift_allowance_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("10.00"))
    shift_change_notice_days = Column(Integer, nullable=False, default=3)

    # -------------------------------------------------------------------------
    # PAYROLL SETTINGS
    # -------------------------------------------------------------------------
    payroll_frequency: Mapped[PayrollFrequency] = mapped_column(
        SAEnum(PayrollFrequency, name="payrollfrequency"),
        nullable=False, default=PayrollFrequency.MONTHLY
    )
    salary_payment_day = Column(Integer, nullable=False, default=28)  # Day of month (1-31, 0 = last day)
    payroll_cutoff_day = Column(Integer, nullable=False, default=25)  # Stop changes after this day
    allow_salary_advance = Column(Boolean, nullable=False, default=True)
    max_advance_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("50.00"))
    max_advance_months = Column(Integer, nullable=False, default=2)
    salary_currency = Column(String(3), nullable=False, default="NGN")

    # -------------------------------------------------------------------------
    # OVERTIME SETTINGS
    # -------------------------------------------------------------------------
    overtime_enabled = Column(Boolean, nullable=False, default=True)
    overtime_calculation: Mapped[OvertimeCalculation] = mapped_column(
        SAEnum(OvertimeCalculation, name="overtimecalculation"),
        nullable=False, default=OvertimeCalculation.HOURLY_RATE
    )
    overtime_multiplier_weekday = Column(Numeric(4, 2), nullable=False, default=Decimal("1.50"))
    overtime_multiplier_weekend = Column(Numeric(4, 2), nullable=False, default=Decimal("2.00"))
    overtime_multiplier_holiday = Column(Numeric(4, 2), nullable=False, default=Decimal("2.50"))
    min_overtime_hours = Column(Numeric(4, 2), nullable=False, default=Decimal("1.00"))
    require_overtime_approval = Column(Boolean, nullable=False, default=True)

    # -------------------------------------------------------------------------
    # BENEFITS & COMPENSATION
    # -------------------------------------------------------------------------
    gratuity_enabled = Column(Boolean, nullable=False, default=True)
    gratuity_calculation: Mapped[GratuityCalculation] = mapped_column(
        SAEnum(GratuityCalculation, name="gratuitycalculation"),
        nullable=False, default=GratuityCalculation.LAST_SALARY
    )
    gratuity_eligibility_years = Column(Integer, nullable=False, default=5)
    gratuity_days_per_year = Column(Integer, nullable=False, default=15)  # Days of salary per year

    pf_enabled = Column(Boolean, nullable=False, default=False)
    pf_employer_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("12.00"))
    pf_employee_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("12.00"))

    pension_enabled = Column(Boolean, nullable=False, default=True)
    pension_employer_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("10.00"))
    pension_employee_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("8.00"))

    nhf_enabled = Column(Boolean, nullable=False, default=True)  # National Housing Fund (Nigeria)
    nhf_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("2.50"))

    # -------------------------------------------------------------------------
    # EMPLOYEE LIFECYCLE
    # -------------------------------------------------------------------------
    default_probation_months = Column(Integer, nullable=False, default=3)
    max_probation_extension_months = Column(Integer, nullable=False, default=3)
    default_notice_period_days = Column(Integer, nullable=False, default=30)
    require_exit_interview = Column(Boolean, nullable=False, default=True)
    final_settlement_days = Column(Integer, nullable=False, default=30)  # Days after separation
    require_clearance_before_settlement = Column(Boolean, nullable=False, default=True)

    # -------------------------------------------------------------------------
    # RECRUITMENT SETTINGS
    # -------------------------------------------------------------------------
    job_posting_validity_days = Column(Integer, nullable=False, default=30)
    offer_validity_days = Column(Integer, nullable=False, default=7)
    default_interview_duration_minutes = Column(Integer, nullable=False, default=60)
    require_background_check = Column(Boolean, nullable=False, default=False)
    document_submission_days = Column(Integer, nullable=False, default=7)  # After offer acceptance
    allow_offer_negotiation = Column(Boolean, nullable=False, default=True)
    offer_negotiation_window_days = Column(Integer, nullable=False, default=3)

    # -------------------------------------------------------------------------
    # PERFORMANCE APPRAISAL
    # -------------------------------------------------------------------------
    appraisal_frequency: Mapped[AppraisalFrequency] = mapped_column(
        SAEnum(AppraisalFrequency, name="appraisalfrequency"),
        nullable=False, default=AppraisalFrequency.ANNUAL
    )
    appraisal_cycle_start_month = Column(Integer, nullable=False, default=1)  # January
    appraisal_rating_scale = Column(Integer, nullable=False, default=5)  # 1-5 scale
    require_self_review = Column(Boolean, nullable=False, default=True)
    require_peer_review = Column(Boolean, nullable=False, default=False)
    enable_360_feedback = Column(Boolean, nullable=False, default=False)
    min_rating_for_promotion = Column(Numeric(3, 1), nullable=False, default=Decimal("4.0"))

    # -------------------------------------------------------------------------
    # TRAINING & DEVELOPMENT
    # -------------------------------------------------------------------------
    mandatory_training_hours_yearly = Column(Integer, nullable=False, default=40)
    require_training_approval = Column(Boolean, nullable=False, default=True)
    training_completion_threshold_percent = Column(Integer, nullable=False, default=80)

    # -------------------------------------------------------------------------
    # COMPLIANCE & STATUTORY
    # -------------------------------------------------------------------------
    work_week_days = Column(JSON, nullable=False, default=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"])
    standard_work_hours_per_day = Column(Numeric(4, 2), nullable=False, default=Decimal("8.00"))
    max_work_hours_per_day = Column(Integer, nullable=False, default=12)

    # -------------------------------------------------------------------------
    # DISPLAY & FORMATTING
    # -------------------------------------------------------------------------
    employee_id_format: Mapped[EmployeeIDFormat] = mapped_column(
        SAEnum(EmployeeIDFormat, name="employeeidformat"),
        nullable=False, default=EmployeeIDFormat.NUMERIC
    )
    employee_id_prefix = Column(String(10), nullable=False, default="EMP")
    employee_id_min_digits = Column(Integer, nullable=False, default=4)

    # -------------------------------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------------------------------
    notify_leave_balance_below = Column(Integer, nullable=False, default=3)  # Notify when balance <= X
    notify_appraisal_due_days = Column(Integer, nullable=False, default=7)  # Days before due
    notify_probation_end_days = Column(Integer, nullable=False, default=14)
    notify_contract_expiry_days = Column(Integer, nullable=False, default=30)
    notify_document_expiry_days = Column(Integer, nullable=False, default=30)

    # -------------------------------------------------------------------------
    # TIMESTAMPS & AUDIT
    # -------------------------------------------------------------------------
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    updated_by = relationship("User", foreign_keys=[updated_by_id])


# =============================================================================
# LEAVE ENCASHMENT POLICY
# =============================================================================

class LeaveEncashmentPolicy(Base):
    """Configuration for leave encashment by leave type"""
    __tablename__ = "leave_encashment_policies"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False, index=True)

    # Encashment rules
    is_encashable = Column(Boolean, nullable=False, default=False)
    max_encashment_days_yearly = Column(Integer, nullable=False, default=0)
    min_balance_to_encash = Column(Integer, nullable=False, default=0)  # Minimum days remaining
    encashment_rate_percent = Column(Numeric(5, 2), nullable=False, default=Decimal("100.00"))  # % of daily salary
    allow_partial_encashment = Column(Boolean, nullable=False, default=True)
    encash_on_separation = Column(Boolean, nullable=False, default=True)
    taxable = Column(Boolean, nullable=False, default=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Note: leave_type relationship removed - access via leave_type_id FK

    __table_args__ = (
        UniqueConstraint("company", "leave_type_id", name="uq_encashment_policy_company_leave_type"),
    )


# =============================================================================
# HOLIDAY CALENDAR
# =============================================================================

class HolidayCalendar(Base):
    """Holiday calendar for different companies/locations"""
    __tablename__ = "holiday_calendars"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    company = Column(String(255), nullable=True, index=True)
    location = Column(String(255), nullable=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    holidays = relationship("HRHoliday", back_populates="calendar", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        UniqueConstraint("company", "location", "year", name="uq_holiday_calendar_company_location_year"),
    )


class HRHoliday(Base):
    """Individual holidays within a calendar"""
    __tablename__ = "hr_holidays"

    id = Column(Integer, primary_key=True)
    calendar_id = Column(Integer, ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False, index=True)
    is_optional = Column(Boolean, nullable=False, default=False)  # Optional holiday
    is_recurring = Column(Boolean, nullable=False, default=False)  # Repeat every year
    description = Column(Text, nullable=True)

    # Relationships
    calendar = relationship("HolidayCalendar", back_populates="holidays")

    __table_args__ = (
        UniqueConstraint("calendar_id", "date", name="uq_hr_holiday_calendar_date"),
    )


# =============================================================================
# SALARY BAND
# =============================================================================

class SalaryBand(Base):
    """Salary ranges by grade/designation"""
    __tablename__ = "salary_bands"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "Grade A", "Senior Engineer"
    grade = Column(String(50), nullable=True, index=True)  # e.g., "L1", "L2", "M1"

    # Salary range
    currency = Column(String(3), nullable=False, default="NGN")
    min_salary = Column(Numeric(18, 2), nullable=False)
    max_salary = Column(Numeric(18, 2), nullable=False)
    mid_salary = Column(Numeric(18, 2), nullable=True)  # Target/reference salary

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company", "name", name="uq_salary_band_company_name"),
    )


# =============================================================================
# DOCUMENT CHECKLIST TEMPLATE
# =============================================================================

class DocumentChecklistTemplate(Base):
    """Checklist templates for onboarding/separation"""
    __tablename__ = "document_checklist_templates"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    template_type = Column(String(20), nullable=False, index=True)  # ONBOARDING, SEPARATION, CONFIRMATION
    items = Column(JSON, nullable=False, default=[])  # List of checklist items
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("company", "name", "template_type", name="uq_checklist_template_company_name_type"),
    )


# =============================================================================
# EMPLOYMENT TYPE DEDUCTION CONFIGURATION
# =============================================================================

class EmploymentTypeDeductionConfig(Base):
    """
    Configures which statutory deductions apply to each employment type.

    Nigerian statutory deductions:
    - PAYE: Income tax (applies to all on payroll)
    - Pension: 8% employee + 10% employer (PenCom)
    - NHF: 2.5% National Housing Fund
    - NHIS: 5% employee + 10% employer health insurance
    - NSITF: 1% employer social insurance
    - ITF: 1% employer training levy

    Some employment types may be exempt from certain deductions:
    - NYSC: Exempt from pension (federal allowance)
    - Interns: Often exempt from pension, NHF
    - Casual workers: May be exempt from pension (< 3 months)
    - Contract staff: Company policy varies
    """
    __tablename__ = "employment_type_deduction_configs"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)

    # Employment type this config applies to
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name="employmenttype"),
        nullable=False, index=True
    )

    # Display name for UI
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Statutory deduction eligibility
    paye_applicable = Column(Boolean, nullable=False, default=True)  # Income tax - almost always applies
    pension_applicable = Column(Boolean, nullable=False, default=True)  # PenCom pension
    nhf_applicable = Column(Boolean, nullable=False, default=True)  # National Housing Fund
    nhis_applicable = Column(Boolean, nullable=False, default=True)  # Health insurance
    nsitf_applicable = Column(Boolean, nullable=False, default=True)  # NSITF (employer)
    itf_applicable = Column(Boolean, nullable=False, default=True)  # ITF (employer)

    # Minimum service period for pension (months) - PenCom requires 3+ months
    pension_min_service_months = Column(Integer, nullable=False, default=0)

    # Whether this type counts towards headcount for ITF calculation
    # ITF applies to companies with 5+ employees OR turnover > N50M
    counts_for_itf_headcount = Column(Boolean, nullable=False, default=True)

    # Is this employee type eligible for gratuity?
    gratuity_eligible = Column(Boolean, nullable=False, default=True)
    gratuity_min_service_years = Column(Integer, nullable=False, default=5)

    # Is this a "on-payroll" type (vs vendor/contractor paid via AP)?
    is_payroll_employee = Column(Boolean, nullable=False, default=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("company", "employment_type", name="uq_employment_type_config_company_type"),
    )


# Default configurations for Nigerian employment types
DEFAULT_EMPLOYMENT_TYPE_CONFIGS = [
    {
        "employment_type": EmploymentType.PERMANENT,
        "display_name": "Permanent Staff",
        "description": "Full-time permanent employees",
        "paye_applicable": True,
        "pension_applicable": True,
        "nhf_applicable": True,
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 0,
        "gratuity_eligible": True,
        "gratuity_min_service_years": 5,
    },
    {
        "employment_type": EmploymentType.CONTRACT,
        "display_name": "Contract Staff",
        "description": "Fixed-term contract employees",
        "paye_applicable": True,
        "pension_applicable": True,  # PenCom applies if > 3 months
        "nhf_applicable": False,  # Often excluded
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 3,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.PART_TIME,
        "display_name": "Part-Time Staff",
        "description": "Part-time employees",
        "paye_applicable": True,
        "pension_applicable": True,
        "nhf_applicable": False,
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 3,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.INTERN,
        "display_name": "Intern / SIWES",
        "description": "Industrial training students",
        "paye_applicable": True,  # If paid above threshold
        "pension_applicable": False,  # Not eligible
        "nhf_applicable": False,
        "nhis_applicable": False,
        "nsitf_applicable": False,
        "itf_applicable": False,
        "pension_min_service_months": 0,
        "counts_for_itf_headcount": False,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.NYSC,
        "display_name": "NYSC Corps Member",
        "description": "National Youth Service Corps members",
        "paye_applicable": False,  # Federal allowance exempt
        "pension_applicable": False,
        "nhf_applicable": False,
        "nhis_applicable": False,
        "nsitf_applicable": False,
        "itf_applicable": False,
        "pension_min_service_months": 0,
        "counts_for_itf_headcount": False,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.PROBATION,
        "display_name": "Probationary Staff",
        "description": "Employees on probation period",
        "paye_applicable": True,
        "pension_applicable": True,
        "nhf_applicable": True,
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 0,
        "gratuity_eligible": True,  # Probation counts towards service
        "gratuity_min_service_years": 5,
    },
    {
        "employment_type": EmploymentType.CASUAL,
        "display_name": "Casual Worker",
        "description": "Daily/casual workers",
        "paye_applicable": True,  # If paid above threshold
        "pension_applicable": False,  # < 3 months typically
        "nhf_applicable": False,
        "nhis_applicable": False,
        "nsitf_applicable": False,
        "itf_applicable": False,
        "pension_min_service_months": 3,
        "counts_for_itf_headcount": False,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.CONSULTANT,
        "display_name": "In-house Consultant",
        "description": "Consultants on company payroll",
        "paye_applicable": True,
        "pension_applicable": False,  # Usually excluded
        "nhf_applicable": False,
        "nhis_applicable": False,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 0,
        "gratuity_eligible": False,
        "gratuity_min_service_years": 0,
    },
    {
        "employment_type": EmploymentType.EXPATRIATE,
        "display_name": "Expatriate Staff",
        "description": "Foreign/expatriate employees",
        "paye_applicable": True,
        "pension_applicable": True,  # Can opt for home country pension
        "nhf_applicable": False,  # Not applicable
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 0,
        "gratuity_eligible": True,
        "gratuity_min_service_years": 5,
    },
]
