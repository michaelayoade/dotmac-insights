"""Nigerian PAYE (Pay As You Earn) Tax Calculator.

Implements the Nigerian Personal Income Tax calculation based on:
- Personal Income Tax Act (PITA) 2011
- Finance Act 2020 amendments

Tax rates (annual):
- First N300,000: 7%
- Next N300,000: 11%
- Next N500,000: 15%
- Next N500,000: 19%
- Next N1,600,000: 21%
- Above N3,200,000: 24%

Consolidated Relief Allowance (CRA):
- 20% of gross income, OR
- N200,000 + 1% of gross income (whichever is higher)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

from app.services.hr.compliance.types import (
    DeductionBreakdown,
    DeductionConfig,
    DeductionResult,
    DeductionType,
    EmployeeInfo,
    SalaryInput,
)

__all__ = ["PAYECalculator"]


# Tax bands (annual amounts in Naira)
TAX_BANDS: List[Tuple[Decimal, Decimal]] = [
    (Decimal("300000"), Decimal("0.07")),    # First 300,000 at 7%
    (Decimal("300000"), Decimal("0.11")),    # Next 300,000 at 11%
    (Decimal("500000"), Decimal("0.15")),    # Next 500,000 at 15%
    (Decimal("500000"), Decimal("0.19")),    # Next 500,000 at 19%
    (Decimal("1600000"), Decimal("0.21")),   # Next 1,600,000 at 21%
    (Decimal("0"), Decimal("0.24")),         # Above 3,200,000 at 24% (unlimited)
]

# Minimum taxable income (below this, tax is 1% of gross)
MINIMUM_TAX_THRESHOLD = Decimal("300000")  # Annual

# Minimum tax rate for low income
MINIMUM_TAX_RATE = Decimal("0.01")


class PAYECalculator:
    """Calculator for Nigerian PAYE (Personal Income Tax)."""

    deduction_type = DeductionType.PAYE

    def calculate(
        self,
        salary: SalaryInput,
        employee: EmployeeInfo,
        period_start: date,
        period_end: date,
        config: Optional[DeductionConfig] = None,
    ) -> DeductionResult:
        """Calculate PAYE tax for the period.

        Args:
            salary: Salary components for the period.
            employee: Employee information.
            period_start: Start of payroll period.
            period_end: End of payroll period.
            config: Optional configuration overrides.

        Returns:
            DeductionResult with calculated tax.
        """
        breakdown: List[DeductionBreakdown] = []

        # Calculate number of months in period (for annualization)
        months_in_period = self._get_months_in_period(period_start, period_end)

        # Step 1: Calculate annual gross income
        monthly_gross = salary.gross_salary
        annual_gross = monthly_gross * 12

        breakdown.append(DeductionBreakdown(
            item="Monthly Gross",
            description="Total monthly earnings",
            amount=monthly_gross,
        ))
        breakdown.append(DeductionBreakdown(
            item="Annualized Gross",
            description="Gross income projected annually",
            amount=annual_gross,
        ))

        # Step 2: Calculate Consolidated Relief Allowance (CRA)
        cra = self._calculate_cra(annual_gross)
        breakdown.append(DeductionBreakdown(
            item="Consolidated Relief Allowance",
            description="CRA (higher of 20% or N200,000 + 1%)",
            amount=cra,
            is_taxable=False,
        ))

        # Step 3: Calculate pension contribution (if applicable)
        # Pension is tax-exempt, so we deduct it from taxable income
        pension_contribution = self._get_pension_contribution(salary)
        annual_pension = pension_contribution * 12
        if annual_pension > Decimal("0"):
            breakdown.append(DeductionBreakdown(
                item="Pension Contribution",
                description="Employee pension (8% of basic + housing + transport)",
                amount=annual_pension,
                is_taxable=False,
            ))

        # Step 4: Calculate NHF contribution (tax-exempt)
        nhf_contribution = self._get_nhf_contribution(salary)
        annual_nhf = nhf_contribution * 12
        if annual_nhf > Decimal("0"):
            breakdown.append(DeductionBreakdown(
                item="NHF Contribution",
                description="National Housing Fund (2.5% of basic)",
                amount=annual_nhf,
                is_taxable=False,
            ))

        # Step 5: Calculate taxable income
        annual_taxable = annual_gross - cra - annual_pension - annual_nhf
        annual_taxable = max(annual_taxable, Decimal("0"))

        breakdown.append(DeductionBreakdown(
            item="Annual Taxable Income",
            description="Gross less CRA and exempt contributions",
            amount=annual_taxable,
        ))

        # Step 6: Apply tax bands
        annual_tax = self._calculate_tax_on_income(annual_taxable, breakdown)

        # Step 7: Check minimum tax rule
        # If taxable income < N300,000, minimum tax is 1% of gross
        minimum_tax = annual_gross * MINIMUM_TAX_RATE
        if annual_taxable < MINIMUM_TAX_THRESHOLD and minimum_tax > annual_tax:
            annual_tax = minimum_tax
            breakdown.append(DeductionBreakdown(
                item="Minimum Tax Applied",
                description="1% of gross (low income rule)",
                amount=minimum_tax,
            ))

        # Step 8: Convert to monthly
        monthly_tax = (annual_tax / 12).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Apply period adjustment
        period_tax = (monthly_tax * months_in_period).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        breakdown.append(DeductionBreakdown(
            item="Annual Tax",
            description="Total annual PAYE",
            amount=annual_tax,
        ))
        breakdown.append(DeductionBreakdown(
            item="Period Tax",
            description=f"Tax for {months_in_period} month(s)",
            amount=period_tax,
        ))

        return DeductionResult(
            deduction_type=DeductionType.PAYE,
            employee_amount=period_tax,
            employer_amount=Decimal("0"),  # PAYE is employee-only
            taxable_amount=Decimal("0"),  # Tax itself is not taxable
            breakdown=breakdown,
            notes=[
                f"Tax calculated using {len(TAX_BANDS)} tax bands",
                f"CRA applied: {cra:,.2f}",
            ],
        )

    def _get_months_in_period(self, start: date, end: date) -> Decimal:
        """Calculate number of months in the period."""
        # Simple month calculation
        months = ((end.year - start.year) * 12 + end.month - start.month) + 1
        return Decimal(str(months))

    def _calculate_cra(self, annual_gross: Decimal) -> Decimal:
        """Calculate Consolidated Relief Allowance.

        CRA is the higher of:
        - 20% of gross income, OR
        - N200,000 + 1% of gross income
        """
        option_1 = annual_gross * Decimal("0.20")
        option_2 = Decimal("200000") + (annual_gross * Decimal("0.01"))
        return max(option_1, option_2)

    def _get_pension_contribution(self, salary: SalaryInput) -> Decimal:
        """Get employee pension contribution (for tax calculation only).

        Pension is calculated on basic + housing + transport.
        Employee rate: 8%
        """
        pensionable = (
            salary.basic_salary
            + salary.housing_allowance
            + salary.transport_allowance
        )
        return (pensionable * Decimal("0.08")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def _get_nhf_contribution(self, salary: SalaryInput) -> Decimal:
        """Get NHF contribution (for tax calculation only).

        NHF is 2.5% of basic salary.
        """
        return (salary.basic_salary * Decimal("0.025")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def _calculate_tax_on_income(
        self,
        taxable_income: Decimal,
        breakdown: List[DeductionBreakdown],
    ) -> Decimal:
        """Apply tax bands to calculate total tax."""
        remaining = taxable_income
        total_tax = Decimal("0")
        cumulative = Decimal("0")

        for band_amount, rate in TAX_BANDS:
            if remaining <= 0:
                break

            if band_amount == Decimal("0"):
                # Unlimited band (highest rate)
                tax_in_band = remaining * rate
                breakdown.append(DeductionBreakdown(
                    item=f"Tax at {rate * 100:.0f}%",
                    description=f"Above {cumulative:,.0f} at {rate * 100:.0f}%",
                    amount=tax_in_band,
                ))
                total_tax += tax_in_band
                remaining = Decimal("0")
            else:
                taxable_in_band = min(remaining, band_amount)
                tax_in_band = taxable_in_band * rate
                if taxable_in_band > 0:
                    breakdown.append(DeductionBreakdown(
                        item=f"Tax at {rate * 100:.0f}%",
                        description=f"{taxable_in_band:,.0f} at {rate * 100:.0f}%",
                        amount=tax_in_band,
                    ))
                total_tax += tax_in_band
                remaining -= taxable_in_band
                cumulative += band_amount

        return total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
