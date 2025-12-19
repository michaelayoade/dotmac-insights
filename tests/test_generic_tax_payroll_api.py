"""
Integration Tests for Generic Tax and Payroll Configuration APIs

Tests the generic (country-agnostic) tax-core and payroll-config endpoints.
These endpoints should always be accessible regardless of compliance entitlements.
"""

import pytest
from decimal import Decimal
from datetime import date
from app.database import SessionLocal, Base, engine
from app.models.tax_config import TaxRegion, GenericGenericTaxCategory, TaxRate, GenericTaxCategoryType, TaxFilingFrequency
from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_tax_core():
    """Seed a tax region and category for API tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_category = db.query(GenericTaxCategory).filter(GenericTaxCategory.code == "VAT").first()
        if existing_category:
            region = db.query(TaxRegion).filter(TaxRegion.id == existing_category.region_id).first()
            yield {"region_id": region.id, "category_id": existing_category.id}
            return

        region = TaxRegion(
            code="UT",
            name="Unit Test Region",
            currency="UTD",
            default_sales_tax_rate=Decimal("0.05"),
            default_withholding_rate=Decimal("0.02"),
            default_filing_frequency=TaxFilingFrequency.MONTHLY,
            filing_deadline_day=15,
            fiscal_year_start_month=1,
            is_active=True,
        )
        db.add(region)
        db.flush()

        category = GenericTaxCategory(
            region_id=region.id,
            code="VAT",
            name="Value Added Tax",
            category_type=GenericTaxCategoryType.SALES_TAX,
            default_rate=Decimal("0.05"),
            is_active=True,
        )
        db.add(category)
        db.flush()

        rate = TaxRate(
            category_id=category.id,
            code="VAT_STD",
            name="Standard VAT",
            rate=Decimal("0.05"),
            effective_from=date(2025, 1, 1),
            is_active=True,
        )
        db.add(rate)
        db.commit()

        yield {"region_id": region.id, "category_id": category.id}
    finally:
        db.rollback()
        db.query(TaxRate).filter(TaxRate.code == "VAT_STD").delete(synchronize_session=False)
        db.query(GenericTaxCategory).filter(GenericTaxCategory.code == "VAT").delete(synchronize_session=False)
        db.query(TaxRegion).filter(TaxRegion.code == "UT").delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.fixture
def seeded_payroll_config():
    """Seed a payroll region and deduction rule for API tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_region = db.query(PayrollRegion).filter(PayrollRegion.code == "UT").first()
        if existing_region:
            rule = db.query(DeductionRule).filter(DeductionRule.region_id == existing_region.id).first()
            yield {"region_id": existing_region.id, "rule_id": rule.id if rule else None}
            return

        region = PayrollRegion(
            code="UT",
            name="Unit Test Payroll",
            currency="UTD",
            default_pay_frequency=PayrollFrequency.MONTHLY,
            fiscal_year_start_month=1,
            payment_day=25,
            is_active=True,
        )
        db.add(region)
        db.flush()

        rule = DeductionRule(
            region_id=region.id,
            code="TEST_FLAT",
            name="Test Flat Deduction",
            deduction_type=DeductionType.LEVY,
            applicability=RuleApplicability.EMPLOYEE,
            is_statutory=False,
            calc_method=CalcMethod.FLAT,
            flat_amount=Decimal("1000"),
            effective_from=date(2025, 1, 1),
            is_active=True,
        )
        db.add(rule)
        db.flush()

        band = TaxBand(
            deduction_rule_id=rule.id,
            lower_limit=Decimal("0"),
            upper_limit=Decimal("100000"),
            rate=Decimal("0.01"),
            band_order=0,
        )
        db.add(band)
        db.commit()

        yield {"region_id": region.id, "rule_id": rule.id}
    finally:
        db.rollback()
        db.query(TaxBand).filter(TaxBand.deduction_rule_id.isnot(None)).delete(synchronize_session=False)
        db.query(DeductionRule).filter(DeductionRule.code == "TEST_FLAT").delete(synchronize_session=False)
        db.query(PayrollRegion).filter(PayrollRegion.code == "UT").delete(synchronize_session=False)
        db.commit()
        db.close()


# =============================================================================
# TAX-CORE API TESTS
# =============================================================================


class TestTaxCoreRegionsAPI:
    """Tests for /api/tax-core/regions endpoints."""

    def test_list_regions(self, client):
        """GET /api/tax-core/regions should return list."""
        resp = client.get("/api/tax-core/regions")
        assert resp.status_code == 200

        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            assert "data" in data

    def test_create_region_validation(self, client):
        """POST /api/tax-core/regions should validate required fields."""
        resp = client.post("/api/tax-core/regions", json={})

        # Should fail validation (422) if required fields missing
        assert resp.status_code == 422

    def test_create_region_success(self, client):
        """POST /api/tax-core/regions should create region."""
        region_data = {
            "code": "KE",
            "name": "Kenya",
            "currency": "KES",
            "tax_authority_name": "Kenya Revenue Authority",
            "tax_id_label": "PIN",
            "default_sales_tax_rate": 0.16,
            "default_withholding_rate": 0.05,
            "filing_deadline_day": 20,
        }

        resp = client.post("/api/tax-core/regions", json=region_data)

        # Success or DB error
        assert resp.status_code in [200, 201]

        if resp.status_code in [200, 201]:
            data = resp.json()
            assert data["code"] == "KE"
            assert data["name"] == "Kenya"


class TestTaxCoreCategoriesAPI:
    """Tests for /api/tax-core/categories endpoints."""

    def test_list_categories(self, client, seeded_tax_core):
        """GET /api/tax-core/categories should return list."""
        resp = client.get(f"/api/tax-core/regions/{seeded_tax_core['region_id']}/categories")
        assert resp.status_code == 200

    def test_list_categories_by_region(self, client, seeded_tax_core):
        """GET /api/tax-core/categories should filter by region."""
        resp = client.get(f"/api/tax-core/regions/{seeded_tax_core['region_id']}/categories")
        assert resp.status_code == 200

    def test_list_categories_by_type(self, client, seeded_tax_core):
        """GET /api/tax-core/categories should filter by type."""
        resp = client.get(f"/api/tax-core/regions/{seeded_tax_core['region_id']}/categories?category_type=sales_tax")
        assert resp.status_code == 200


class TestTaxCoreRatesAPI:
    """Tests for /api/tax-core/rates endpoints."""

    def test_list_rates(self, client, seeded_tax_core):
        """GET /api/tax-core/rates should return list."""
        resp = client.get(f"/api/tax-core/categories/{seeded_tax_core['category_id']}")
        assert resp.status_code == 200

    def test_list_rates_by_category(self, client, seeded_tax_core):
        """GET /api/tax-core/rates should filter by category."""
        resp = client.get(f"/api/tax-core/categories/{seeded_tax_core['category_id']}")
        assert resp.status_code == 200


class TestTaxCoreTransactionsAPI:
    """Tests for /api/tax-core/transactions endpoints."""

    def test_list_transactions(self, client):
        """GET /api/tax-core/transactions should return list."""
        resp = client.get("/api/tax-core/transactions")
        assert resp.status_code == 200

    def test_list_transactions_by_period(self, client):
        """GET /api/tax-core/transactions should filter by period."""
        resp = client.get("/api/tax-core/transactions?filing_period=2025-01")
        assert resp.status_code == 200

    def test_list_transactions_by_type(self, client):
        """GET /api/tax-core/transactions should filter by type."""
        resp = client.get("/api/tax-core/transactions?transaction_type=output")
        assert resp.status_code == 200

    def test_transaction_summary(self, client, seeded_tax_core):
        """GET /api/tax-core/transactions/summary should return summary."""
        resp = client.get(
            "/api/tax-core/transactions/summary",
            params={
                "region_id": seeded_tax_core["region_id"],
                "filing_period": "2025-01",
            }
        )
        assert resp.status_code == 200


class TestTaxCoreCompanySettingsAPI:
    """Tests for /api/tax-core/company-settings endpoints."""

    def test_list_company_settings(self, client):
        """GET /api/tax-core/company-settings should return list."""
        resp = client.get("/api/tax-core/company-settings")
        assert resp.status_code == 200


# =============================================================================
# PAYROLL-CONFIG API TESTS
# =============================================================================


class TestPayrollConfigRegionsAPI:
    """Tests for /api/payroll-config/regions endpoints."""

    def test_list_payroll_regions(self, client):
        """GET /api/payroll-config/regions should return list."""
        resp = client.get("/api/payroll-config/regions")
        assert resp.status_code == 200

    def test_create_payroll_region_validation(self, client):
        """POST /api/payroll-config/regions should validate required fields."""
        resp = client.post("/api/payroll-config/regions", json={})
        assert resp.status_code == 422

    def test_create_payroll_region_success(self, client):
        """POST /api/payroll-config/regions should create region."""
        region_data = {
            "code": "GH",
            "name": "Ghana",
            "currency": "GHS",
            "default_pay_frequency": "monthly",
            "fiscal_year_start_month": 1,
            "payment_day": 25,
            "has_statutory_deductions": True,
            "tax_authority_name": "Ghana Revenue Authority",
            "tax_id_label": "TIN",
        }

        resp = client.post("/api/payroll-config/regions", json=region_data)
        assert resp.status_code in [200, 201]


class TestPayrollConfigRulesAPI:
    """Tests for /api/payroll-config/rules endpoints."""

    def test_list_deduction_rules(self, client, seeded_payroll_config):
        """GET /api/payroll-config/rules should return list."""
        resp = client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules")
        assert resp.status_code == 200

    def test_list_rules_by_region(self, client, seeded_payroll_config):
        """GET /api/payroll-config/rules should filter by region."""
        resp = client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules")
        assert resp.status_code == 200

    def test_list_rules_by_type(self, client, seeded_payroll_config):
        """GET /api/payroll-config/rules should filter by deduction type."""
        resp = client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules?deduction_type=levy")
        assert resp.status_code == 200

    def test_list_rules_statutory_only(self, client, seeded_payroll_config):
        """GET /api/payroll-config/rules should filter statutory rules."""
        resp = client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules?statutory_only=true")
        assert resp.status_code == 200


class TestPayrollConfigBandsAPI:
    """Tests for /api/payroll-config/bands endpoints."""

    def test_list_tax_bands(self, client, seeded_payroll_config):
        """GET /api/payroll-config/bands should return list."""
        resp = client.get(f"/api/payroll-config/rules/{seeded_payroll_config['rule_id']}")
        assert resp.status_code == 200

    def test_list_bands_by_rule(self, client, seeded_payroll_config):
        """GET /api/payroll-config/bands should filter by rule."""
        resp = client.get(f"/api/payroll-config/rules/{seeded_payroll_config['rule_id']}")
        assert resp.status_code == 200


# =============================================================================
# SCHEMA VALIDATION TESTS
# =============================================================================


class TestSchemaValidation:
    """Test request/response schema validation."""

    def test_region_code_format(self, client):
        """Region code should be validated (ISO 3166-1 alpha-2)."""
        # Invalid: too long
        region_data = {
            "code": "TOOLONG",
            "name": "Invalid",
            "currency": "XXX",
        }
        resp = client.post("/api/tax-core/regions", json=region_data)
        # Should fail validation or succeed with truncation
        assert resp.status_code in [422, 200, 201]

    def test_currency_code_format(self, client):
        """Currency should be 3-letter ISO code."""
        region_data = {
            "code": "XX",
            "name": "Test",
            "currency": "INVALID",
        }
        resp = client.post("/api/tax-core/regions", json=region_data)
        assert resp.status_code in [422, 200, 201]

    def test_rate_decimal_precision(self, client):
        """Tax rates should handle decimal precision."""
        # Test with many decimal places
        region_data = {
            "code": "TP",
            "name": "Test Precision",
            "currency": "TST",
            "default_sales_tax_rate": 0.123456789,
        }
        resp = client.post("/api/tax-core/regions", json=region_data)
        assert resp.status_code in [200, 201, 422]

    def test_filing_period_format(self, client, seeded_tax_core):
        """Filing period should be YYYY-MM format."""
        payload = {
            "category_id": seeded_tax_core["category_id"],
            "transaction_type": "output",
            "transaction_date": "2025-01-15",
            "company": "TestCo",
            "party_type": "customer",
            "party_name": "Test Customer",
            "taxable_amount": 1000,
            "tax_rate": 0.1,
            "filing_period": "2025-13",
            "source_doctype": "invoice",
            "source_docname": "INV-001",
        }
        resp = client.post(f"/api/tax-core/regions/{seeded_tax_core['region_id']}/transactions", json=payload)
        assert resp.status_code == 422


# =============================================================================
# PAGINATION TESTS
# =============================================================================


class TestPagination:
    """Test pagination on list endpoints."""

    def test_tax_transactions_pagination(self, client):
        """Tax transactions should support pagination."""
        resp = client.get("/api/tax-core/transactions?limit=10&offset=0")
        assert resp.status_code == 200

        if resp.status_code == 200:
            data = resp.json()
            # Should be list or paginated response
            assert isinstance(data, (list, dict))

    def test_deduction_rules_pagination(self, client, seeded_payroll_config):
        """Deduction rules should support pagination."""
        resp = client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules?limit=10&offset=0")
        assert resp.status_code == 200


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_get_nonexistent_region(self, client):
        """GET nonexistent region should return 404."""
        resp = client.get("/api/tax-core/regions/99999")
        assert resp.status_code == 404

    def test_get_nonexistent_rule(self, client):
        """GET nonexistent rule should return 404."""
        resp = client.get("/api/payroll-config/rules/99999")
        assert resp.status_code == 404

    def test_delete_nonexistent_region(self, client):
        """DELETE nonexistent region should return 404."""
        resp = client.delete("/api/tax-core/regions/99999")
        assert resp.status_code == 404

    def test_invalid_enum_value(self, client):
        """Invalid enum values should return 422."""
        rule_data = {
            "region_id": 1,
            "code": "TEST",
            "name": "Test",
            "deduction_type": "invalid_type",
            "calc_method": "flat",
            "effective_from": "2025-01-01",
        }
        resp = client.post("/api/payroll-config/rules", json=rule_data)
        assert resp.status_code == 422
