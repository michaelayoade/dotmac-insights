"""Nigerian Compliance Module Implementation.

Implements Nigerian statutory deductions:
- PAYE (Pay As You Earn) - Personal Income Tax
- PENSION - Contributory Pension Scheme (8% employee + 10% employer)
- NHF (National Housing Fund) - 2.5% of basic salary
- NHIS (National Health Insurance) - 1.75% employee + 3.25% employer
- NSITF (Nigeria Social Insurance Trust Fund) - 1% employer only
- ITF (Industrial Training Fund) - 1% employer only
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, List, Optional

from app.services.hr.compliance.base import ComplianceModuleBase
from app.services.hr.compliance.ng.paye import PAYECalculator
from app.services.hr.compliance.types import (
    ComplianceSchedule,
    DeductionBreakdown,
    DeductionConfig,
    DeductionResult,
    DeductionType,
    EmployeeInfo,
    SalaryInput,
    ScheduleEntry,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = ["NigerianComplianceModule"]


# Pension rates
PENSION_EMPLOYEE_RATE = Decimal("0.08")  # 8%
PENSION_EMPLOYER_RATE = Decimal("0.10")  # 10%

# NHF rate
NHF_RATE = Decimal("0.025")  # 2.5% of basic

# NHIS rates
NHIS_EMPLOYEE_RATE = Decimal("0.0175")  # 1.75%
NHIS_EMPLOYER_RATE = Decimal("0.0325")  # 3.25%

# NSITF rate (employer only)
NSITF_RATE = Decimal("0.01")  # 1%

# ITF rate (employer only)
ITF_RATE = Decimal("0.01")  # 1%


class NigerianComplianceModule(ComplianceModuleBase):
    """Nigerian statutory compliance module.

    Supports selectable deductions:
    - PAYE: Personal Income Tax
    - PENSION: Contributory Pension (8% employee + 10% employer)
    - NHF: National Housing Fund (2.5% of basic)
    - NHIS: Health Insurance (1.75% employee + 3.25% employer)
    - NSITF: Employee Compensation (1% employer only)
    - ITF: Industrial Training Fund (1% employer only)
    """

    region_code = "NG"
    region_name = "Nigeria"
    currency = "NGN"
    available_deductions = [
        DeductionType.PAYE,
        DeductionType.PENSION,
        DeductionType.NHF,
        DeductionType.NHIS,
        DeductionType.NSITF,
        DeductionType.ITF,
    ]

    def __init__(self) -> None:
        super().__init__()
        self._paye_calculator = PAYECalculator()

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
        if deduction_type == DeductionType.PAYE:
            return self._paye_calculator.calculate(
                salary, employee, period_start, period_end, config
            )
        elif deduction_type == DeductionType.PENSION:
            return self._calculate_pension(salary, employee, config)
        elif deduction_type == DeductionType.NHF:
            return self._calculate_nhf(salary, employee, config)
        elif deduction_type == DeductionType.NHIS:
            return self._calculate_nhis(salary, employee, config)
        elif deduction_type == DeductionType.NSITF:
            return self._calculate_nsitf(salary, employee, config)
        elif deduction_type == DeductionType.ITF:
            return self._calculate_itf(salary, employee, config)
        else:
            return DeductionResult(
                deduction_type=deduction_type,
                notes=[f"Unsupported deduction type: {deduction_type}"],
            )

    def _calculate_pension(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate pension contribution.

        Contributory Pension Scheme:
        - Employee: 8% of (basic + housing + transport)
        - Employer: 10% of (basic + housing + transport)
        """
        breakdown: List[DeductionBreakdown] = []

        # Get rates (allow override)
        employee_rate = (
            config.employee_rate if config and config.employee_rate
            else PENSION_EMPLOYEE_RATE
        )
        employer_rate = (
            config.employer_rate if config and config.employer_rate
            else PENSION_EMPLOYER_RATE
        )

        # Pensionable earnings: basic + housing + transport
        pensionable = (
            salary.basic_salary
            + salary.housing_allowance
            + salary.transport_allowance
        )

        breakdown.append(DeductionBreakdown(
            item="Pensionable Earnings",
            description="Basic + Housing + Transport",
            amount=pensionable,
        ))

        employee_amount = (pensionable * employee_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        employer_amount = (pensionable * employer_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Employee Contribution",
            description=f"{employee_rate * 100:.0f}% of pensionable",
            amount=employee_amount,
            is_taxable=False,
        ))
        breakdown.append(DeductionBreakdown(
            item="Employer Contribution",
            description=f"{employer_rate * 100:.0f}% of pensionable",
            amount=employer_amount,
            is_taxable=False,
        ))

        return DeductionResult(
            deduction_type=DeductionType.PENSION,
            employee_amount=employee_amount,
            employer_amount=employer_amount,
            taxable_amount=Decimal("0"),  # Pension is tax-exempt
            breakdown=breakdown,
            notes=[
                f"Employee rate: {employee_rate * 100:.0f}%",
                f"Employer rate: {employer_rate * 100:.0f}%",
            ],
        )

    def _calculate_nhf(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate National Housing Fund contribution.

        NHF: 2.5% of basic salary (employee only).
        """
        breakdown: List[DeductionBreakdown] = []

        rate = (
            config.employee_rate if config and config.employee_rate
            else NHF_RATE
        )

        nhf_amount = (salary.basic_salary * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Basic Salary",
            description="Base for NHF calculation",
            amount=salary.basic_salary,
        ))
        breakdown.append(DeductionBreakdown(
            item="NHF Contribution",
            description=f"{rate * 100:.1f}% of basic",
            amount=nhf_amount,
            is_taxable=False,
        ))

        return DeductionResult(
            deduction_type=DeductionType.NHF,
            employee_amount=nhf_amount,
            employer_amount=Decimal("0"),  # NHF is employee-only
            taxable_amount=Decimal("0"),  # NHF is tax-exempt
            breakdown=breakdown,
            notes=[f"NHF rate: {rate * 100:.1f}%"],
        )

    def _calculate_nhis(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate National Health Insurance contribution.

        NHIS (formal sector):
        - Employee: 1.75% of basic salary
        - Employer: 3.25% of basic salary
        """
        breakdown: List[DeductionBreakdown] = []

        employee_rate = (
            config.employee_rate if config and config.employee_rate
            else NHIS_EMPLOYEE_RATE
        )
        employer_rate = (
            config.employer_rate if config and config.employer_rate
            else NHIS_EMPLOYER_RATE
        )

        employee_amount = (salary.basic_salary * employee_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        employer_amount = (salary.basic_salary * employer_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Basic Salary",
            description="Base for NHIS calculation",
            amount=salary.basic_salary,
        ))
        breakdown.append(DeductionBreakdown(
            item="Employee Contribution",
            description=f"{employee_rate * 100:.2f}% of basic",
            amount=employee_amount,
        ))
        breakdown.append(DeductionBreakdown(
            item="Employer Contribution",
            description=f"{employer_rate * 100:.2f}% of basic",
            amount=employer_amount,
        ))

        return DeductionResult(
            deduction_type=DeductionType.NHIS,
            employee_amount=employee_amount,
            employer_amount=employer_amount,
            taxable_amount=Decimal("0"),
            breakdown=breakdown,
            notes=[
                f"Employee rate: {employee_rate * 100:.2f}%",
                f"Employer rate: {employer_rate * 100:.2f}%",
            ],
        )

    def _calculate_nsitf(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate NSITF (Employee Compensation) contribution.

        NSITF: 1% of total payroll (employer only).
        """
        breakdown: List[DeductionBreakdown] = []

        rate = (
            config.employer_rate if config and config.employer_rate
            else NSITF_RATE
        )

        employer_amount = (salary.gross_salary * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Gross Salary",
            description="Base for NSITF calculation",
            amount=salary.gross_salary,
        ))
        breakdown.append(DeductionBreakdown(
            item="NSITF Contribution",
            description=f"{rate * 100:.0f}% of gross (employer)",
            amount=employer_amount,
        ))

        return DeductionResult(
            deduction_type=DeductionType.NSITF,
            employee_amount=Decimal("0"),  # NSITF is employer-only
            employer_amount=employer_amount,
            taxable_amount=Decimal("0"),
            breakdown=breakdown,
            notes=[
                "NSITF is employer contribution only",
                f"Rate: {rate * 100:.0f}% of payroll",
            ],
        )

    def _calculate_itf(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate Industrial Training Fund contribution.

        ITF: 1% of total payroll (employer only).
        Applies to employers with 5+ employees or annual turnover > N50 million.
        """
        breakdown: List[DeductionBreakdown] = []

        rate = (
            config.employer_rate if config and config.employer_rate
            else ITF_RATE
        )

        employer_amount = (salary.gross_salary * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Gross Salary",
            description="Base for ITF calculation",
            amount=salary.gross_salary,
        ))
        breakdown.append(DeductionBreakdown(
            item="ITF Contribution",
            description=f"{rate * 100:.0f}% of gross (employer)",
            amount=employer_amount,
        ))

        return DeductionResult(
            deduction_type=DeductionType.ITF,
            employee_amount=Decimal("0"),  # ITF is employer-only
            employer_amount=employer_amount,
            taxable_amount=Decimal("0"),
            breakdown=breakdown,
            notes=[
                "ITF is employer contribution only",
                f"Rate: {rate * 100:.0f}% of payroll",
            ],
        )

    def generate_schedule(
        self,
        db: "Session",
        deduction_type: DeductionType,
        period_start: date,
        period_end: date,
        company: str,
    ) -> ComplianceSchedule:
        """Generate a remittance schedule for a deduction type."""
        from sqlalchemy import and_, select
        from app.models.hr_payroll import SalarySlip, SalarySlipStatus

        schedule = ComplianceSchedule(
            deduction_type=deduction_type,
            period_start=period_start,
            period_end=period_end,
            company=company,
            region_code=self.region_code,
            generated_at=date.today(),
        )

        # Get all submitted/paid salary slips for the period
        slips = db.scalars(
            select(SalarySlip).where(
                and_(
                    SalarySlip.company == company,
                    SalarySlip.start_date >= period_start,
                    SalarySlip.end_date <= period_end,
                    SalarySlip.status.in_([
                        SalarySlipStatus.SUBMITTED,
                        SalarySlipStatus.PAID,
                    ]),
                )
            )
        ).all()

        deduction_name = str(deduction_type)

        for slip in slips:
            # Find the deduction in the slip
            deduction_amount = Decimal("0")
            for deduction in slip.deductions:
                if deduction.salary_component == deduction_name:
                    deduction_amount = deduction.amount
                    break

            if deduction_amount > Decimal("0") or deduction_type in [
                DeductionType.NSITF, DeductionType.ITF
            ]:
                # For employer-only deductions, calculate on the fly
                if deduction_type in [DeductionType.NSITF, DeductionType.ITF]:
                    employer_amount = (slip.gross_pay * Decimal("0.01")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    employee_amount = Decimal("0")
                elif deduction_type == DeductionType.PENSION:
                    # Split pension (8% employee, 10% employer)
                    pensionable = slip.gross_pay * Decimal("0.6")  # Estimate
                    employee_amount = deduction_amount
                    employer_amount = (pensionable * PENSION_EMPLOYER_RATE).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                elif deduction_type == DeductionType.NHIS:
                    employee_amount = deduction_amount
                    employer_amount = (
                        deduction_amount * NHIS_EMPLOYER_RATE / NHIS_EMPLOYEE_RATE
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    employee_amount = deduction_amount
                    employer_amount = Decimal("0")

                total = employee_amount + employer_amount

                # Get registration number based on deduction type
                reg_number = None
                # Would look up from employee record in production

                entry = ScheduleEntry(
                    employee_id=slip.employee_id or 0,
                    employee_name=slip.employee_name or slip.employee,
                    employee_number=slip.employee,
                    registration_number=reg_number,
                    gross_salary=slip.gross_pay,
                    employee_amount=employee_amount,
                    employer_amount=employer_amount,
                    total_amount=total,
                )
                schedule.entries.append(entry)
                schedule.total_employee_amount += employee_amount
                schedule.total_employer_amount += employer_amount
                schedule.total_remittance += total

        return schedule

    def get_taxable_income(
        self,
        salary: SalaryInput,
        deductions: dict,
    ) -> Decimal:
        """Calculate taxable income after exemptions.

        Taxable income = Gross - CRA - Pension - NHF
        """
        annual_gross = salary.gross_salary * 12

        # Calculate CRA
        cra_option_1 = annual_gross * Decimal("0.20")
        cra_option_2 = Decimal("200000") + (annual_gross * Decimal("0.01"))
        cra = max(cra_option_1, cra_option_2)

        # Get pension contribution (tax-exempt)
        pension = Decimal("0")
        if "PENSION" in deductions:
            pension = deductions["PENSION"].employee_amount * 12

        # Get NHF contribution (tax-exempt)
        nhf = Decimal("0")
        if "NHF" in deductions:
            nhf = deductions["NHF"].employee_amount * 12

        taxable = annual_gross - cra - pension - nhf
        return max(taxable, Decimal("0"))
