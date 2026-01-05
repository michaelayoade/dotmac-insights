"""Type definitions for statutory compliance calculations.

These dataclasses define the contract for compliance operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set

__all__ = [
    # Enums
    "DeductionType",
    # Configuration
    "DeductionConfig",
    "EmployeeDeductionConfig",
    # Input types
    "SalaryInput",
    "EmployeeInfo",
    # Result types
    "DeductionResult",
    "DeductionBreakdown",
    "ComplianceResult",
    "ScheduleEntry",
    "ComplianceSchedule",
    # Summary types
    "PayrollComplianceSummary",
    "DeductionTotals",
]


class DeductionType(str, Enum):
    """Standard statutory deduction types."""

    PAYE = "PAYE"  # Income Tax
    PENSION = "PENSION"  # Pension contribution
    NHF = "NHF"  # National Housing Fund
    NHIS = "NHIS"  # National Health Insurance
    NSITF = "NSITF"  # Employee Compensation (NSITF)
    ITF = "ITF"  # Industrial Training Fund

    def __str__(self) -> str:
        return self.value


# ==============================================================================
# Configuration Types
# ==============================================================================


@dataclass
class DeductionConfig:
    """Configuration for a deduction type."""

    deduction_type: DeductionType
    enabled: bool = True
    employee_rate: Optional[Decimal] = None  # Override rate for employee
    employer_rate: Optional[Decimal] = None  # Override rate for employer
    cap: Optional[Decimal] = None  # Maximum amount cap
    floor: Optional[Decimal] = None  # Minimum amount floor


@dataclass
class EmployeeDeductionConfig:
    """Per-employee deduction configuration."""

    employee_id: int
    enabled_deductions: Set[str] = field(default_factory=set)
    overrides: Dict[str, DeductionConfig] = field(default_factory=dict)


# ==============================================================================
# Input Types
# ==============================================================================


@dataclass
class SalaryInput:
    """Salary components for compliance calculations."""

    basic_salary: Decimal = Decimal("0")
    housing_allowance: Decimal = Decimal("0")
    transport_allowance: Decimal = Decimal("0")
    utility_allowance: Decimal = Decimal("0")
    meal_allowance: Decimal = Decimal("0")
    other_allowances: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    benefits_in_kind: Decimal = Decimal("0")

    @property
    def gross_salary(self) -> Decimal:
        """Calculate gross salary."""
        return (
            self.basic_salary
            + self.housing_allowance
            + self.transport_allowance
            + self.utility_allowance
            + self.meal_allowance
            + self.other_allowances
            + self.bonus
            + self.benefits_in_kind
        )


@dataclass
class EmployeeInfo:
    """Employee information for compliance calculations."""

    employee_id: int
    employment_type: str = "permanent"  # permanent, contract, etc.
    state_of_residence: Optional[str] = None  # For state-specific calculations
    date_of_birth: Optional[date] = None  # For age-based rules
    pension_pin: Optional[str] = None  # For pension registration
    tax_id: Optional[str] = None  # Tax identification number
    nhf_number: Optional[str] = None  # NHF registration number


# ==============================================================================
# Result Types
# ==============================================================================


@dataclass
class DeductionBreakdown:
    """Detailed breakdown of a deduction calculation."""

    item: str
    description: str
    amount: Decimal
    is_taxable: bool = True


@dataclass
class DeductionResult:
    """Result of calculating a single deduction."""

    deduction_type: DeductionType
    employee_amount: Decimal = Decimal("0")
    employer_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    taxable_amount: Decimal = Decimal("0")  # Amount to include in taxable income
    breakdown: List[DeductionBreakdown] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total_amount == Decimal("0"):
            self.total_amount = self.employee_amount + self.employer_amount


@dataclass
class ComplianceResult:
    """Complete compliance calculation result for an employee."""

    employee_id: int
    period_start: date
    period_end: date
    region_code: str
    gross_salary: Decimal
    taxable_income: Decimal
    deductions: Dict[str, DeductionResult] = field(default_factory=dict)
    total_employee_deductions: Decimal = Decimal("0")
    total_employer_contributions: Decimal = Decimal("0")
    net_pay: Decimal = Decimal("0")
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_deduction(self, deduction_type: str) -> Optional[DeductionResult]:
        """Get a specific deduction result."""
        return self.deductions.get(deduction_type)


# ==============================================================================
# Schedule Types
# ==============================================================================


@dataclass
class ScheduleEntry:
    """Entry in a compliance schedule (remittance list)."""

    employee_id: int
    employee_name: str
    employee_number: Optional[str]
    registration_number: Optional[str]  # Tax ID, Pension PIN, etc.
    gross_salary: Decimal
    employee_amount: Decimal
    employer_amount: Decimal
    total_amount: Decimal
    notes: Optional[str] = None


@dataclass
class ComplianceSchedule:
    """Schedule for statutory remittance."""

    deduction_type: DeductionType
    period_start: date
    period_end: date
    company: str
    region_code: str
    entries: List[ScheduleEntry] = field(default_factory=list)
    total_employee_amount: Decimal = Decimal("0")
    total_employer_amount: Decimal = Decimal("0")
    total_remittance: Decimal = Decimal("0")
    generated_at: Optional[date] = None


# ==============================================================================
# Summary Types
# ==============================================================================


@dataclass
class DeductionTotals:
    """Totals for a deduction type across a payroll."""

    deduction_type: DeductionType
    employee_count: int = 0
    total_employee_amount: Decimal = Decimal("0")
    total_employer_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")


@dataclass
class PayrollComplianceSummary:
    """Summary of compliance calculations for a payroll run."""

    payroll_entry_id: int
    period_start: date
    period_end: date
    region_code: str
    total_employees: int
    total_gross_pay: Decimal
    total_taxable_income: Decimal
    total_employee_deductions: Decimal
    total_employer_contributions: Decimal
    total_net_pay: Decimal
    by_deduction_type: Dict[str, DeductionTotals] = field(default_factory=dict)
