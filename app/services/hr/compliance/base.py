"""Base protocol and abstract class for compliance modules.

Compliance modules implement region-specific statutory deduction calculations.
Each region (country/jurisdiction) has its own module that implements the
ComplianceModule protocol.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import List, Optional, Protocol, Set, TYPE_CHECKING

from app.services.hr.compliance.types import (
    ComplianceResult,
    ComplianceSchedule,
    DeductionConfig,
    DeductionResult,
    DeductionType,
    EmployeeInfo,
    SalaryInput,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "ComplianceModule",
    "ComplianceModuleBase",
    "DeductionCalculator",
]


class DeductionCalculator(Protocol):
    """Protocol for individual deduction calculators."""

    deduction_type: DeductionType

    def calculate(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate the deduction for an employee."""
        ...


class ComplianceModule(Protocol):
    """Protocol for region-specific compliance modules.

    Each compliance module provides:
    - Region code (ISO 3166-1 alpha-2)
    - Available deduction types for the region
    - Calculation methods for each deduction type
    - Schedule generation for remittance
    """

    region_code: str
    region_name: str
    currency: str
    available_deductions: List[DeductionType]

    def calculate(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        enabled_deductions: Optional[Set[str]] = None,
        config_overrides: Optional[dict] = None,
    ) -> ComplianceResult:
        """Calculate all enabled deductions for an employee."""
        ...

    def calculate_deduction(
        self,
        deduction_type: DeductionType,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate a specific deduction type."""
        ...

    def generate_schedule(
        self,
        db: "Session",
        deduction_type: DeductionType,
        period_start: date,
        period_end: date,
        company: str,
    ) -> ComplianceSchedule:
        """Generate a remittance schedule for a deduction type."""
        ...

    def get_taxable_income(
        self,
        salary: SalaryInput,
        deductions: dict,
    ) -> Decimal:
        """Calculate taxable income after exemptions and relief."""
        ...


class ComplianceModuleBase(ABC):
    """Abstract base class for compliance modules.

    Provides common functionality and enforces the ComplianceModule protocol.
    Subclasses must implement region-specific calculation logic.
    """

    region_code: str
    region_name: str
    currency: str
    available_deductions: List[DeductionType]

    def __init__(self) -> None:
        self._calculators: dict[DeductionType, DeductionCalculator] = {}

    def register_calculator(
        self, calculator: DeductionCalculator
    ) -> None:
        """Register a deduction calculator."""
        self._calculators[calculator.deduction_type] = calculator

    def get_calculator(
        self, deduction_type: DeductionType
    ) -> Optional[DeductionCalculator]:
        """Get a calculator for a deduction type."""
        return self._calculators.get(deduction_type)

    def calculate(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        enabled_deductions: Optional[Set[str]] = None,
        config_overrides: Optional[dict] = None,
    ) -> ComplianceResult:
        """Calculate all enabled deductions for an employee."""
        # Default to all available deductions if not specified
        if enabled_deductions is None:
            enabled_deductions = {str(d) for d in self.available_deductions}

        result = ComplianceResult(
            employee_id=employee.employee_id,
            period_start=period_start,
            period_end=period_end,
            region_code=self.region_code,
            gross_salary=salary.gross_salary,
            taxable_income=Decimal("0"),
        )

        # Calculate each enabled deduction
        for deduction_name in enabled_deductions:
            try:
                deduction_type = DeductionType(deduction_name)
            except ValueError:
                result.warnings.append(f"Unknown deduction type: {deduction_name}")
                continue

            if deduction_type not in self.available_deductions:
                result.warnings.append(
                    f"Deduction {deduction_name} not available in {self.region_code}"
                )
                continue

            # Get config override if provided
            config = None
            if config_overrides and deduction_name in config_overrides:
                config = config_overrides[deduction_name]

            try:
                deduction_result = self.calculate_deduction(
                    deduction_type, salary, employee, period_start, period_end, config
                )
                result.deductions[deduction_name] = deduction_result
                result.total_employee_deductions += deduction_result.employee_amount
                result.total_employer_contributions += deduction_result.employer_amount
            except Exception as e:
                result.errors.append(f"Error calculating {deduction_name}: {str(e)}")

        # Calculate taxable income
        result.taxable_income = self.get_taxable_income(salary, result.deductions)

        # Calculate net pay
        result.net_pay = salary.gross_salary - result.total_employee_deductions

        return result

    @abstractmethod
    def calculate_deduction(
        self,
        deduction_type: DeductionType,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate a specific deduction type."""
        ...

    @abstractmethod
    def generate_schedule(
        self,
        db: "Session",
        deduction_type: DeductionType,
        period_start: date,
        period_end: date,
        company: str,
    ) -> ComplianceSchedule:
        """Generate a remittance schedule for a deduction type."""
        ...

    @abstractmethod
    def get_taxable_income(
        self,
        salary: SalaryInput,
        deductions: dict,
    ) -> Decimal:
        """Calculate taxable income after exemptions and relief."""
        ...
