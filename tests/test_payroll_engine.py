"""
Unit tests for Generic Payroll Engine

Tests the DeductionCalculator and PayrollBuilder classes with various
calculation methods: FLAT, PERCENTAGE, PROGRESSIVE.
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)
from app.services.payroll_engine import (
    DeductionCalculator,
    PayrollBuilder,
    DeductionResult,
    PayrollDeductionsResult,
)
from app.api.tax.helpers import PAYE_BANDS_PITA


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_region():
    """Create a mock PayrollRegion."""
    region = MagicMock(spec=PayrollRegion)
    region.id = 1
    region.code = "NG"
    region.name = "Nigeria"
    region.currency = "NGN"
    region.is_active = True
    return region


@pytest.fixture
def mock_flat_rule():
    """Create a mock FLAT deduction rule."""
    rule = MagicMock(spec=DeductionRule)
    rule.id = 1
    rule.code = "TEST_FLAT"
    rule.name = "Test Flat Deduction"
    rule.deduction_type = DeductionType.LEVY
    rule.applicability = RuleApplicability.EMPLOYEE
    rule.calc_method = CalcMethod.FLAT
    rule.flat_amount = Decimal("5000")
    rule.rate = None
    rule.base_components = None
    rule.min_base = None
    rule.max_base = None
    rule.cap_amount = None
    rule.floor_amount = None
    rule.employment_types = None
    rule.min_service_months = 0
    rule.is_statutory = True
    rule.display_order = 1
    return rule


@pytest.fixture
def mock_percentage_rule():
    """Create a mock PERCENTAGE deduction rule."""
    rule = MagicMock(spec=DeductionRule)
    rule.id = 2
    rule.code = "PENSION_EE"
    rule.name = "Pension (Employee)"
    rule.deduction_type = DeductionType.PENSION
    rule.applicability = RuleApplicability.EMPLOYEE
    rule.calc_method = CalcMethod.PERCENTAGE
    rule.flat_amount = None
    rule.rate = Decimal("0.08")  # 8%
    rule.base_components = ["basic", "housing", "transport"]
    rule.min_base = None
    rule.max_base = None
    rule.cap_amount = None
    rule.floor_amount = None
    rule.employment_types = None
    rule.min_service_months = 0
    rule.is_statutory = True
    rule.display_order = 2
    return rule


@pytest.fixture
def mock_progressive_rule():
    """Create a mock PROGRESSIVE deduction rule (PAYE)."""
    rule = MagicMock(spec=DeductionRule)
    rule.id = 3
    rule.code = "PAYE"
    rule.name = "Pay As You Earn"
    rule.deduction_type = DeductionType.TAX
    rule.applicability = RuleApplicability.EMPLOYEE
    rule.calc_method = CalcMethod.PROGRESSIVE
    rule.flat_amount = None
    rule.rate = None
    rule.base_components = ["basic", "housing", "transport", "other"]
    rule.min_base = None
    rule.max_base = None
    rule.cap_amount = None
    rule.floor_amount = None
    rule.employment_types = None
    rule.min_service_months = 0
    rule.is_statutory = True
    rule.display_order = 1
    return rule


@pytest.fixture
def mock_tax_bands():
    """Create mock PITA progressive tax bands."""
    bands = []
    for i, (lower, upper, rate) in enumerate(PAYE_BANDS_PITA):
        band = MagicMock(spec=TaxBand)
        band.id = i + 1
        band.deduction_rule_id = 3
        band.lower_limit = lower
        band.upper_limit = upper
        band.rate = rate
        band.band_order = i
        bands.append(band)

    return bands


@pytest.fixture
def salary_components():
    """Standard salary components for testing."""
    return {
        "basic_salary": Decimal("300000"),
        "housing_allowance": Decimal("100000"),
        "transport_allowance": Decimal("50000"),
        "other_allowances": Decimal("50000"),
    }


# =============================================================================
# DEDUCTION CALCULATOR TESTS
# =============================================================================


class TestDeductionCalculator:
    """Tests for DeductionCalculator class."""

    def test_calculate_flat_basic(self, mock_flat_rule):
        """Test basic FLAT calculation."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_flat(mock_flat_rule, Decimal("500000"))

        assert result == Decimal("5000.00")

    def test_calculate_flat_with_cap(self, mock_flat_rule):
        """Test FLAT calculation with cap."""
        mock_flat_rule.cap_amount = Decimal("3000")
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_flat(mock_flat_rule, Decimal("500000"))

        assert result == Decimal("3000.00")

    def test_calculate_flat_with_floor(self, mock_flat_rule):
        """Test FLAT calculation with floor."""
        mock_flat_rule.flat_amount = Decimal("1000")
        mock_flat_rule.floor_amount = Decimal("2000")
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_flat(mock_flat_rule, Decimal("500000"))

        assert result == Decimal("2000.00")

    def test_calculate_percentage_basic(self, mock_percentage_rule, salary_components):
        """Test basic PERCENTAGE calculation."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_percentage(mock_percentage_rule, salary_components)

        # Base = basic (300000) + housing (100000) + transport (50000) = 450000
        # 8% of 450000 = 36000
        assert result == Decimal("36000.00")

    def test_calculate_percentage_with_max_base(self, mock_percentage_rule, salary_components):
        """Test PERCENTAGE calculation with max base."""
        mock_percentage_rule.max_base = Decimal("400000")
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_percentage(mock_percentage_rule, salary_components)

        # Base capped at 400000, 8% = 32000
        assert result == Decimal("32000.00")

    def test_calculate_percentage_with_cap(self, mock_percentage_rule, salary_components):
        """Test PERCENTAGE calculation with amount cap."""
        mock_percentage_rule.cap_amount = Decimal("30000")
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        result = calculator.calculate_percentage(mock_percentage_rule, salary_components)

        # 8% of 450000 = 36000, capped at 30000
        assert result == Decimal("30000.00")

    def test_calculate_base_with_components(self, mock_percentage_rule, salary_components):
        """Test base calculation from component names."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        base = calculator.calculate_base(mock_percentage_rule, salary_components)

        # Should match basic_salary + housing_allowance + transport_allowance
        assert base == Decimal("450000")

    def test_calculate_base_all_components(self, mock_percentage_rule, salary_components):
        """Test base calculation when no base_components specified."""
        mock_percentage_rule.base_components = None
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        base = calculator.calculate_base(mock_percentage_rule, salary_components)

        # Should sum all components
        assert base == Decimal("500000")

    def test_calculate_progressive_basic(self, mock_progressive_rule, mock_tax_bands):
        """Test basic PROGRESSIVE (tax band) calculation."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")
        calculator._bands_cache[3] = mock_tax_bands

        # Monthly income of 200000 -> annual 2400000
        # Band 1: 300000 * 7% = 21000
        # Band 2: 300000 * 11% = 33000
        # Band 3: 500000 * 15% = 75000
        # Band 4: 500000 * 19% = 95000
        # Band 5: 800000 * 21% = 168000
        # Total annual: 392000
        # Monthly: 392000 / 12 = 32666.67

        result = calculator.calculate_progressive(mock_progressive_rule, Decimal("200000"))

        assert result == Decimal("32666.67")

    def test_calculate_progressive_low_income(self, mock_progressive_rule, mock_tax_bands):
        """Test PROGRESSIVE calculation for low income (single band)."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")
        calculator._bands_cache[3] = mock_tax_bands

        # Monthly income of 20000 -> annual 240000
        # Only Band 1 applies: 240000 * 7% = 16800
        # Monthly: 16800 / 12 = 1400

        result = calculator.calculate_progressive(mock_progressive_rule, Decimal("20000"))

        assert result == Decimal("1400.00")

    def test_calculate_progressive_high_income(self, mock_progressive_rule, mock_tax_bands):
        """Test PROGRESSIVE calculation for high income (all bands)."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")
        calculator._bands_cache[3] = mock_tax_bands

        # Monthly income of 400000 -> annual 4800000
        # Band 1: 300000 * 7% = 21000
        # Band 2: 300000 * 11% = 33000
        # Band 3: 500000 * 15% = 75000
        # Band 4: 500000 * 19% = 95000
        # Band 5: 1600000 * 21% = 336000
        # Band 6: 1600000 * 24% = 384000
        # Total annual: 944000
        # Monthly: 944000 / 12 = 78666.67

        result = calculator.calculate_progressive(mock_progressive_rule, Decimal("400000"))

        assert result == Decimal("78666.67")

    def test_is_applicable_no_restrictions(self, mock_percentage_rule):
        """Test applicability check with no restrictions."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        is_applicable, reason = calculator.is_applicable(
            mock_percentage_rule,
            employment_type="PERMANENT",
            months_of_service=6,
        )

        assert is_applicable is True
        assert reason is None

    def test_is_applicable_wrong_employment_type(self, mock_percentage_rule):
        """Test applicability check with wrong employment type."""
        mock_percentage_rule.employment_types = ["PERMANENT", "CONTRACT"]
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        is_applicable, reason = calculator.is_applicable(
            mock_percentage_rule,
            employment_type="INTERN",
            months_of_service=6,
        )

        assert is_applicable is False
        assert "Employment type" in reason

    def test_is_applicable_insufficient_service(self, mock_percentage_rule):
        """Test applicability check with insufficient service months."""
        mock_percentage_rule.min_service_months = 12
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        is_applicable, reason = calculator.is_applicable(
            mock_percentage_rule,
            employment_type="PERMANENT",
            months_of_service=6,
        )

        assert is_applicable is False
        assert "months service" in reason


# =============================================================================
# PAYROLL BUILDER TESTS
# =============================================================================


class TestPayrollBuilder:
    """Tests for PayrollBuilder class."""

    def test_calculate_deductions_empty_region(self, salary_components):
        """Test calculation when region has no rules."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        builder = PayrollBuilder(mock_db, "XX")
        result = builder.calculate_deductions(salary_components)

        assert result.region_code == "XX"
        assert result.gross_pay == Decimal("500000")
        assert result.net_pay == Decimal("500000")
        assert len(result.employee_deductions) == 0
        assert len(result.employer_contributions) == 0

    def test_deduction_result_to_dict(self, salary_components):
        """Test PayrollBuilder.to_dict serialization."""
        mock_db = MagicMock()
        builder = PayrollBuilder(mock_db, "NG")

        result = PayrollDeductionsResult(
            region_code="NG",
            gross_pay=Decimal("500000"),
            employee_deductions=[
                DeductionResult(
                    rule_code="PENSION_EE",
                    rule_name="Pension (Employee)",
                    deduction_type="pension",
                    applicability="employee",
                    amount=Decimal("36000"),
                    calc_details={"method": "percentage", "rate": "0.08"},
                ),
            ],
            employer_contributions=[],
            total_employee_deductions=Decimal("36000"),
            total_employer_contributions=Decimal("0"),
            net_pay=Decimal("464000"),
            calc_date=date(2025, 1, 15),
        )

        output = builder.to_dict(result)

        assert output["region_code"] == "NG"
        assert output["gross_pay"] == "500000"
        assert output["net_pay"] == "464000"
        assert len(output["employee_deductions"]) == 1
        assert output["employee_deductions"][0]["code"] == "PENSION_EE"
        assert output["employee_deductions"][0]["amount"] == "36000"


# =============================================================================
# INTEGRATION-STYLE TESTS (With Mocked DB)
# =============================================================================


class TestPayrollEngineIntegration:
    """Integration-style tests with mocked database."""

    def test_full_nigeria_style_deductions(
        self,
        mock_region,
        mock_percentage_rule,
        mock_progressive_rule,
        mock_tax_bands,
        salary_components,
    ):
        """Test full payroll calculation with Nigeria-style rules."""
        mock_db = MagicMock()

        # Setup region query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_region

        # Create employer pension rule
        mock_pension_er = MagicMock(spec=DeductionRule)
        mock_pension_er.id = 4
        mock_pension_er.code = "PENSION_ER"
        mock_pension_er.name = "Pension (Employer)"
        mock_pension_er.deduction_type = DeductionType.PENSION
        mock_pension_er.applicability = RuleApplicability.EMPLOYER
        mock_pension_er.calc_method = CalcMethod.PERCENTAGE
        mock_pension_er.rate = Decimal("0.10")  # 10%
        mock_pension_er.base_components = ["basic", "housing", "transport"]
        mock_pension_er.employment_types = None
        mock_pension_er.min_service_months = 0
        mock_pension_er.is_statutory = True
        mock_pension_er.display_order = 3
        mock_pension_er.min_base = None
        mock_pension_er.max_base = None
        mock_pension_er.cap_amount = None
        mock_pension_er.floor_amount = None

        # Setup active rules query
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_progressive_rule,
            mock_percentage_rule,
            mock_pension_er,
        ]

        calculator = DeductionCalculator(mock_db, "NG")
        calculator._region = mock_region
        calculator._rules_cache = {
            f"PAYE:{date.today()}": mock_progressive_rule,
            f"PENSION_EE:{date.today()}": mock_percentage_rule,
            f"PENSION_ER:{date.today()}": mock_pension_er,
        }
        calculator._bands_cache[3] = mock_tax_bands

        builder = PayrollBuilder(mock_db, "NG")
        builder.calculator = calculator

        result = builder.calculate_deductions(
            salary_components=salary_components,
            employment_type="PERMANENT",
            months_of_service=12,
        )

        # Verify results
        assert result.region_code == "NG"
        assert result.gross_pay == Decimal("500000")

        # Employee deductions should include PAYE and Pension
        employee_codes = [d.rule_code for d in result.employee_deductions]
        assert "PENSION_EE" in employee_codes

        # Employer contributions should include Pension
        employer_codes = [d.rule_code for d in result.employer_contributions]
        assert "PENSION_ER" in employer_codes

        # Net pay should be gross minus employee deductions
        assert result.net_pay == result.gross_pay - result.total_employee_deductions

    def test_both_applicability_split(self, mock_region, salary_components):
        """Test rule with BOTH applicability splits correctly."""
        mock_db = MagicMock()

        # Create BOTH applicability rule (e.g., NHIS)
        mock_nhis = MagicMock(spec=DeductionRule)
        mock_nhis.id = 5
        mock_nhis.code = "NHIS"
        mock_nhis.name = "National Health Insurance"
        mock_nhis.deduction_type = DeductionType.INSURANCE
        mock_nhis.applicability = RuleApplicability.BOTH
        mock_nhis.calc_method = CalcMethod.PERCENTAGE
        mock_nhis.rate = Decimal("0.15")  # 15% total
        mock_nhis.base_components = ["basic"]
        mock_nhis.employee_share = Decimal("0.3333")  # 1/3
        mock_nhis.employer_share = Decimal("0.6667")  # 2/3
        mock_nhis.employment_types = None
        mock_nhis.min_service_months = 0
        mock_nhis.is_statutory = True
        mock_nhis.display_order = 1
        mock_nhis.min_base = None
        mock_nhis.max_base = None
        mock_nhis.cap_amount = None
        mock_nhis.floor_amount = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_region
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_nhis]

        calculator = DeductionCalculator(mock_db, "NG")
        calculator._region = mock_region
        calculator._rules_cache = {f"NHIS:{date.today()}": mock_nhis}

        builder = PayrollBuilder(mock_db, "NG")
        builder.calculator = calculator

        result = builder.calculate_deductions(salary_components)

        # Total NHIS = 15% of basic (300000) = 45000
        # Employee: 45000 * 0.3333 = 14998.50
        # Employer: 45000 * 0.6667 = 30001.50

        assert len(result.employee_deductions) == 1
        assert len(result.employer_contributions) == 1

        employee_nhis = result.employee_deductions[0]
        employer_nhis = result.employer_contributions[0]

        assert employee_nhis.rule_code == "NHIS"
        assert employer_nhis.rule_code == "NHIS_ER"

        # Verify total equals calculated amount (allowing for rounding)
        total_nhis = employee_nhis.amount + employer_nhis.amount
        assert total_nhis == Decimal("45000.00")


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_salary(self):
        """Test calculation with zero salary."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        builder = PayrollBuilder(mock_db, "NG")
        result = builder.calculate_deductions({})

        assert result.gross_pay == Decimal("0")
        assert result.net_pay == Decimal("0")

    def test_negative_after_deductions(self, mock_region, salary_components):
        """Test behavior when deductions exceed gross (edge case)."""
        mock_db = MagicMock()

        # Create a rule with huge flat amount
        mock_huge_rule = MagicMock(spec=DeductionRule)
        mock_huge_rule.id = 99
        mock_huge_rule.code = "HUGE"
        mock_huge_rule.name = "Huge Deduction"
        mock_huge_rule.deduction_type = DeductionType.LEVY
        mock_huge_rule.applicability = RuleApplicability.EMPLOYEE
        mock_huge_rule.calc_method = CalcMethod.FLAT
        mock_huge_rule.flat_amount = Decimal("1000000")  # More than gross
        mock_huge_rule.employment_types = None
        mock_huge_rule.min_service_months = 0
        mock_huge_rule.is_statutory = True
        mock_huge_rule.display_order = 1
        mock_huge_rule.min_base = None
        mock_huge_rule.max_base = None
        mock_huge_rule.cap_amount = None
        mock_huge_rule.floor_amount = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_region
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_huge_rule]

        calculator = DeductionCalculator(mock_db, "NG")
        calculator._region = mock_region
        calculator._rules_cache = {f"HUGE:{date.today()}": mock_huge_rule}

        builder = PayrollBuilder(mock_db, "NG")
        builder.calculator = calculator

        result = builder.calculate_deductions(salary_components)

        # Net pay can go negative in this implementation
        # Real system would need validation
        assert result.net_pay < Decimal("0")

    def test_progressive_zero_income(self, mock_progressive_rule, mock_tax_bands):
        """Test PROGRESSIVE calculation with zero income."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")
        calculator._bands_cache[3] = mock_tax_bands

        result = calculator.calculate_progressive(mock_progressive_rule, Decimal("0"))

        assert result == Decimal("0.00")

    def test_rounding_precision(self, mock_percentage_rule):
        """Test that calculations maintain correct decimal precision."""
        mock_db = MagicMock()
        calculator = DeductionCalculator(mock_db, "NG")

        # Use values that will create rounding scenarios
        salary_components = {
            "basic_salary": Decimal("333333.33"),
            "housing_allowance": Decimal("111111.11"),
            "transport_allowance": Decimal("55555.56"),
        }

        result = calculator.calculate_percentage(mock_percentage_rule, salary_components)

        # Result should be rounded to 2 decimal places
        assert result == result.quantize(Decimal("0.01"))
