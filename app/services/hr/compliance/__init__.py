"""Statutory Compliance Service.

This module provides a registry-based compliance service that supports
pluggable region-specific compliance modules.

Usage:
    from app.services.hr.compliance import ComplianceService
    from app.services.hr.compliance.ng import NigerianComplianceModule

    # Register modules
    ComplianceService.register_module(NigerianComplianceModule())

    # Use the service
    service = ComplianceService(db)
    result = service.calculate_deductions(
        employee_id=1,
        salary=SalaryInput(basic_salary=Decimal("100000")),
        region_code="NG",
        enabled_deductions={"PAYE", "PENSION", "NHF"}
    )
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.hr_payroll import SalarySlip, SalarySlipStatus
from app.services.hr.compliance.base import ComplianceModule, ComplianceModuleBase
from app.services.hr.compliance.types import (
    ComplianceResult,
    ComplianceSchedule,
    DeductionConfig,
    DeductionTotals,
    DeductionType,
    EmployeeDeductionConfig,
    EmployeeInfo,
    PayrollComplianceSummary,
    SalaryInput,
)

if TYPE_CHECKING:
    from app.web.context import Principal

__all__ = [
    "ComplianceService",
    # Base classes
    "ComplianceModule",
    "ComplianceModuleBase",
    # Types
    "ComplianceResult",
    "ComplianceSchedule",
    "DeductionConfig",
    "DeductionResult",
    "DeductionTotals",
    "DeductionType",
    "EmployeeDeductionConfig",
    "EmployeeInfo",
    "PayrollComplianceSummary",
    "SalaryInput",
]

# Re-export from types for convenience
from app.services.hr.compliance.types import DeductionResult


class ComplianceService:
    """Service for statutory compliance calculations.

    This service acts as a registry and facade for region-specific
    compliance modules. It provides a unified interface for calculating
    deductions and generating remittance schedules.
    """

    # Class-level module registry
    _modules: Dict[str, ComplianceModule] = {}

    def __init__(
        self, db: Session, principal: Optional["Principal"] = None
    ) -> None:
        self.db = db
        self.principal = principal

    @classmethod
    def register_module(cls, module: ComplianceModule) -> None:
        """Register a compliance module for a region.

        Args:
            module: The compliance module to register.
        """
        cls._modules[module.region_code] = module

    @classmethod
    def get_module(cls, region_code: str) -> Optional[ComplianceModule]:
        """Get a registered compliance module.

        Args:
            region_code: ISO 3166-1 alpha-2 country code.

        Returns:
            The compliance module for the region, or None if not registered.
        """
        return cls._modules.get(region_code)

    @classmethod
    def list_regions(cls) -> List[str]:
        """List all registered region codes."""
        return list(cls._modules.keys())

    @classmethod
    def get_available_deductions(cls, region_code: str) -> List[DeductionType]:
        """Get available deduction types for a region."""
        module = cls.get_module(region_code)
        if module:
            return module.available_deductions
        return []

    def calculate_deductions(
        self,
        employee_id: int,
        salary: SalaryInput,
        region_code: str,
        period_start: date,
        period_end: date,
        enabled_deductions: Optional[Set[str]] = None,
        config_overrides: Optional[Dict[str, DeductionConfig]] = None,
    ) -> ComplianceResult:
        """Calculate statutory deductions for an employee.

        Args:
            employee_id: The employee ID.
            salary: Salary components for calculation.
            region_code: ISO 3166-1 alpha-2 country code.
            period_start: Start of the payroll period.
            period_end: End of the payroll period.
            enabled_deductions: Set of deduction types to calculate.
                If None, calculates all available deductions.
            config_overrides: Optional configuration overrides per deduction type.

        Returns:
            ComplianceResult with all calculated deductions.

        Raises:
            ValueError: If the region code is not registered.
        """
        module = self.get_module(region_code)
        if not module:
            raise ValueError(f"No compliance module registered for region: {region_code}")

        # Get employee info
        employee = self.db.get(Employee, employee_id)
        if not employee:
            result = ComplianceResult(
                employee_id=employee_id,
                period_start=period_start,
                period_end=period_end,
                region_code=region_code,
                gross_salary=salary.gross_salary,
                taxable_income=Decimal("0"),
            )
            result.errors.append(f"Employee not found: {employee_id}")
            return result

        employee_info = EmployeeInfo(
            employee_id=employee_id,
            employment_type=employee.employment_type or "permanent",
        )

        return module.calculate(
            salary=salary,
            employee=employee_info,
            period_start=period_start,
            period_end=period_end,
            enabled_deductions=enabled_deductions,
            config_overrides=config_overrides,
        )

    def generate_schedule(
        self,
        region_code: str,
        deduction_type: DeductionType,
        period_start: date,
        period_end: date,
        company: str,
    ) -> ComplianceSchedule:
        """Generate a remittance schedule for a deduction type.

        Args:
            region_code: ISO 3166-1 alpha-2 country code.
            deduction_type: The type of deduction to generate schedule for.
            period_start: Start of the payroll period.
            period_end: End of the payroll period.
            company: Company name/code to filter employees.

        Returns:
            ComplianceSchedule with all entries for remittance.

        Raises:
            ValueError: If the region code is not registered.
        """
        module = self.get_module(region_code)
        if not module:
            raise ValueError(f"No compliance module registered for region: {region_code}")

        return module.generate_schedule(
            db=self.db,
            deduction_type=deduction_type,
            period_start=period_start,
            period_end=period_end,
            company=company,
        )

    def get_payroll_compliance_summary(
        self,
        payroll_entry_id: int,
        region_code: str,
    ) -> PayrollComplianceSummary:
        """Get compliance summary for a payroll run.

        Aggregates compliance data from all salary slips in a payroll entry.

        Args:
            payroll_entry_id: The payroll entry ID.
            region_code: ISO 3166-1 alpha-2 country code.

        Returns:
            PayrollComplianceSummary with totals by deduction type.
        """
        # Get all salary slips for this payroll entry
        slips = self.db.scalars(
            select(SalarySlip).where(
                SalarySlip.payroll_entry == str(payroll_entry_id),
                SalarySlip.status.in_([
                    SalarySlipStatus.SUBMITTED,
                    SalarySlipStatus.PAID,
                ]),
            )
        ).all()

        # Initialize summary
        summary = PayrollComplianceSummary(
            payroll_entry_id=payroll_entry_id,
            period_start=slips[0].start_date if slips else date.today(),
            period_end=slips[0].end_date if slips else date.today(),
            region_code=region_code,
            total_employees=len(slips),
            total_gross_pay=Decimal("0"),
            total_taxable_income=Decimal("0"),
            total_employee_deductions=Decimal("0"),
            total_employer_contributions=Decimal("0"),
            total_net_pay=Decimal("0"),
        )

        # Aggregate deduction totals from slip deductions
        deduction_names = set()
        for slip in slips:
            summary.total_gross_pay += slip.gross_pay
            summary.total_employee_deductions += slip.total_deduction
            summary.total_net_pay += slip.net_pay

            for deduction in slip.deductions:
                deduction_names.add(deduction.salary_component)

        # Create deduction totals
        for deduction_name in deduction_names:
            try:
                deduction_type = DeductionType(deduction_name)
            except ValueError:
                continue

            totals = DeductionTotals(deduction_type=deduction_type)
            for slip in slips:
                for deduction in slip.deductions:
                    if deduction.salary_component == deduction_name:
                        totals.employee_count += 1
                        totals.total_employee_amount += deduction.amount
                        totals.total_amount += deduction.amount

            summary.by_deduction_type[deduction_name] = totals

        # Calculate taxable income (gross - non-taxable allowances)
        summary.total_taxable_income = summary.total_gross_pay

        return summary

    def recalculate_slip_deductions(
        self,
        slip_id: int,
        region_code: str,
        enabled_deductions: Optional[Set[str]] = None,
    ) -> ComplianceResult:
        """Recalculate deductions for a specific salary slip.

        This is useful for updating deductions when tax rules change
        or when employee information is updated.

        Args:
            slip_id: The salary slip ID.
            region_code: ISO 3166-1 alpha-2 country code.
            enabled_deductions: Set of deduction types to calculate.

        Returns:
            ComplianceResult with recalculated deductions.
        """
        slip = self.db.get(SalarySlip, slip_id)
        if not slip:
            result = ComplianceResult(
                employee_id=0,
                period_start=date.today(),
                period_end=date.today(),
                region_code=region_code,
                gross_salary=Decimal("0"),
                taxable_income=Decimal("0"),
            )
            result.errors.append(f"Salary slip not found: {slip_id}")
            return result

        # Build salary input from slip
        salary = SalaryInput()
        for earning in slip.earnings:
            # Map common earning components
            if "basic" in earning.salary_component.lower():
                salary.basic_salary = earning.amount
            elif "housing" in earning.salary_component.lower():
                salary.housing_allowance = earning.amount
            elif "transport" in earning.salary_component.lower():
                salary.transport_allowance = earning.amount
            else:
                salary.other_allowances += earning.amount

        return self.calculate_deductions(
            employee_id=slip.employee_id or 0,
            salary=salary,
            region_code=region_code,
            period_start=slip.start_date,
            period_end=slip.end_date,
            enabled_deductions=enabled_deductions,
        )


# Auto-register Nigerian compliance module on import
def _auto_register_modules() -> None:
    """Auto-register available compliance modules."""
    try:
        from app.services.hr.compliance.ng import NigerianComplianceModule
        ComplianceService.register_module(NigerianComplianceModule())
    except ImportError:
        pass  # Module not available


_auto_register_modules()
