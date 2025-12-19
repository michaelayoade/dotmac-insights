"""
Generic Payroll Calculation Engine

Provides country-agnostic payroll calculations using configurable rules.
Supports three calculation methods:
- FLAT: Fixed deduction amount
- PERCENTAGE: Percentage of specified base components
- PROGRESSIVE: Progressive tax bands

Usage:
    from app.services.payroll_engine import DeductionCalculator, PayrollBuilder

    # Calculate a single deduction
    calculator = DeductionCalculator(db, region_code="NG")
    result = calculator.calculate(
        rule_code="PENSION_EE",
        salary_components={"basic_salary": Decimal("500000"), "housing": Decimal("100000")},
        employment_type="PERMANENT",
        months_of_service=12,
    )

    # Build complete slip deductions
    builder = PayrollBuilder(db, region_code="NG")
    deductions = builder.calculate_deductions(
        salary_components={"basic_salary": Decimal("500000"), ...},
        employment_type="PERMANENT",
        months_of_service=12,
        calc_date=date.today(),
    )
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    RuleApplicability,
)
from app.config import settings

if TYPE_CHECKING:
    from app.models.employee import Employee

logger = logging.getLogger(__name__)


# ============= DATA CLASSES =============


@dataclass
class DeductionResult:
    """Result of a single deduction calculation."""
    rule_code: str
    rule_name: str
    deduction_type: str
    applicability: str  # employee, employer, both
    amount: Decimal
    is_applicable: bool = True
    skip_reason: Optional[str] = None
    calc_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PayrollDeductionsResult:
    """Complete set of deductions for a payroll slip."""
    region_code: str
    gross_pay: Decimal
    employee_deductions: List[DeductionResult]
    employer_contributions: List[DeductionResult]
    total_employee_deductions: Decimal
    total_employer_contributions: Decimal
    net_pay: Decimal
    calc_date: date


# ============= DEDUCTION CALCULATOR =============


class DeductionCalculator:
    """
    Calculate individual deductions based on configured rules.

    Supports caching of rules and tax bands for performance.
    """

    def __init__(self, db: Session, region_code: str, cache_ttl_seconds: int = 300):
        self.db = db
        self.region_code = region_code
        self._cache_ttl_seconds = cache_ttl_seconds
        self._rules_cache: Dict[str, tuple[DeductionRule, float]] = {}
        self._bands_cache: Dict[int, tuple[List[TaxBand], float]] = {}
        self._region: Optional[tuple[PayrollRegion, float]] = None

    def _cache_valid(self, cached_at: float) -> bool:
        if self._cache_ttl_seconds <= 0:
            return False
        return (time.monotonic() - cached_at) <= self._cache_ttl_seconds

    def get_region(self) -> Optional[PayrollRegion]:
        """Get the PayrollRegion for this calculator."""
        if self._region is not None and self._cache_valid(self._region[1]):
            return self._region[0]

        region = self.db.query(PayrollRegion).filter(
            PayrollRegion.code == self.region_code,
            PayrollRegion.is_active == True,
        ).first()
        if region:
            self._region = (region, time.monotonic())
        return region

    def get_rule(self, rule_code: str, calc_date: Optional[date] = None) -> Optional[DeductionRule]:
        """Get a deduction rule by code, respecting effective dates."""
        if calc_date is None:
            calc_date = date.today()

        cache_key = f"{rule_code}:{calc_date}"
        if cache_key in self._rules_cache:
            cached_rule, cached_at = self._rules_cache[cache_key]
            if self._cache_valid(cached_at):
                return cached_rule
            self._rules_cache.pop(cache_key, None)

        region = self.get_region()
        if not region:
            return None

        rule = self.db.query(DeductionRule).filter(
            DeductionRule.region_id == region.id,
            DeductionRule.code == rule_code,
            DeductionRule.is_active == True,
            DeductionRule.effective_from <= calc_date,
            or_(
                DeductionRule.effective_to.is_(None),
                DeductionRule.effective_to >= calc_date,
            ),
        ).first()

        if rule:
            self._rules_cache[cache_key] = (rule, time.monotonic())
        return rule

    def get_active_rules(self, calc_date: Optional[date] = None) -> List[DeductionRule]:
        """Get all active deduction rules for the region."""
        if calc_date is None:
            calc_date = date.today()

        region = self.get_region()
        if not region:
            return []

        return self.db.query(DeductionRule).filter(
            DeductionRule.region_id == region.id,
            DeductionRule.is_active == True,
            DeductionRule.effective_from <= calc_date,
            or_(
                DeductionRule.effective_to.is_(None),
                DeductionRule.effective_to >= calc_date,
            ),
        ).order_by(DeductionRule.display_order).all()

    def get_tax_bands(self, rule_id: int) -> List[TaxBand]:
        """Get tax bands for a progressive rule."""
        if rule_id in self._bands_cache:
            cached_bands, cached_at = self._bands_cache[rule_id]
            if self._cache_valid(cached_at):
                return cached_bands
            self._bands_cache.pop(rule_id, None)

        bands = self.db.query(TaxBand).filter(
            TaxBand.deduction_rule_id == rule_id,
        ).order_by(TaxBand.band_order).all()

        self._bands_cache[rule_id] = (bands, time.monotonic())
        return bands

    def is_applicable(
        self,
        rule: DeductionRule,
        employment_type: Optional[str] = None,
        months_of_service: int = 0,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a rule applies to the given employee context.

        Returns (is_applicable, skip_reason)
        """
        # Check employment type filter
        if rule.employment_types and employment_type:
            emp_type_upper = employment_type.upper().replace("-", "_").replace(" ", "_")
            allowed_types = [t.upper() for t in rule.employment_types]
            if emp_type_upper not in allowed_types:
                return False, f"Employment type {employment_type} not in allowed types"

        # Check minimum service requirement
        if rule.min_service_months > 0 and months_of_service < rule.min_service_months:
            return False, f"Requires {rule.min_service_months} months service, has {months_of_service}"

        return True, None

    def calculate_base(
        self,
        rule: DeductionRule,
        salary_components: Dict[str, Decimal],
    ) -> Decimal:
        """Calculate the base amount for a percentage calculation."""
        if not rule.base_components:
            # Default to sum of all components
            return sum(salary_components.values())

        base = Decimal("0")
        base_patterns = [c.lower() for c in rule.base_components]

        for comp_name, amount in salary_components.items():
            comp_lower = comp_name.lower()
            for pattern in base_patterns:
                if pattern in comp_lower or comp_lower in pattern:
                    base += amount
                    break

        return base

    def calculate_flat(self, rule: DeductionRule, base: Decimal) -> Decimal:
        """Calculate flat amount deduction."""
        amount = rule.flat_amount or Decimal("0")

        # Apply floor
        if rule.floor_amount is not None:
            amount = max(amount, rule.floor_amount)

        # Apply cap
        if rule.cap_amount is not None:
            amount = min(amount, rule.cap_amount)

        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_percentage(
        self,
        rule: DeductionRule,
        salary_components: Dict[str, Decimal],
    ) -> Decimal:
        """Calculate percentage-based deduction."""
        base = self.calculate_base(rule, salary_components)

        # Apply min/max base thresholds
        if rule.min_base is not None:
            base = max(base, rule.min_base)
        if rule.max_base is not None:
            base = min(base, rule.max_base)

        rate = rule.rate or Decimal("0")
        amount = base * rate

        # Apply floor
        if rule.floor_amount is not None:
            amount = max(amount, rule.floor_amount)

        # Apply cap
        if rule.cap_amount is not None:
            amount = min(amount, rule.cap_amount)

        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_progressive(
        self,
        rule: DeductionRule,
        taxable_income: Decimal,
        annualize: bool = True,
    ) -> Decimal:
        """
        Calculate progressive tax using tax bands.

        Args:
            rule: The deduction rule with PROGRESSIVE calc_method
            taxable_income: Monthly taxable income
            annualize: If True, annualize income, calculate, then divide by 12
        """
        bands = self.get_tax_bands(rule.id)
        if not bands:
            logger.warning(f"No tax bands found for rule {rule.code}")
            return Decimal("0")

        # Annualize if needed
        annual_income = taxable_income * 12 if annualize else taxable_income

        # Apply min/max base thresholds
        if rule.min_base is not None:
            annual_income = max(annual_income, rule.min_base)
        if rule.max_base is not None:
            annual_income = min(annual_income, rule.max_base)

        # Calculate progressive tax
        total_tax = Decimal("0")
        remaining_income = annual_income

        for band in bands:
            if remaining_income <= 0:
                break

            if band.lower_limit is not None and annual_income <= band.lower_limit:
                continue

            upper_limit = band.upper_limit if band.upper_limit is not None else annual_income
            taxable_in_band = min(annual_income, upper_limit) - band.lower_limit
            if taxable_in_band <= 0:
                continue

            tax_in_band = taxable_in_band * band.rate
            total_tax += tax_in_band
            remaining_income -= taxable_in_band

        # Convert back to monthly if annualized
        if annualize:
            total_tax = total_tax / 12

        # Apply floor
        if rule.floor_amount is not None:
            total_tax = max(total_tax, rule.floor_amount)

        # Apply cap
        if rule.cap_amount is not None:
            total_tax = min(total_tax, rule.cap_amount)

        return total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate(
        self,
        rule_code: str,
        salary_components: Dict[str, Decimal],
        employment_type: Optional[str] = None,
        months_of_service: int = 0,
        calc_date: Optional[date] = None,
    ) -> DeductionResult:
        """
        Calculate a single deduction by rule code.

        Args:
            rule_code: The deduction rule code (e.g., "PAYE", "PENSION_EE")
            salary_components: Dict of component name -> amount
            employment_type: Optional employment type for eligibility check
            months_of_service: Optional months of service for eligibility
            calc_date: Date for rule lookup and calculation

        Returns:
            DeductionResult with amount and metadata
        """
        rule = self.get_rule(rule_code, calc_date)
        if not rule:
            return DeductionResult(
                rule_code=rule_code,
                rule_name=rule_code,
                deduction_type="unknown",
                applicability="unknown",
                amount=Decimal("0"),
                is_applicable=False,
                skip_reason=f"Rule {rule_code} not found for region {self.region_code}",
            )

        # Check applicability
        is_applicable, skip_reason = self.is_applicable(
            rule, employment_type, months_of_service
        )

        if not is_applicable:
            return DeductionResult(
                rule_code=rule.code,
                rule_name=rule.name,
                deduction_type=rule.deduction_type.value,
                applicability=rule.applicability.value,
                amount=Decimal("0"),
                is_applicable=False,
                skip_reason=skip_reason,
            )

        # Calculate based on method
        if rule.calc_method == CalcMethod.FLAT:
            amount = self.calculate_flat(rule, sum(salary_components.values()))
            calc_details = {"method": "flat", "flat_amount": str(rule.flat_amount)}

        elif rule.calc_method == CalcMethod.PERCENTAGE:
            amount = self.calculate_percentage(rule, salary_components)
            base = self.calculate_base(rule, salary_components)
            calc_details = {
                "method": "percentage",
                "rate": str(rule.rate),
                "base": str(base),
            }

        elif rule.calc_method == CalcMethod.PROGRESSIVE:
            base = self.calculate_base(rule, salary_components)
            amount = self.calculate_progressive(rule, base)
            calc_details = {
                "method": "progressive",
                "base": str(base),
                "annualized": True,
            }
        else:
            amount = Decimal("0")
            calc_details = {"method": "unknown"}

        return DeductionResult(
            rule_code=rule.code,
            rule_name=rule.name,
            deduction_type=rule.deduction_type.value,
            applicability=rule.applicability.value,
            amount=amount,
            is_applicable=True,
            calc_details=calc_details,
        )


# ============= PAYROLL BUILDER =============


class PayrollBuilder:
    """
    Orchestrate complete payroll slip deduction calculation.

    Loads all applicable rules for a region and calculates deductions.
    """

    def __init__(self, db: Session, region_code: str, cache_ttl_seconds: int = 300):
        self.db = db
        self.region_code = region_code
        self.calculator = DeductionCalculator(db, region_code, cache_ttl_seconds=cache_ttl_seconds)

    def calculate_deductions(
        self,
        salary_components: Dict[str, Decimal],
        employment_type: Optional[str] = None,
        months_of_service: int = 0,
        calc_date: Optional[date] = None,
        only_statutory: bool = False,
    ) -> PayrollDeductionsResult:
        """
        Calculate all applicable deductions for a payroll slip.

        Args:
            salary_components: Dict of component name -> amount
            employment_type: Employee's employment type
            months_of_service: Employee's months of service
            calc_date: Calculation date (defaults to today)
            only_statutory: If True, only calculate statutory deductions

        Returns:
            PayrollDeductionsResult with all calculated deductions
        """
        if calc_date is None:
            calc_date = date.today()

        gross_pay = sum(salary_components.values())
        employee_deductions: List[DeductionResult] = []
        employer_contributions: List[DeductionResult] = []

        # Get all applicable rules
        rules = self.calculator.get_active_rules(calc_date)

        for rule in rules:
            # Skip non-statutory if only_statutory
            if only_statutory and not rule.is_statutory:
                continue

            result = self.calculator.calculate(
                rule_code=rule.code,
                salary_components=salary_components,
                employment_type=employment_type,
                months_of_service=months_of_service,
                calc_date=calc_date,
            )

            if not result.is_applicable:
                logger.debug(f"Skipping {rule.code}: {result.skip_reason}")
                continue

            if result.amount == Decimal("0"):
                continue

            # Categorize by applicability
            if rule.applicability == RuleApplicability.EMPLOYEE:
                employee_deductions.append(result)
            elif rule.applicability == RuleApplicability.EMPLOYER:
                employer_contributions.append(result)
            elif rule.applicability == RuleApplicability.BOTH:
                employee_share = rule.employee_share if rule.employee_share is not None else Decimal("0.5")
                employer_share = rule.employer_share if rule.employer_share is not None else Decimal("0.5")
                employee_amount = (result.amount * employee_share).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                employer_amount = (result.amount * employer_share).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if employee_amount + employer_amount != result.amount:
                    employer_amount = (result.amount - employee_amount).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

                employee_details = dict(result.calc_details)
                employee_details.update({"employee_share": str(employee_share), "employer_share": str(employer_share)})

                employee_deductions.append(DeductionResult(
                    rule_code=result.rule_code,
                    rule_name=result.rule_name,
                    deduction_type=result.deduction_type,
                    applicability="employee",
                    amount=employee_amount,
                    calc_details=employee_details,
                ))
                employer_contributions.append(DeductionResult(
                    rule_code=f"{result.rule_code}_ER",
                    rule_name=f"{result.rule_name} (Employer)",
                    deduction_type=result.deduction_type,
                    applicability="employer",
                    amount=employer_amount,
                    calc_details=employee_details,
                ))

        total_employee = sum(d.amount for d in employee_deductions)
        total_employer = sum(d.amount for d in employer_contributions)
        net_pay = gross_pay - total_employee

        return PayrollDeductionsResult(
            region_code=self.region_code,
            gross_pay=gross_pay,
            employee_deductions=employee_deductions,
            employer_contributions=employer_contributions,
            total_employee_deductions=total_employee,
            total_employer_contributions=total_employer,
            net_pay=net_pay,
            calc_date=calc_date,
        )

    def to_dict(self, result: PayrollDeductionsResult) -> Dict[str, Any]:
        """Convert PayrollDeductionsResult to a dict for JSON serialization."""
        return {
            "region_code": result.region_code,
            "gross_pay": str(result.gross_pay),
            "net_pay": str(result.net_pay),
            "total_employee_deductions": str(result.total_employee_deductions),
            "total_employer_contributions": str(result.total_employer_contributions),
            "calc_date": result.calc_date.isoformat(),
            "employee_deductions": [
                {
                    "code": d.rule_code,
                    "name": d.rule_name,
                    "type": d.deduction_type,
                    "amount": str(d.amount),
                    "details": d.calc_details,
                }
                for d in result.employee_deductions
            ],
            "employer_contributions": [
                {
                    "code": d.rule_code,
                    "name": d.rule_name,
                    "type": d.deduction_type,
                    "amount": str(d.amount),
                    "details": d.calc_details,
                }
                for d in result.employer_contributions
            ],
        }


# ============= UTILITY FUNCTIONS =============


def get_payroll_builder(
    db: Session,
    region_code: str,
    cache_ttl_seconds: Optional[int] = None,
) -> PayrollBuilder:
    """Factory function to create a PayrollBuilder for dependency injection."""
    ttl = settings.payroll_cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
    return PayrollBuilder(db, region_code, cache_ttl_seconds=ttl)


def calculate_deductions_for_slip(
    db: Session,
    region_code: str,
    salary_components: Dict[str, Decimal],
    employment_type: Optional[str] = None,
    months_of_service: int = 0,
    calc_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Convenience function to calculate deductions and return a dict.

    Compatible with the existing Nigeria calculate_slip_deductions interface.
    """
    builder = PayrollBuilder(db, region_code)
    result = builder.calculate_deductions(
        salary_components=salary_components,
        employment_type=employment_type,
        months_of_service=months_of_service,
        calc_date=calc_date,
    )
    return builder.to_dict(result)
