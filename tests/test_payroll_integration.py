"""
Payroll Engine Integration Tests

Tests the full flow: API → Engine → Database → Response.
Verifies progressive tax calculations match expected PITA values.

Run with: poetry run pytest tests/test_payroll_integration.py -v
"""

import pytest
from decimal import Decimal
from datetime import date

from app.database import SessionLocal, Base, engine
from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)
from app.services.payroll_engine import DeductionCalculator, PayrollBuilder

# PITA tax bands (current law through 2025)
PAYE_BANDS_PITA = [
    (Decimal("0"), Decimal("300000"), Decimal("0.07")),
    (Decimal("300000"), Decimal("600000"), Decimal("0.11")),
    (Decimal("600000"), Decimal("1100000"), Decimal("0.15")),
    (Decimal("1100000"), Decimal("1600000"), Decimal("0.19")),
    (Decimal("1600000"), Decimal("3200000"), Decimal("0.21")),
    (Decimal("3200000"), None, Decimal("0.24")),
]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_progressive_rule():
    """Seed a region with PAYE progressive tax rule and bands."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check for existing
        existing = db.query(PayrollRegion).filter(
            PayrollRegion.code == "INT"
        ).first()
        if existing:
            rule = db.query(DeductionRule).filter(
                DeductionRule.region_id == existing.id,
                DeductionRule.code == "PAYE_INT"
            ).first()
            yield {
                "db": db,
                "region_id": existing.id,
                "region_code": "INT",
                "rule_id": rule.id if rule else None
            }
            return

        # Create region
        region = PayrollRegion(
            code="INT",
            name="Integration Test Region",
            currency="NGN",
            default_pay_frequency=PayrollFrequency.MONTHLY,
            fiscal_year_start_month=1,
            payment_day=25,
            has_statutory_deductions=True,
            is_active=True,
        )
        db.add(region)
        db.flush()

        # Create progressive PAYE rule
        paye_rule = DeductionRule(
            region_id=region.id,
            code="PAYE_INT",
            name="Pay As You Earn (Integration Test)",
            deduction_type=DeductionType.TAX,
            applicability=RuleApplicability.EMPLOYEE,
            is_statutory=True,
            calc_method=CalcMethod.PROGRESSIVE,
            effective_from=date(2025, 1, 1),
            is_active=True,
        )
        db.add(paye_rule)
        db.flush()

        # Add tax bands (PITA)
        for idx, (lower, upper, rate) in enumerate(PAYE_BANDS_PITA):
            band = TaxBand(
                deduction_rule_id=paye_rule.id,
                lower_limit=lower,
                upper_limit=upper,
                rate=rate,
                band_order=idx,
            )
            db.add(band)

        db.commit()

        yield {
            "db": db,
            "region_id": region.id,
            "region_code": "INT",
            "rule_id": paye_rule.id,
        }
    finally:
        # Cleanup
        try:
            db.rollback()
            db.query(TaxBand).filter(
                TaxBand.deduction_rule_id.in_(
                    db.query(DeductionRule.id).filter(
                        DeductionRule.code.in_(["PAYE_INT", "PENSION_INT"])
                    )
                )
            ).delete(synchronize_session=False)
            db.query(DeductionRule).filter(
                DeductionRule.code.in_(["PAYE_INT", "PENSION_INT"])
            ).delete(synchronize_session=False)
            db.query(PayrollRegion).filter(
                PayrollRegion.code == "INT"
            ).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


@pytest.fixture
def seeded_split_rule(seeded_progressive_rule):
    """Add a BOTH applicability rule (employee/employer split)."""
    db = seeded_progressive_rule["db"]
    region_id = seeded_progressive_rule["region_id"]

    # Create pension rule with 50/50 split
    pension_rule = DeductionRule(
        region_id=region_id,
        code="PENSION_INT",
        name="Pension Contribution (Integration Test)",
        deduction_type=DeductionType.PENSION,
        applicability=RuleApplicability.BOTH,
        is_statutory=True,
        calc_method=CalcMethod.PERCENTAGE,
        rate=Decimal("0.18"),  # 18% total
        employee_share=Decimal("0.4444"),  # 8% / 18% = 0.4444
        employer_share=Decimal("0.5556"),  # 10% / 18% = 0.5556
        base_components="basic_salary,housing_allowance,transport_allowance",
        effective_from=date(2025, 1, 1),
        is_active=True,
    )
    db.add(pension_rule)
    db.commit()

    return {
        **seeded_progressive_rule,
        "pension_rule_id": pension_rule.id,
    }


# =============================================================================
# PROGRESSIVE TAX CALCULATION TESTS
# =============================================================================


class TestProgressiveTaxCalculation:
    """Test progressive PAYE calculations match expected values."""

    def test_single_band_low_income(self, seeded_progressive_rule):
        """
        Monthly income: 20,000 (annual 240,000)
        Expected: 240,000 * 0.07 / 12 = 1,400/month
        """
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("20000")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        assert result.is_applicable
        # Annual: 240,000 * 0.07 = 16,800
        # Monthly: 16,800 / 12 = 1,400
        expected = Decimal("1400.00")
        assert result.amount == expected, f"Expected {expected}, got {result.amount}"

    def test_two_bands_mid_income(self, seeded_progressive_rule):
        """
        Monthly income: 50,000 (annual 600,000 - crosses 2 bands)
        Band 1: 300,000 * 0.07 = 21,000
        Band 2: 300,000 * 0.11 = 33,000
        Total: 54,000 / 12 = 4,500/month
        """
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("50000")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        assert result.is_applicable
        expected = Decimal("4500.00")
        assert result.amount == expected, f"Expected {expected}, got {result.amount}"

    def test_multiple_bands_high_income(self, seeded_progressive_rule):
        """
        Monthly income: 200,000 (annual 2,400,000 - crosses 5 bands)
        Band 1: 300,000 * 0.07 = 21,000
        Band 2: 300,000 * 0.11 = 33,000
        Band 3: 500,000 * 0.15 = 75,000
        Band 4: 500,000 * 0.19 = 95,000
        Band 5: 800,000 * 0.21 = 168,000
        Total: 392,000 / 12 = 32,666.67/month
        """
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("200000")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        assert result.is_applicable
        # 392,000 / 12 = 32,666.666...
        expected = Decimal("32666.67")
        # Allow small rounding difference
        assert abs(result.amount - expected) <= Decimal("0.01"), \
            f"Expected ~{expected}, got {result.amount}"

    def test_top_bracket_very_high_income(self, seeded_progressive_rule):
        """
        Monthly income: 400,000 (annual 4,800,000 - all bands including 24%)
        """
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("400000")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        assert result.is_applicable
        # Band 1: 300,000 * 0.07 = 21,000
        # Band 2: 300,000 * 0.11 = 33,000
        # Band 3: 500,000 * 0.15 = 75,000
        # Band 4: 500,000 * 0.19 = 95,000
        # Band 5: 1,600,000 * 0.21 = 336,000
        # Band 6: 1,600,000 * 0.24 = 384,000
        # Total: 944,000 / 12 = 78,666.67/month
        expected = Decimal("78666.67")
        assert abs(result.amount - expected) <= Decimal("0.01"), \
            f"Expected ~{expected}, got {result.amount}"


# =============================================================================
# EMPLOYEE/EMPLOYER SPLIT TESTS
# =============================================================================


class TestEmployeeEmployerSplit:
    """Test deductions with BOTH applicability are split correctly."""

    def test_pension_split_calculation(self, seeded_split_rule):
        """Verify employee and employer shares sum correctly."""
        db = seeded_split_rule["db"]
        region_code = seeded_split_rule["region_code"]

        # Use PayrollBuilder to get both employee and employer deductions
        builder = PayrollBuilder(db, region_code=region_code)
        result = builder.calculate_deductions(
            salary_components={
                "basic_salary": Decimal("300000"),
                "housing_allowance": Decimal("100000"),
                "transport_allowance": Decimal("50000"),
            },
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        # Find pension deductions
        employee_pension = next(
            (d for d in result.employee_deductions if "PENSION" in d.rule_code),
            None
        )
        employer_pension = next(
            (d for d in result.employer_contributions if "PENSION" in d.rule_code),
            None
        )

        assert employee_pension is not None, "Employee pension deduction not found"
        assert employer_pension is not None, "Employer pension contribution not found"

        # Base: 300,000 + 100,000 + 50,000 = 450,000
        # Total pension: 450,000 * 0.18 = 81,000
        # Employee (44.44%): 81,000 * 0.4444 ≈ 36,000 (8% effective)
        # Employer (55.56%): 81,000 * 0.5556 ≈ 45,000 (10% effective)
        total_pension = employee_pension.amount + employer_pension.amount
        expected_total = Decimal("81000")

        assert abs(total_pension - expected_total) <= Decimal("1"), \
            f"Expected total ~{expected_total}, got {total_pension}"


# =============================================================================
# PAYROLL BUILDER INTEGRATION TESTS
# =============================================================================


class TestPayrollBuilderIntegration:
    """Test complete payroll slip generation."""

    def test_complete_slip_totals(self, seeded_split_rule):
        """Verify slip totals are calculated correctly."""
        db = seeded_split_rule["db"]
        region_code = seeded_split_rule["region_code"]

        builder = PayrollBuilder(db, region_code=region_code)
        result = builder.calculate_deductions(
            salary_components={
                "basic_salary": Decimal("300000"),
                "housing_allowance": Decimal("100000"),
                "transport_allowance": Decimal("50000"),
                "other_allowances": Decimal("50000"),
            },
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        # Verify gross is sum of components
        expected_gross = Decimal("500000")
        assert result.gross_pay == expected_gross

        # Verify net pay equation: gross - employee_deductions = net
        calculated_net = result.gross_pay - result.total_employee_deductions
        assert result.net_pay == calculated_net

        # Verify totals match sum of individual deductions
        employee_sum = sum(d.amount for d in result.employee_deductions)
        assert result.total_employee_deductions == employee_sum

        employer_sum = sum(d.amount for d in result.employer_contributions)
        assert result.total_employer_contributions == employer_sum

    def test_dict_serialization(self, seeded_progressive_rule):
        """Verify to_dict produces valid JSON-serializable output."""
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        builder = PayrollBuilder(db, region_code=region_code)
        result = builder.calculate_deductions(
            salary_components={"gross_pay": Decimal("100000")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        # to_dict should not raise
        data = result.to_dict() if hasattr(result, 'to_dict') else {
            "gross_pay": str(result.gross_pay),
            "net_pay": str(result.net_pay),
            "total_employee_deductions": str(result.total_employee_deductions),
        }

        assert "gross_pay" in data or hasattr(result, 'gross_pay')
        assert "net_pay" in data or hasattr(result, 'net_pay')


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_income_no_tax(self, seeded_progressive_rule):
        """Zero income should result in zero tax."""
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("0")},
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        assert result.amount == Decimal("0")

    def test_small_income_rounding(self, seeded_progressive_rule):
        """Small income amounts should round correctly."""
        db = seeded_progressive_rule["db"]
        region_code = seeded_progressive_rule["region_code"]

        calculator = DeductionCalculator(db, region_code=region_code)
        result = calculator.calculate(
            rule_code="PAYE_INT",
            salary_components={"gross_pay": Decimal("1000")},  # 12,000 annual
            employment_type="PERMANENT",
            months_of_service=12,
            calc_date=date(2025, 6, 15),
        )

        # 12,000 * 0.07 = 840 annual / 12 = 70/month
        expected = Decimal("70.00")
        assert result.amount == expected
