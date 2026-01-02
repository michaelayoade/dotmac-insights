"""RADIUS Settings API Integration Tests.

Tests RADIUS configuration API endpoints:
- Settings CRUD (GET, PUT, seed defaults)
- Attribute mapping CRUD
- NAS config CRUD (with unique constraint validation)
- Dictionary entry CRUD
- RBAC (subscriptions:read vs subscriptions:admin)
- Error handling (404, 400, 422)
- Secret masking in responses
"""
import pytest
from datetime import datetime

from app.models.radius_settings import (
    RADIUSSettings,
    RADIUSAttributeMapping,
    NASConfig,
    RADIUSDictionary,
    NASType,
    AuthenticationType,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_radius_settings(integration_db):
    """Create test RADIUS settings."""
    settings = RADIUSSettings(
        company=None,
        radius_host="test-radius.example.com",
        radius_auth_port=1812,
        radius_acct_port=1813,
        radius_secret="test_secret_123",
        coa_enabled=True,
        coa_port=3799,
        coa_secret="coa_secret",
    )
    integration_db.add(settings)
    integration_db.commit()
    integration_db.refresh(settings)
    return settings


@pytest.fixture
def sample_attribute_mapping(integration_db):
    """Create test attribute mapping."""
    mapping = RADIUSAttributeMapping(
        company=None,
        nas_type=NASType.MIKROTIK,
        attribute_name="rate_limit",
        radius_attribute="Mikrotik-Rate-Limit",
        radius_vendor_id=14988,
        value_format="{download}M/{upload}M",
        is_active=True,
    )
    integration_db.add(mapping)
    integration_db.commit()
    integration_db.refresh(mapping)
    return mapping


@pytest.fixture
def sample_router(integration_db):
    """Create a test router for NAS config."""
    from app.models.router import Router

    router = Router(
        name="Test Router",
        ip_address="192.168.1.1",
        router_type="mikrotik",
        is_active=True,
    )
    integration_db.add(router)
    integration_db.commit()
    integration_db.refresh(router)
    return router


@pytest.fixture
def sample_nas_config(integration_db, sample_router):
    """Create test NAS config."""
    config = NASConfig(
        router_id=sample_router.id,
        nas_identifier="test-nas-001",
        radius_secret="nas_secret_123",
        nas_type=NASType.MIKROTIK,
        coa_enabled=True,
        coa_port=3799,
        is_active=True,
    )
    integration_db.add(config)
    integration_db.commit()
    integration_db.refresh(config)
    return config


@pytest.fixture
def sample_dictionary_entry(integration_db):
    """Create test dictionary entry."""
    entry = RADIUSDictionary(
        vendor_name="MikroTik",
        vendor_id=14988,
        attribute_name="Mikrotik-Rate-Limit",
        attribute_type=8,
        attribute_value_type="string",
        description="Rate limit attribute for MikroTik",
        is_active=True,
    )
    integration_db.add(entry)
    integration_db.commit()
    integration_db.refresh(entry)
    return entry


@pytest.fixture
def create_additional_router(integration_db):
    """Factory to create additional routers for duplicate tests."""
    from app.models.router import Router

    def _create(name: str = "Additional Router"):
        router = Router(
            name=name,
            ip_address=f"192.168.{len(integration_db.query(Router).all())}.1",
            router_type="mikrotik",
            is_active=True,
        )
        integration_db.add(router)
        integration_db.commit()
        integration_db.refresh(router)
        return router

    return _create


# =============================================================================
# MAIN SETTINGS TESTS
# =============================================================================


class TestGetRADIUSSettings:
    """Tests for GET /api/subscriptions/radius"""

    def test_get_settings_returns_defaults(self, auth_client):
        """Should return default settings when none exist."""
        client = auth_client(["subscriptions:read"])
        resp = client.get("/api/subscriptions/radius")

        assert resp.status_code == 200
        data = resp.json()
        assert "server" in data
        assert "authentication" in data
        assert "accounting" in data
        assert data["server"]["host"] == "localhost"
        assert data["server"]["auth_port"] == 1812

    def test_get_settings_masks_secrets(self, auth_client, sample_radius_settings):
        """Should mask secret fields in response."""
        client = auth_client(["subscriptions:read"])
        resp = client.get("/api/subscriptions/radius")

        assert resp.status_code == 200
        data = resp.json()
        assert data["server"]["secret"] == "***"

    def test_get_settings_without_auth_fails(self, unauthenticated_client):
        """Should return 401 without authentication."""
        resp = unauthenticated_client.get("/api/subscriptions/radius")
        assert resp.status_code == 401


class TestUpdateRADIUSSettings:
    """Tests for PUT /api/subscriptions/radius"""

    def test_update_server_settings(self, auth_client, integration_db):
        """Should update server settings."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "server": {
                "host": "new-radius.example.com",
                "auth_port": 1815,
                "timeout_seconds": 10,
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify settings were updated
        resp2 = client.get("/api/subscriptions/radius")
        data2 = resp2.json()
        assert data2["server"]["host"] == "new-radius.example.com"
        assert data2["server"]["auth_port"] == 1815

    def test_update_requires_admin_scope(self, auth_client, sample_radius_settings):
        """Should require subscriptions:admin scope for updates."""
        client = auth_client(["subscriptions:read"])
        payload = {"server": {"host": "should-fail.com"}}

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 403

    def test_update_authentication_with_valid_enum(self, auth_client):
        """Should accept valid authentication type enum."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "authentication": {
                "default_auth_type": "CHAP",
                "mac_auth_enabled": True,
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 200

    def test_update_authentication_with_invalid_enum_fails(self, auth_client):
        """Should reject invalid authentication type enum."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "authentication": {
                "default_auth_type": "INVALID_TYPE",
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 400
        assert "Invalid default_auth_type" in resp.json()["detail"]

    def test_update_coa_settings(self, auth_client):
        """Should update CoA settings."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "coa": {
                "enabled": False,
                "port": 3800,
                "timeout_seconds": 15,
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 200

    def test_update_bandwidth_with_valid_unit(self, auth_client):
        """Should accept valid bandwidth unit."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "bandwidth": {
                "unit": "GBPS",
                "burst_enabled": True,
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 200

    def test_update_bandwidth_with_invalid_unit_fails(self, auth_client):
        """Should reject invalid bandwidth unit."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "bandwidth": {
                "unit": "TBPS",  # Invalid
            }
        }

        resp = client.put("/api/subscriptions/radius", json=payload)

        assert resp.status_code == 400
        assert "Invalid unit" in resp.json()["detail"]


class TestSeedDefaults:
    """Tests for POST /api/subscriptions/radius/seed-defaults"""

    def test_seed_defaults_creates_settings(self, auth_client, integration_db):
        """Should create default settings if not exist."""
        client = auth_client(["subscriptions:admin"])

        resp = client.post("/api/subscriptions/radius/seed-defaults")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data

    def test_seed_defaults_idempotent(self, auth_client, sample_radius_settings):
        """Should return existing settings if they already exist."""
        client = auth_client(["subscriptions:admin"])

        resp = client.post("/api/subscriptions/radius/seed-defaults")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_radius_settings.id

    def test_seed_defaults_requires_admin(self, auth_client):
        """Should require admin scope."""
        client = auth_client(["subscriptions:read"])

        resp = client.post("/api/subscriptions/radius/seed-defaults")

        assert resp.status_code == 403


# =============================================================================
# SECTION-SPECIFIC ENDPOINT TESTS
# =============================================================================


class TestSectionEndpoints:
    """Tests for section-specific GET endpoints."""

    def test_get_server_config(self, auth_client, sample_radius_settings):
        """Should return server config section."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/server")

        assert resp.status_code == 200
        data = resp.json()
        assert "host" in data
        assert "auth_port" in data
        # Server section should not include secret
        assert "secret" not in data or data.get("secret") is None

    def test_get_authentication_config(self, auth_client, sample_radius_settings):
        """Should return authentication config section."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/authentication")

        assert resp.status_code == 200
        data = resp.json()
        assert "default_auth_type" in data
        assert "mac_auth_enabled" in data

    def test_get_accounting_config(self, auth_client, sample_radius_settings):
        """Should return accounting config section."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/accounting")

        assert resp.status_code == 200
        data = resp.json()
        assert "method" in data
        assert "interim_update_interval_seconds" in data

    def test_get_coa_config(self, auth_client, sample_radius_settings):
        """Should return CoA config section."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/coa")

        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "port" in data

    def test_get_bandwidth_config(self, auth_client, sample_radius_settings):
        """Should return bandwidth config section."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/bandwidth")

        assert resp.status_code == 200
        data = resp.json()
        assert "unit" in data
        assert "burst_enabled" in data


# =============================================================================
# ATTRIBUTE MAPPING TESTS
# =============================================================================


class TestAttributeMappingList:
    """Tests for GET /api/subscriptions/radius/attribute-mappings"""

    def test_list_mappings(self, auth_client, sample_attribute_mapping):
        """Should list attribute mappings."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/attribute-mappings")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1

    def test_list_mappings_filter_by_nas_type(self, auth_client, sample_attribute_mapping):
        """Should filter mappings by NAS type."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/attribute-mappings?nas_type=MIKROTIK")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["nas_type"] == "MIKROTIK"

    def test_list_mappings_pagination(self, auth_client, sample_attribute_mapping, integration_db):
        """Should paginate results."""
        # Create additional mappings
        for i in range(3):
            mapping = RADIUSAttributeMapping(
                company=None,
                nas_type=NASType.MIKROTIK,
                attribute_name=f"attr_{i}",
                radius_attribute=f"Test-Attr-{i}",
                is_active=True,
            )
            integration_db.add(mapping)
        integration_db.commit()

        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/attribute-mappings?page=1&per_page=2")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["per_page"] == 2


class TestAttributeMappingGet:
    """Tests for GET /api/subscriptions/radius/attribute-mappings/{id}"""

    def test_get_mapping_by_id(self, auth_client, sample_attribute_mapping):
        """Should get mapping by ID."""
        client = auth_client(["subscriptions:read"])

        resp = client.get(f"/api/subscriptions/radius/attribute-mappings/{sample_attribute_mapping.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_attribute_mapping.id
        assert data["attribute_name"] == "rate_limit"

    def test_get_mapping_not_found(self, auth_client):
        """Should return 404 for non-existent mapping."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/attribute-mappings/99999")

        assert resp.status_code == 404


class TestAttributeMappingCreate:
    """Tests for POST /api/subscriptions/radius/attribute-mappings"""

    def test_create_mapping(self, auth_client, integration_db):
        """Should create new attribute mapping."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_type": "CISCO",
            "attribute_name": "test_attribute",
            "radius_attribute": "Cisco-Test-Attr",
            "radius_vendor_id": 9,
        }

        resp = client.post("/api/subscriptions/radius/attribute-mappings", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data

    def test_create_mapping_invalid_nas_type(self, auth_client):
        """Should reject invalid NAS type."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_type": "INVALID",
            "attribute_name": "test",
            "radius_attribute": "Test-Attr",
        }

        resp = client.post("/api/subscriptions/radius/attribute-mappings", json=payload)

        assert resp.status_code == 400
        assert "Invalid nas_type" in resp.json()["detail"]

    def test_create_mapping_requires_admin(self, auth_client):
        """Should require admin scope."""
        client = auth_client(["subscriptions:read"])
        payload = {
            "nas_type": "MIKROTIK",
            "attribute_name": "test",
            "radius_attribute": "Test-Attr",
        }

        resp = client.post("/api/subscriptions/radius/attribute-mappings", json=payload)

        assert resp.status_code == 403


class TestAttributeMappingUpdate:
    """Tests for PUT /api/subscriptions/radius/attribute-mappings/{id}"""

    def test_update_mapping(self, auth_client, sample_attribute_mapping):
        """Should update existing mapping."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_type": "CISCO",
            "attribute_name": "updated_attr",
            "radius_attribute": "Cisco-Updated",
        }

        resp = client.put(
            f"/api/subscriptions/radius/attribute-mappings/{sample_attribute_mapping.id}",
            json=payload
        )

        assert resp.status_code == 200

    def test_update_mapping_not_found(self, auth_client):
        """Should return 404 for non-existent mapping."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_type": "MIKROTIK",
            "attribute_name": "test",
            "radius_attribute": "Test-Attr",
        }

        resp = client.put("/api/subscriptions/radius/attribute-mappings/99999", json=payload)

        assert resp.status_code == 404


class TestAttributeMappingDelete:
    """Tests for DELETE /api/subscriptions/radius/attribute-mappings/{id}"""

    def test_delete_mapping(self, auth_client, sample_attribute_mapping, integration_db):
        """Should soft-delete mapping."""
        client = auth_client(["subscriptions:admin"])

        resp = client.delete(f"/api/subscriptions/radius/attribute-mappings/{sample_attribute_mapping.id}")

        assert resp.status_code == 200

        # Verify soft-delete
        integration_db.refresh(sample_attribute_mapping)
        assert sample_attribute_mapping.is_active is False

    def test_delete_mapping_not_found(self, auth_client):
        """Should return 404 for non-existent mapping."""
        client = auth_client(["subscriptions:admin"])

        resp = client.delete("/api/subscriptions/radius/attribute-mappings/99999")

        assert resp.status_code == 404


# =============================================================================
# NAS CONFIG TESTS
# =============================================================================


class TestNASConfigList:
    """Tests for GET /api/subscriptions/radius/nas-configs"""

    def test_list_nas_configs(self, auth_client, sample_nas_config):
        """Should list NAS configs."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/nas-configs")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_list_nas_configs_filter_by_router(self, auth_client, sample_nas_config, sample_router):
        """Should filter configs by router_id."""
        client = auth_client(["subscriptions:read"])

        resp = client.get(f"/api/subscriptions/radius/nas-configs?router_id={sample_router.id}")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["router_id"] == sample_router.id


class TestNASConfigGet:
    """Tests for GET /api/subscriptions/radius/nas-configs/{id}"""

    def test_get_nas_config(self, auth_client, sample_nas_config):
        """Should get NAS config by ID."""
        client = auth_client(["subscriptions:read"])

        resp = client.get(f"/api/subscriptions/radius/nas-configs/{sample_nas_config.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_nas_config.id
        assert data["nas_identifier"] == "test-nas-001"

    def test_get_nas_config_not_found(self, auth_client):
        """Should return 404 for non-existent config."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/nas-configs/99999")

        assert resp.status_code == 404


class TestNASConfigCreate:
    """Tests for POST /api/subscriptions/radius/nas-configs"""

    def test_create_nas_config(self, auth_client, create_additional_router):
        """Should create new NAS config."""
        router = create_additional_router("New Router")

        client = auth_client(["subscriptions:admin"])
        payload = {
            "router_id": router.id,
            "nas_identifier": "new-nas",
            "nas_type": "MIKROTIK",
            "coa_enabled": True,
            "coa_port": 3799,
        }

        resp = client.post("/api/subscriptions/radius/nas-configs", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data

    def test_create_nas_config_duplicate_router_fails(self, auth_client, sample_nas_config, sample_router):
        """Should reject duplicate config for same router."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "router_id": sample_router.id,  # Already has config
            "nas_identifier": "duplicate-nas",
            "nas_type": "MIKROTIK",
        }

        resp = client.post("/api/subscriptions/radius/nas-configs", json=payload)

        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_create_nas_config_invalid_nas_type(self, auth_client, create_additional_router):
        """Should reject invalid NAS type."""
        router = create_additional_router("Router for Invalid Type")

        client = auth_client(["subscriptions:admin"])
        payload = {
            "router_id": router.id,
            "nas_type": "INVALID_TYPE",
        }

        resp = client.post("/api/subscriptions/radius/nas-configs", json=payload)

        assert resp.status_code == 400
        assert "Invalid nas_type" in resp.json()["detail"]

    def test_create_nas_config_requires_admin(self, auth_client, create_additional_router):
        """Should require admin scope."""
        router = create_additional_router("Router for Auth Test")

        client = auth_client(["subscriptions:read"])
        payload = {
            "router_id": router.id,
            "nas_type": "MIKROTIK",
        }

        resp = client.post("/api/subscriptions/radius/nas-configs", json=payload)

        assert resp.status_code == 403


class TestNASConfigUpdate:
    """Tests for PUT /api/subscriptions/radius/nas-configs/{id}"""

    def test_update_nas_config(self, auth_client, sample_nas_config):
        """Should update NAS config (except router_id)."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_identifier": "updated-nas",
            "nas_type": "CISCO",
            "coa_enabled": False,
        }

        resp = client.put(
            f"/api/subscriptions/radius/nas-configs/{sample_nas_config.id}",
            json=payload
        )

        assert resp.status_code == 200

    def test_update_nas_config_not_found(self, auth_client):
        """Should return 404 for non-existent config."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_identifier": "test",
            "nas_type": "MIKROTIK",
        }

        resp = client.put("/api/subscriptions/radius/nas-configs/99999", json=payload)

        assert resp.status_code == 404


class TestNASConfigDelete:
    """Tests for DELETE /api/subscriptions/radius/nas-configs/{id}"""

    def test_delete_nas_config(self, auth_client, sample_nas_config, integration_db):
        """Should soft-delete NAS config."""
        client = auth_client(["subscriptions:admin"])

        resp = client.delete(f"/api/subscriptions/radius/nas-configs/{sample_nas_config.id}")

        assert resp.status_code == 200

        # Verify soft-delete
        integration_db.refresh(sample_nas_config)
        assert sample_nas_config.is_active is False


# =============================================================================
# DICTIONARY TESTS
# =============================================================================


class TestDictionaryList:
    """Tests for GET /api/subscriptions/radius/dictionary"""

    def test_list_dictionary_entries(self, auth_client, sample_dictionary_entry):
        """Should list dictionary entries."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/dictionary")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_list_dictionary_filter_by_vendor(self, auth_client, sample_dictionary_entry):
        """Should filter by vendor."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/dictionary?vendor_name=MikroTik")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_name"] == "MikroTik"


class TestDictionaryGet:
    """Tests for GET /api/subscriptions/radius/dictionary/{id}"""

    def test_get_dictionary_entry(self, auth_client, sample_dictionary_entry):
        """Should get dictionary entry by ID."""
        client = auth_client(["subscriptions:read"])

        resp = client.get(f"/api/subscriptions/radius/dictionary/{sample_dictionary_entry.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_dictionary_entry.id
        assert data["vendor_name"] == "MikroTik"

    def test_get_dictionary_entry_not_found(self, auth_client):
        """Should return 404 for non-existent entry."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/dictionary/99999")

        assert resp.status_code == 404


class TestDictionaryVendors:
    """Tests for GET /api/subscriptions/radius/dictionary/vendors"""

    def test_list_vendors(self, auth_client, sample_dictionary_entry):
        """Should list vendors with attribute counts."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/dictionary/vendors")

        assert resp.status_code == 200
        data = resp.json()
        assert "vendors" in data
        assert len(data["vendors"]) >= 1

        # Check vendor structure
        vendor = data["vendors"][0]
        assert "vendor_name" in vendor
        assert "vendor_id" in vendor
        assert "attribute_count" in vendor


class TestDictionaryCreate:
    """Tests for POST /api/subscriptions/radius/dictionary"""

    def test_create_dictionary_entry(self, auth_client):
        """Should create new dictionary entry."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "vendor_name": "Cisco",
            "vendor_id": 9,
            "attribute_name": "Cisco-Test-Attr",
            "attribute_type": 100,
            "attribute_value_type": "string",
            "description": "Test attribute",
        }

        resp = client.post("/api/subscriptions/radius/dictionary", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data

    def test_create_dictionary_requires_admin(self, auth_client):
        """Should require admin scope."""
        client = auth_client(["subscriptions:read"])
        payload = {
            "vendor_name": "Test",
            "vendor_id": 1,
            "attribute_name": "Test-Attr",
            "attribute_type": 1,
        }

        resp = client.post("/api/subscriptions/radius/dictionary", json=payload)

        assert resp.status_code == 403


class TestDictionaryUpdate:
    """Tests for PUT /api/subscriptions/radius/dictionary/{id}"""

    def test_update_dictionary_entry(self, auth_client, sample_dictionary_entry):
        """Should update dictionary entry."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "vendor_name": "MikroTik",
            "vendor_id": 14988,
            "attribute_name": "Mikrotik-Updated-Attr",
            "attribute_type": 9,
            "description": "Updated description",
        }

        resp = client.put(
            f"/api/subscriptions/radius/dictionary/{sample_dictionary_entry.id}",
            json=payload
        )

        assert resp.status_code == 200

    def test_update_dictionary_not_found(self, auth_client):
        """Should return 404 for non-existent entry."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "vendor_name": "Test",
            "vendor_id": 1,
            "attribute_name": "Test-Attr",
            "attribute_type": 1,
        }

        resp = client.put("/api/subscriptions/radius/dictionary/99999", json=payload)

        assert resp.status_code == 404


class TestDictionaryDelete:
    """Tests for DELETE /api/subscriptions/radius/dictionary/{id}"""

    def test_delete_dictionary_entry(self, auth_client, sample_dictionary_entry, integration_db):
        """Should soft-delete dictionary entry."""
        client = auth_client(["subscriptions:admin"])

        resp = client.delete(f"/api/subscriptions/radius/dictionary/{sample_dictionary_entry.id}")

        assert resp.status_code == 200

        # Verify soft-delete
        integration_db.refresh(sample_dictionary_entry)
        assert sample_dictionary_entry.is_active is False


# =============================================================================
# DIAGNOSTICS TESTS
# =============================================================================


class TestDiagnostics:
    """Tests for diagnostic endpoints."""

    def test_test_connection(self, auth_client, sample_radius_settings):
        """Should test RADIUS connection."""
        client = auth_client(["subscriptions:admin"])

        resp = client.post("/api/subscriptions/radius/test-connection", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "server" in data
        assert "port" in data

    def test_test_connection_with_custom_params(self, auth_client):
        """Should test connection with custom parameters."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "host": "custom-radius.example.com",
            "port": 1818,
        }

        resp = client.post("/api/subscriptions/radius/test-connection", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "custom-radius.example.com"
        assert data["port"] == 1818

    def test_test_coa(self, auth_client):
        """Should test CoA connectivity."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "nas_ip": "192.168.1.1",
            "port": 3799,
            "action": "DISCONNECT",
        }

        resp = client.post("/api/subscriptions/radius/test-coa", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert data["nas_ip"] == "192.168.1.1"

    def test_get_health_status(self, auth_client, sample_radius_settings):
        """Should get health status."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "primary_server_up" in data
        assert "database_connected" in data


# =============================================================================
# REFERENCE DATA TESTS
# =============================================================================


class TestReferenceData:
    """Tests for reference data endpoints."""

    def test_get_auth_types(self, auth_client):
        """Should list authentication types."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/auth-types")

        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data
        assert len(data["types"]) >= 1

        # Check structure
        auth_type = data["types"][0]
        assert "code" in auth_type
        assert "label" in auth_type
        assert "description" in auth_type

    def test_get_nas_types(self, auth_client):
        """Should list NAS types."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/nas-types")

        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data

        # Should include MikroTik
        codes = [t["code"] for t in data["types"]]
        assert "MIKROTIK" in codes

    def test_get_session_limit_actions(self, auth_client):
        """Should list session limit actions."""
        client = auth_client(["subscriptions:read"])

        resp = client.get("/api/subscriptions/radius/session-limit-actions")

        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data

        codes = [a["code"] for a in data["actions"]]
        assert "REJECT" in codes
        assert "DISCONNECT_OLDEST" in codes


# =============================================================================
# RBAC TESTS
# =============================================================================


class TestRADIUSSettingsRBAC:
    """Tests for role-based access control."""

    def test_read_scope_allows_get(self, auth_client, sample_radius_settings):
        """Read scope should allow GET operations."""
        client = auth_client(["subscriptions:read"])

        # Main settings
        resp = client.get("/api/subscriptions/radius")
        assert resp.status_code == 200

        # Attribute mappings
        resp = client.get("/api/subscriptions/radius/attribute-mappings")
        assert resp.status_code == 200

        # NAS configs
        resp = client.get("/api/subscriptions/radius/nas-configs")
        assert resp.status_code == 200

        # Dictionary
        resp = client.get("/api/subscriptions/radius/dictionary")
        assert resp.status_code == 200

    def test_read_scope_denies_write(self, auth_client, sample_radius_settings):
        """Read scope should deny write operations."""
        client = auth_client(["subscriptions:read"])

        # Update settings
        resp = client.put("/api/subscriptions/radius", json={})
        assert resp.status_code == 403

        # Seed defaults
        resp = client.post("/api/subscriptions/radius/seed-defaults")
        assert resp.status_code == 403

        # Test connection
        resp = client.post("/api/subscriptions/radius/test-connection", json={})
        assert resp.status_code == 403

    def test_admin_scope_allows_write(self, auth_client, sample_radius_settings):
        """Admin scope should allow write operations."""
        client = auth_client(["subscriptions:admin"])

        # Update settings
        resp = client.put("/api/subscriptions/radius", json={"server": {"timeout_seconds": 10}})
        assert resp.status_code == 200

        # Test connection
        resp = client.post("/api/subscriptions/radius/test-connection", json={})
        assert resp.status_code == 200

    def test_superuser_has_full_access(self, superuser_client, sample_radius_settings):
        """Superuser should have full access."""
        # Read
        resp = superuser_client.get("/api/subscriptions/radius")
        assert resp.status_code == 200

        # Write
        resp = superuser_client.put("/api/subscriptions/radius", json={})
        assert resp.status_code == 200

        # Admin actions
        resp = superuser_client.post("/api/subscriptions/radius/test-connection", json={})
        assert resp.status_code == 200


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_update_succeeds(self, auth_client):
        """Should handle empty update payload."""
        client = auth_client(["subscriptions:admin"])

        resp = client.put("/api/subscriptions/radius", json={})

        assert resp.status_code == 200

    def test_pagination_boundary(self, auth_client, sample_attribute_mapping):
        """Should handle pagination edge cases."""
        client = auth_client(["subscriptions:read"])

        # Page 0 should behave same as page 1
        resp = client.get("/api/subscriptions/radius/attribute-mappings?page=0")
        # FastAPI validation will catch this
        assert resp.status_code in [200, 422]

        # Very large page number
        resp = client.get("/api/subscriptions/radius/attribute-mappings?page=999999")
        assert resp.status_code == 200
        data = resp.json()
        # Should return empty items for non-existent page
        assert "items" in data

    def test_special_characters_in_nas_identifier(self, auth_client, create_additional_router):
        """Should handle special characters in identifiers."""
        router = create_additional_router("Special Chars Router")

        client = auth_client(["subscriptions:admin"])
        payload = {
            "router_id": router.id,
            "nas_identifier": "nas-001_test.example.com",
            "nas_type": "MIKROTIK",
        }

        resp = client.post("/api/subscriptions/radius/nas-configs", json=payload)

        assert resp.status_code == 200

    def test_long_description_in_dictionary(self, auth_client):
        """Should handle long descriptions."""
        client = auth_client(["subscriptions:admin"])
        payload = {
            "vendor_name": "Test",
            "vendor_id": 99999,
            "attribute_name": "Test-Long-Desc",
            "attribute_type": 1,
            "description": "A" * 1000,  # Long description
        }

        resp = client.post("/api/subscriptions/radius/dictionary", json=payload)

        assert resp.status_code == 200
