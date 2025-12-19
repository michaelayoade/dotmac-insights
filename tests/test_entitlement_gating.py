"""
Tests for Entitlement Gating

Tests that Nigeria compliance features are properly gated behind feature flags
and return 403 when entitlements are not enabled.
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_principal, Principal
from app.feature_flags import feature_flags, FeatureFlags
from app.database import SessionLocal, Base, engine
from app.models.tax_config import TaxRegion, GenericTaxCategory, TaxRate, TaxCategoryType, TaxFilingFrequency
from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def authenticated_client():
    """Create an authenticated test client with standard permissions."""
    mock_principal = Principal(
        type="user",
        id=1,
        external_id="test_user",
        email="test@example.com",
        name="Test User",
        is_superuser=False,
        scopes={"*"},  # All scopes but not superuser
    )

    async def override_get_current_principal():
        return mock_principal

    app.dependency_overrides[get_current_principal] = override_get_current_principal

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = {}


@pytest.fixture
def flags_disabled():
    """Fixture to disable Nigeria compliance flags."""
    with patch.object(feature_flags, 'NIGERIA_COMPLIANCE_ENABLED', False), \
         patch.object(feature_flags, 'STATUTORY_CALCULATIONS_ENABLED', False):
        yield


@pytest.fixture
def flags_enabled():
    """Fixture to enable Nigeria compliance flags."""
    with patch.object(feature_flags, 'NIGERIA_COMPLIANCE_ENABLED', True), \
         patch.object(feature_flags, 'STATUTORY_CALCULATIONS_ENABLED', True):
        yield


@pytest.fixture
def seeded_tax_core():
    """Seed a tax region and category for gating tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        region = db.query(TaxRegion).filter(TaxRegion.code == "UTG").first()
        if not region:
            region = TaxRegion(
                code="UTG",
                name="Unit Test Gating Region",
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

        category = db.query(GenericTaxCategory).filter(GenericTaxCategory.code == "VAT_ENT").first()
        if not category:
            category = GenericTaxCategory(
                region_id=region.id,
                code="VAT_ENT",
                name="Value Added Tax",
                category_type=TaxCategoryType.SALES_TAX,
                default_rate=Decimal("0.05"),
                is_active=True,
            )
            db.add(category)
            db.flush()

        rate = db.query(TaxRate).filter(TaxRate.code == "VAT_STD_ENT").first()
        if not rate:
            rate = TaxRate(
                category_id=category.id,
                code="VAT_STD_ENT",
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
        db.query(TaxRate).filter(TaxRate.code == "VAT_STD_ENT").delete(synchronize_session=False)
        db.query(GenericTaxCategory).filter(GenericTaxCategory.code == "VAT_ENT").delete(synchronize_session=False)
        db.query(TaxRegion).filter(TaxRegion.code == "UTG").delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.fixture
def seeded_payroll_config():
    """Seed a payroll region and deduction rule for gating tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        region = db.query(PayrollRegion).filter(PayrollRegion.code == "UTG").first()
        if not region:
            region = PayrollRegion(
                code="UTG",
                name="Unit Test Payroll Gating",
                currency="UTD",
                default_pay_frequency=PayrollFrequency.MONTHLY,
                fiscal_year_start_month=1,
                payment_day=25,
                is_active=True,
            )
            db.add(region)
            db.flush()

        rule = db.query(DeductionRule).filter(DeductionRule.code == "TEST_FLAT_G").first()
        if not rule:
            rule = DeductionRule(
                region_id=region.id,
                code="TEST_FLAT_G",
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
        db.commit()

        yield {"region_id": region.id, "rule_id": rule.id}
    finally:
        db.rollback()
        db.query(DeductionRule).filter(DeductionRule.code == "TEST_FLAT_G").delete(synchronize_session=False)
        db.query(PayrollRegion).filter(PayrollRegion.code == "UTG").delete(synchronize_session=False)
        db.commit()
        db.close()


# =============================================================================
# NIGERIA TAX API GATING TESTS
# =============================================================================


class TestNigeriaTaxGating:
    """Test that Nigeria-specific tax endpoints are gated."""

    def test_vat_endpoints_gated_when_disabled(self, authenticated_client, flags_disabled):
        """VAT endpoints should return 403 when Nigeria compliance disabled."""
        # Test VAT transactions list
        resp = authenticated_client.get("/api/tax/vat/transactions")
        assert resp.status_code == 403
        assert "nigeria" in resp.json().get("detail", "").lower() or "entitlement" in resp.json().get("detail", "").lower()

    def test_wht_endpoints_gated_when_disabled(self, authenticated_client, flags_disabled):
        """WHT endpoints should return 403 when Nigeria compliance disabled."""
        resp = authenticated_client.get("/api/tax/wht/transactions")
        assert resp.status_code == 403

    def test_paye_endpoints_gated_when_disabled(self, authenticated_client, flags_disabled):
        """PAYE endpoints should return 403 when Nigeria compliance disabled."""
        resp = authenticated_client.get("/api/tax/paye/calculations")
        assert resp.status_code == 403

    def test_cit_endpoints_gated_when_disabled(self, authenticated_client, flags_disabled):
        """CIT endpoints should return 403 when Nigeria compliance disabled."""
        resp = authenticated_client.get("/api/tax/cit/assessments")
        assert resp.status_code == 403

    def test_filing_endpoints_gated_when_disabled(self, authenticated_client, flags_disabled):
        """Filing endpoints should return 403 when Nigeria compliance disabled."""
        resp = authenticated_client.get("/api/tax/filing/calendar")
        assert resp.status_code == 403


# =============================================================================
# GENERIC TAX CORE API TESTS (ALWAYS AVAILABLE)
# =============================================================================


class TestGenericTaxCoreAlwaysAvailable:
    """Test that generic tax-core endpoints are always available."""

    def test_tax_regions_available_when_disabled(self, authenticated_client, flags_disabled):
        """Tax regions should be accessible regardless of compliance flags."""
        resp = authenticated_client.get("/api/tax-core/regions")
        assert resp.status_code == 200

    def test_tax_categories_available_when_disabled(self, authenticated_client, flags_disabled, seeded_tax_core):
        """Tax categories should be accessible regardless of compliance flags."""
        resp = authenticated_client.get(f"/api/tax-core/regions/{seeded_tax_core['region_id']}/categories")
        assert resp.status_code == 200

    def test_tax_rates_available_when_disabled(self, authenticated_client, flags_disabled, seeded_tax_core):
        """Tax rates should be accessible regardless of compliance flags."""
        resp = authenticated_client.get(f"/api/tax-core/categories/{seeded_tax_core['category_id']}")
        assert resp.status_code == 200


# =============================================================================
# GENERIC PAYROLL CONFIG API TESTS (ALWAYS AVAILABLE)
# =============================================================================


class TestGenericPayrollConfigAlwaysAvailable:
    """Test that generic payroll-config endpoints are always available."""

    def test_payroll_regions_available(self, authenticated_client, flags_disabled):
        """Payroll regions should be accessible regardless of compliance flags."""
        resp = authenticated_client.get("/api/payroll-config/regions")
        assert resp.status_code == 200

    def test_deduction_rules_available(self, authenticated_client, flags_disabled, seeded_payroll_config):
        """Deduction rules should be accessible regardless of compliance flags."""
        resp = authenticated_client.get(f"/api/payroll-config/regions/{seeded_payroll_config['region_id']}/rules")
        assert resp.status_code == 200


# =============================================================================
# FEATURE FLAG STATE TESTS
# =============================================================================


class TestFeatureFlagState:
    """Test feature flag state management."""

    def test_flags_default_to_disabled(self):
        """Compliance flags should default to disabled."""
        # Create fresh instance without env vars
        fresh_flags = FeatureFlags()
        assert fresh_flags.NIGERIA_COMPLIANCE_ENABLED is False
        assert fresh_flags.STATUTORY_CALCULATIONS_ENABLED is False

    def test_is_feature_enabled_function(self):
        """Test is_feature_enabled helper function."""
        from app.feature_flags import is_feature_enabled

        with patch.object(feature_flags, 'NIGERIA_COMPLIANCE_ENABLED', True):
            assert is_feature_enabled('NIGERIA_COMPLIANCE_ENABLED') is True

        with patch.object(feature_flags, 'NIGERIA_COMPLIANCE_ENABLED', False):
            assert is_feature_enabled('NIGERIA_COMPLIANCE_ENABLED') is False

    def test_unknown_flag_returns_false(self):
        """Unknown flag names should return False."""
        from app.feature_flags import is_feature_enabled

        assert is_feature_enabled('NONEXISTENT_FLAG') is False


# =============================================================================
# ENTITLEMENTS ENDPOINT TESTS
# =============================================================================


class TestEntitlementsEndpoint:
    """Test the /api/entitlements endpoint."""

    def test_entitlements_returns_flag_state(self, authenticated_client):
        """Entitlements endpoint should return current flag state."""
        resp = authenticated_client.get("/api/entitlements")

        # Should return 200 with entitlement data
        assert resp.status_code == 200
        data = resp.json()

        # Should include compliance flags
        assert "feature_flags" in data
        assert "NIGERIA_COMPLIANCE_ENABLED" in data["feature_flags"]

    def test_entitlements_reflects_enabled_state(self, authenticated_client, flags_enabled):
        """Entitlements should reflect when flags are enabled."""
        resp = authenticated_client.get("/api/entitlements")

        assert resp.status_code == 200
        data = resp.json()

        assert data["feature_flags"]["NIGERIA_COMPLIANCE_ENABLED"] is True


# =============================================================================
# PAYROLL TAX INTEGRATION GATING TESTS
# =============================================================================


class TestPayrollTaxIntegrationGating:
    """Test that payroll-tax integration endpoints are gated."""

    def test_payroll_tax_integration_gated(self, authenticated_client, flags_disabled):
        """Payroll-tax integration should be gated when Nigeria compliance disabled."""
        # The payroll_integration router should be gated
        resp = authenticated_client.get("/api/tax/payroll-tax/rates")
        assert resp.status_code == 403


# =============================================================================
# COMBINED FEATURE FLAG TESTS
# =============================================================================


class TestCombinedFeatureFlags:
    """Test behavior with different flag combinations."""

    def test_nigeria_enabled_statutory_disabled(self, authenticated_client):
        """Test with Nigeria enabled but statutory disabled."""
        with patch.object(feature_flags, 'NIGERIA_COMPLIANCE_ENABLED', True), \
             patch.object(feature_flags, 'STATUTORY_CALCULATIONS_ENABLED', False):
            # Nigeria tax endpoints should work
            resp = authenticated_client.get("/api/tax/vat/transactions")
            # Should not be gated when enabled
            assert resp.status_code in [200, 404]

    def test_both_enabled(self, authenticated_client, flags_enabled):
        """Test with both flags enabled."""
        # All Nigeria-specific endpoints should be accessible
        endpoints = [
            "/api/tax/vat/transactions",
            "/api/tax/wht/transactions",
            "/api/tax/paye/calculations",
            "/api/tax/filing/calendar",
        ]

        for endpoint in endpoints:
            resp = authenticated_client.get(endpoint)
            # Should not be gated when enabled (200 or 404 for empty data)
            assert resp.status_code in [200, 404], f"{endpoint} returned unexpected status {resp.status_code}"


# =============================================================================
# SUCCESS PATH TESTS (WITH FLAGS ENABLED)
# =============================================================================


class TestTaxEndpointsSuccessPath:
    """Verify tax endpoints work correctly when flags are enabled."""

    def test_vat_transactions_returns_200_when_enabled(
        self, authenticated_client, flags_enabled
    ):
        """VAT transactions should return 200 (not 500) when enabled."""
        resp = authenticated_client.get("/api/tax/vat/transactions")
        # Should be 200 (list) or 404 (no data), never 403 or 500
        assert resp.status_code in [200, 404], \
            f"Expected 200/404, got {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (dict, list))

    def test_wht_transactions_returns_200_when_enabled(
        self, authenticated_client, flags_enabled
    ):
        """WHT transactions should return 200 when enabled."""
        resp = authenticated_client.get("/api/tax/wht/transactions")
        assert resp.status_code in [200, 404], \
            f"Expected 200/404, got {resp.status_code}: {resp.text}"

    def test_paye_calculations_returns_200_when_enabled(
        self, authenticated_client, flags_enabled
    ):
        """PAYE calculations should return 200 when enabled."""
        resp = authenticated_client.get("/api/tax/paye/calculations")
        assert resp.status_code in [200, 404], \
            f"Expected 200/404, got {resp.status_code}: {resp.text}"

    def test_filing_calendar_returns_200_when_enabled(
        self, authenticated_client, flags_enabled
    ):
        """Filing calendar should return 200 when enabled."""
        resp = authenticated_client.get("/api/tax/filing/calendar")
        assert resp.status_code in [200, 404], \
            f"Expected 200/404, got {resp.status_code}: {resp.text}"

    def test_tax_core_create_region_success(self, authenticated_client, flags_enabled):
        """Creating a tax region should succeed when enabled."""
        resp = authenticated_client.post("/api/tax-core/regions", json={
            "code": "TS",
            "name": "Test Success Region",
            "currency": "USD",
            "default_sales_tax_rate": 0.05,
            "default_withholding_rate": 0.02,
            "filing_deadline_day": 15,
        })
        # Should be 200/201 or 409 (conflict if exists)
        assert resp.status_code in [200, 201, 409], \
            f"Expected 200/201/409, got {resp.status_code}: {resp.text}"


class TestGatingReturns403Not500:
    """Verify gated endpoints return 403, never 500."""

    def test_vat_returns_403_not_500_when_disabled(
        self, authenticated_client, flags_disabled
    ):
        """VAT endpoint should return 403, not 500."""
        resp = authenticated_client.get("/api/tax/vat/transactions")
        assert resp.status_code == 403, \
            f"Expected 403, got {resp.status_code} - gating may be broken"
        # Verify error message is meaningful
        detail = resp.json().get("detail", "")
        assert len(detail) > 10, "Error message should be descriptive"

    def test_wht_returns_403_not_500_when_disabled(
        self, authenticated_client, flags_disabled
    ):
        """WHT endpoint should return 403, not 500."""
        resp = authenticated_client.get("/api/tax/wht/transactions")
        assert resp.status_code == 403, \
            f"Expected 403, got {resp.status_code}"

    def test_paye_returns_403_not_500_when_disabled(
        self, authenticated_client, flags_disabled
    ):
        """PAYE endpoint should return 403, not 500."""
        resp = authenticated_client.get("/api/tax/paye/calculations")
        assert resp.status_code == 403, \
            f"Expected 403, got {resp.status_code}"

    def test_filing_returns_403_not_500_when_disabled(
        self, authenticated_client, flags_disabled
    ):
        """Filing endpoint should return 403, not 500."""
        resp = authenticated_client.get("/api/tax/filing/calendar")
        assert resp.status_code == 403, \
            f"Expected 403, got {resp.status_code}"
