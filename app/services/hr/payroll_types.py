"""Type definitions for payroll service.

These dataclasses define the contract for payroll operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from app.models.hr_payroll import SalaryComponentType, SalarySlipStatus

__all__ = [
    # Salary Component
    "SalaryComponentCreateData",
    "SalaryComponentUpdateData",
    # Salary Structure
    "SalaryStructureFilters",
    "SalaryStructureCreateData",
    "SalaryStructureUpdateData",
    "StructureEarningData",
    "StructureDeductionData",
    # Salary Structure Assignment
    "StructureAssignmentFilters",
    "StructureAssignmentCreateData",
    "StructureAssignmentUpdateData",
    # Payroll Entry
    "PayrollEntryFilters",
    "PayrollEntryCreateData",
    "PayrollEntryUpdateData",
    # Salary Slip
    "SalarySlipFilters",
    "SalarySlipCreateData",
    "SalarySlipUpdateData",
    "SlipEarningData",
    "SlipDeductionData",
    "SlipPaymentData",
    # Results
    "SlipGenerationResult",
    "SlipCalculation",
    "ComponentAmount",
    "YTDEarnings",
    "PayrollSummary",
    "BulkSlipResult",
]


# ==============================================================================
# Salary Component
# ==============================================================================


@dataclass
class SalaryComponentCreateData:
    """Data for creating a salary component."""

    salary_component_name: str
    type: SalaryComponentType = SalaryComponentType.EARNING
    salary_component_abbr: Optional[str] = None
    description: Optional[str] = None
    is_tax_applicable: bool = False
    is_payable: bool = True
    is_flexible_benefit: bool = False
    depends_on_payment_days: bool = True
    variable_based_on_taxable_salary: bool = False
    exempted_from_income_tax: bool = False
    statistical_component: bool = False
    do_not_include_in_total: bool = False
    default_account: Optional[str] = None


@dataclass
class SalaryComponentUpdateData:
    """Data for updating a salary component (all fields optional)."""

    salary_component_name: Optional[str] = None
    salary_component_abbr: Optional[str] = None
    type: Optional[SalaryComponentType] = None
    description: Optional[str] = None
    is_tax_applicable: Optional[bool] = None
    is_payable: Optional[bool] = None
    is_flexible_benefit: Optional[bool] = None
    depends_on_payment_days: Optional[bool] = None
    variable_based_on_taxable_salary: Optional[bool] = None
    exempted_from_income_tax: Optional[bool] = None
    statistical_component: Optional[bool] = None
    do_not_include_in_total: Optional[bool] = None
    default_account: Optional[str] = None
    disabled: Optional[bool] = None


# ==============================================================================
# Salary Structure
# ==============================================================================


@dataclass
class StructureEarningData:
    """Earning component in a salary structure."""

    salary_component: str
    abbr: Optional[str] = None
    amount: Decimal = Decimal("0")
    amount_based_on_formula: bool = False
    formula: Optional[str] = None
    condition: Optional[str] = None
    statistical_component: bool = False
    do_not_include_in_total: bool = False
    idx: int = 0


@dataclass
class StructureDeductionData:
    """Deduction component in a salary structure."""

    salary_component: str
    abbr: Optional[str] = None
    amount: Decimal = Decimal("0")
    amount_based_on_formula: bool = False
    formula: Optional[str] = None
    condition: Optional[str] = None
    statistical_component: bool = False
    do_not_include_in_total: bool = False
    idx: int = 0


@dataclass
class SalaryStructureFilters:
    """Filters for listing salary structures."""

    company: Optional[str] = None
    is_active: Optional[bool] = None
    payroll_frequency: Optional[str] = None
    search: Optional[str] = None


@dataclass
class SalaryStructureCreateData:
    """Data for creating a salary structure."""

    salary_structure_name: str
    company: Optional[str] = None
    payroll_frequency: Optional[str] = None
    currency: str = "NGN"
    payment_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    earnings: List[StructureEarningData] = field(default_factory=list)
    deductions: List[StructureDeductionData] = field(default_factory=list)


@dataclass
class SalaryStructureUpdateData:
    """Data for updating a salary structure (all fields optional)."""

    salary_structure_name: Optional[str] = None
    company: Optional[str] = None
    is_active: Optional[bool] = None
    payroll_frequency: Optional[str] = None
    currency: Optional[str] = None
    payment_account: Optional[str] = None
    mode_of_payment: Optional[str] = None
    earnings: Optional[List[StructureEarningData]] = None
    deductions: Optional[List[StructureDeductionData]] = None


# ==============================================================================
# Salary Structure Assignment
# ==============================================================================


@dataclass
class StructureAssignmentFilters:
    """Filters for listing salary structure assignments."""

    employee_id: Optional[int] = None
    salary_structure_id: Optional[int] = None
    from_date: Optional[date] = None
    company: Optional[str] = None


@dataclass
class StructureAssignmentCreateData:
    """Data for creating a salary structure assignment."""

    employee_id: int
    employee: str
    salary_structure_id: int
    salary_structure: str
    from_date: date
    base: Decimal = Decimal("0")
    variable: Decimal = Decimal("0")
    employee_name: Optional[str] = None
    income_tax_slab: Optional[str] = None
    company: Optional[str] = None


@dataclass
class StructureAssignmentUpdateData:
    """Data for updating a salary structure assignment (all fields optional)."""

    salary_structure_id: Optional[int] = None
    salary_structure: Optional[str] = None
    from_date: Optional[date] = None
    base: Optional[Decimal] = None
    variable: Optional[Decimal] = None
    income_tax_slab: Optional[str] = None


# ==============================================================================
# Payroll Entry
# ==============================================================================


@dataclass
class PayrollEntryFilters:
    """Filters for listing payroll entries."""

    company: Optional[str] = None
    department: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    salary_slips_created: Optional[bool] = None
    salary_slips_submitted: Optional[bool] = None


@dataclass
class PayrollEntryCreateData:
    """Data for creating a payroll entry."""

    posting_date: date
    start_date: date
    end_date: date
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: str = "NGN"
    exchange_rate: Decimal = Decimal("1")
    region_code: Optional[str] = None
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None


@dataclass
class PayrollEntryUpdateData:
    """Data for updating a payroll entry (all fields optional)."""

    posting_date: Optional[date] = None
    payroll_frequency: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    designation: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    region_code: Optional[str] = None
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None


# ==============================================================================
# Salary Slip
# ==============================================================================


@dataclass
class SlipEarningData:
    """Earning line item on a salary slip."""

    salary_component: str
    amount: Decimal
    abbr: Optional[str] = None
    default_amount: Decimal = Decimal("0")
    additional_amount: Decimal = Decimal("0")
    year_to_date: Decimal = Decimal("0")
    statistical_component: bool = False
    do_not_include_in_total: bool = False
    idx: int = 0


@dataclass
class SlipDeductionData:
    """Deduction line item on a salary slip."""

    salary_component: str
    amount: Decimal
    abbr: Optional[str] = None
    default_amount: Decimal = Decimal("0")
    additional_amount: Decimal = Decimal("0")
    year_to_date: Decimal = Decimal("0")
    statistical_component: bool = False
    do_not_include_in_total: bool = False
    idx: int = 0


@dataclass
class SalarySlipFilters:
    """Filters for listing salary slips."""

    employee_id: Optional[int] = None
    status: Optional[SalarySlipStatus] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    department: Optional[str] = None
    payroll_entry: Optional[str] = None


@dataclass
class SalarySlipCreateData:
    """Data for creating a salary slip."""

    employee_id: int
    employee: str
    posting_date: date
    start_date: date
    end_date: date
    employee_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    branch: Optional[str] = None
    salary_structure: Optional[str] = None
    payroll_frequency: Optional[str] = None
    company: Optional[str] = None
    currency: str = "NGN"
    region_code: Optional[str] = None
    total_working_days: Decimal = Decimal("0")
    absent_days: Decimal = Decimal("0")
    payment_days: Decimal = Decimal("0")
    leave_without_pay: Decimal = Decimal("0")
    gross_pay: Decimal = Decimal("0")
    total_deduction: Decimal = Decimal("0")
    net_pay: Decimal = Decimal("0")
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    payroll_entry: Optional[str] = None
    earnings: List[SlipEarningData] = field(default_factory=list)
    deductions: List[SlipDeductionData] = field(default_factory=list)


@dataclass
class SalarySlipUpdateData:
    """Data for updating a salary slip (all fields optional)."""

    total_working_days: Optional[Decimal] = None
    absent_days: Optional[Decimal] = None
    payment_days: Optional[Decimal] = None
    leave_without_pay: Optional[Decimal] = None
    gross_pay: Optional[Decimal] = None
    total_deduction: Optional[Decimal] = None
    net_pay: Optional[Decimal] = None
    earnings: Optional[List[SlipEarningData]] = None
    deductions: Optional[List[SlipDeductionData]] = None


@dataclass
class SlipPaymentData:
    """Data for marking a salary slip as paid."""

    payment_reference: Optional[str] = None
    payment_mode: Optional[str] = None
    paid_at: Optional[datetime] = None


# ==============================================================================
# Results
# ==============================================================================


@dataclass
class SlipGenerationResult:
    """Result of generating salary slips from a payroll entry."""

    payroll_entry_id: int
    created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    skipped_employees: List[int] = field(default_factory=list)
    failed_employees: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ComponentAmount:
    """A salary component with its calculated amount."""

    component_name: str
    component_type: SalaryComponentType
    abbr: Optional[str]
    amount: Decimal
    is_tax_applicable: bool = False
    depends_on_payment_days: bool = True


@dataclass
class SlipCalculation:
    """Calculated salary slip components before saving."""

    employee_id: int
    start_date: date
    end_date: date
    total_working_days: Decimal
    payment_days: Decimal
    absent_days: Decimal
    leave_without_pay: Decimal
    earnings: List[ComponentAmount] = field(default_factory=list)
    deductions: List[ComponentAmount] = field(default_factory=list)
    gross_pay: Decimal = Decimal("0")
    total_deduction: Decimal = Decimal("0")
    net_pay: Decimal = Decimal("0")


@dataclass
class YTDEarnings:
    """Year-to-date earnings summary for an employee."""

    employee_id: int
    year: int
    gross_earnings: Decimal = Decimal("0")
    total_deductions: Decimal = Decimal("0")
    net_earnings: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")
    tax_paid: Decimal = Decimal("0")
    component_totals: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class PayrollSummary:
    """Summary of a payroll run."""

    payroll_entry_id: int
    start_date: date
    end_date: date
    total_employees: int
    total_gross_pay: Decimal
    total_deductions: Decimal
    total_net_pay: Decimal
    by_department: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class BulkSlipResult:
    """Result of bulk salary slip operations."""

    submitted_count: int = 0
    paid_count: int = 0
    cancelled_count: int = 0
    failed_ids: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class CreatedSlipDetail:
    """Details of a created salary slip."""

    id: int
    employee: str
    employee_id: int
    gross_pay: Decimal
    net_pay: Decimal
    paye: Decimal = Decimal("0")
    pension: Decimal = Decimal("0")
    is_paye_exempt: bool = False


@dataclass
class SkippedSlipDetail:
    """Details of a skipped salary slip."""

    employee_id: int
    employee: str
    reason: str


@dataclass
class SlipGenerationDetailResult:
    """Detailed result of generating salary slips with Nigerian tax compliance."""

    payroll_entry_id: int
    created_count: int = 0
    skipped_count: int = 0
    created_details: List[CreatedSlipDetail] = field(default_factory=list)
    skipped_details: List[SkippedSlipDetail] = field(default_factory=list)
    deleted_drafts: int = 0  # For regeneration


@dataclass
class PayoutItem:
    """Data for a single payout."""

    salary_slip_id: int
    account_number: str
    bank_code: str
    account_name: Optional[str] = None


@dataclass
class PayoutResult:
    """Result of a payout operation."""

    reference: str
    provider_reference: Optional[str]
    status: str
    amount: Decimal
    salary_slip_id: int
    fee: Optional[Decimal] = None


@dataclass
class PayoutBatchResult:
    """Result of batch payout operations."""

    count: int
    transfers: List[PayoutResult] = field(default_factory=list)
    drafts: List[Dict[str, Any]] = field(default_factory=list)  # For handoff
