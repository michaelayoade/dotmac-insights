"""Unit tests for RADIUSSettingsService.

Tests RADIUS configuration management:
- Settings CRUD (get, update, seed defaults)
- Attribute mapping CRUD
- NAS config CRUD (with unique constraint validation)
- Dictionary entry CRUD
- Enum validation
- Error handling
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.services.subscriptions.radius_settings import RADIUSSettingsService, _safe_enum
from app.services.subscriptions.radius_settings_types import (
    RADIUSSettingsData,
    RADIUSSettingsUpdate,
    AttributeMappingData,
    AttributeMappingFilters,
    NASConfigData,
    NASConfigFilters,
    DictionaryEntryData,
    DictionaryFilters,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams
from app.models.radius_settings import (
    RADIUSSettings,
    RADIUSAttributeMapping,
    NASConfig,
    RADIUSDictionary,
    NASType,
    AuthenticationType,
    PasswordEncryption,
    AccountingMethod,
    SessionLimitAction,
    BandwidthUnit,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

class TestSafeEnum:
    """Test _safe_enum helper function."""

    def test_valid_enum_value(self):
        """Should return enum for valid value."""
        result = _safe_enum(NASType, "MIKROTIK", "nas_type")
        assert result == NASType.MIKROTIK

    def test_invalid_enum_value_raises(self):
        """Should raise ValidationError for invalid value."""
        with pytest.raises(ValidationError) as exc:
            _safe_enum(NASType, "INVALID_TYPE", "nas_type")
        assert "Invalid nas_type" in str(exc.value)
        assert "INVALID_TYPE" in str(exc.value)
        assert "MIKROTIK" in str(exc.value)  # Shows valid values

    def test_all_nas_types(self):
        """Should accept all valid NAS types."""
        for nas_type in NASType:
            result = _safe_enum(NASType, nas_type.value, "nas_type")
            assert result == nas_type

    def test_all_auth_types(self):
        """Should accept all valid auth types."""
        for auth_type in AuthenticationType:
            result = _safe_enum(AuthenticationType, auth_type.value, "auth_type")
            assert result == auth_type


# =============================================================================
# SERVICE FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value = MagicMock()
    db.get.return_value = None
    return db


@pytest.fixture
def mock_principal():
    """Create a mock principal."""
    principal = MagicMock()
    principal.id = 1
    principal.is_superuser = False
    return principal


@pytest.fixture
def service(mock_db, mock_principal):
    """Create a RADIUSSettingsService instance."""
    return RADIUSSettingsService(mock_db, mock_principal)


@pytest.fixture
def mock_radius_settings():
    """Create a mock RADIUSSettings model."""
    settings = MagicMock(spec=RADIUSSettings)
    settings.id = 1
    settings.company = None
    settings.radius_host = "radius.example.com"
    settings.radius_auth_port = 1812
    settings.radius_acct_port = 1813
    settings.radius_secret = "secret123"
    settings.radius_timeout_seconds = 5
    settings.radius_retries = 3
    settings.radius_dead_time_seconds = 120
    settings.failover_enabled = False
    settings.radius_secondary_host = None
    settings.radius_secondary_auth_port = 1812
    settings.radius_secondary_acct_port = 1813
    settings.radius_secondary_secret = None
    settings.default_auth_type = AuthenticationType.PAP
    settings.password_encryption = PasswordEncryption.CLEARTEXT
    settings.mac_auth_enabled = False
    settings.mac_auth_password = None
    settings.mac_format = "XX:XX:XX:XX:XX:XX"
    settings.default_realm = None
    settings.strip_realm = True
    settings.accounting_method = AccountingMethod.RADIUS
    settings.interim_update_interval_seconds = 300
    settings.acct_delay_time_enabled = True
    settings.track_sessions = True
    settings.session_timeout_minutes = 0
    settings.idle_timeout_minutes = 0
    settings.track_usage = True
    settings.aggregate_usage_daily = True
    settings.max_sessions_per_user = 1
    settings.session_limit_action = SessionLimitAction.REJECT
    settings.simultaneous_use_enabled = True
    settings.coa_enabled = True
    settings.coa_port = 3799
    settings.coa_secret = None
    settings.coa_timeout_seconds = 5
    settings.coa_retries = 3
    settings.bandwidth_unit = BandwidthUnit.MBPS
    settings.use_mikrotik_rate_limit = True
    settings.use_wispr_bandwidth = False
    settings.burst_enabled = False
    settings.burst_threshold_percent = 100
    settings.burst_time_seconds = 10
    settings.ip_pool_enabled = True
    settings.default_ip_pool = None
    settings.ipv6_enabled = False
    settings.default_ipv6_pool = None
    settings.static_ip_reply_attribute = "Framed-IP-Address"
    settings.static_ipv6_reply_attribute = "Framed-IPv6-Address"
    settings.default_nas_type = NASType.MIKROTIK
    settings.auto_add_nas = False
    settings.default_nas_secret = None
    settings.nas_require_secret = True
    settings.radius_db_enabled = True
    settings.radius_db_host = None
    settings.radius_db_port = 3306
    settings.radius_db_name = "radius"
    settings.radius_db_user = None
    settings.radius_db_password = None
    settings.radcheck_table = "radcheck"
    settings.radreply_table = "radreply"
    settings.radgroupcheck_table = "radgroupcheck"
    settings.radgroupreply_table = "radgroupreply"
    settings.radacct_table = "radacct"
    settings.nas_table = "nas"
    settings.log_auth_requests = True
    settings.log_acct_requests = True
    settings.log_failed_auth = True
    settings.debug_mode = False
    settings.log_retention_days = 90
    return settings


@pytest.fixture
def mock_attribute_mapping():
    """Create a mock RADIUSAttributeMapping model."""
    mapping = MagicMock(spec=RADIUSAttributeMapping)
    mapping.id = 1
    mapping.company = None
    mapping.nas_type = NASType.MIKROTIK
    mapping.attribute_name = "rate_limit"
    mapping.radius_attribute = "Mikrotik-Rate-Limit"
    mapping.radius_vendor_id = 14988
    mapping.radius_vendor_type = None
    mapping.value_format = "{download}M/{upload}M"
    mapping.is_active = True
    mapping.created_at = datetime.now()
    return mapping


@pytest.fixture
def mock_nas_config():
    """Create a mock NASConfig model."""
    config = MagicMock(spec=NASConfig)
    config.id = 1
    config.router_id = 100
    config.nas_identifier = "router-001"
    config.radius_secret = "nas_secret"
    config.nas_type = NASType.MIKROTIK
    config.coa_enabled = True
    config.coa_port = 3799
    config.coa_secret = None
    config.interim_interval = 300
    config.custom_attributes = {"test": "value"}
    config.is_active = True
    return config


@pytest.fixture
def mock_dictionary_entry():
    """Create a mock RADIUSDictionary model."""
    entry = MagicMock(spec=RADIUSDictionary)
    entry.id = 1
    entry.vendor_name = "MikroTik"
    entry.vendor_id = 14988
    entry.attribute_name = "Mikrotik-Rate-Limit"
    entry.attribute_type = 8
    entry.attribute_value_type = "string"
    entry.description = "Rate limit attribute"
    entry.is_active = True
    entry.created_at = datetime.now()
    return entry


# =============================================================================
# SETTINGS TESTS
# =============================================================================

class TestGetSettings:
    """Test get_settings method."""

    def test_get_global_settings(self, service, mock_db, mock_radius_settings):
        """Should return global settings when no company specified."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        result = service.get_settings()

        assert isinstance(result, RADIUSSettingsData)
        assert result.server.host == "radius.example.com"
        assert result.server.auth_port == 1812

    def test_get_company_settings_fallback_to_global(self, service, mock_db, mock_radius_settings):
        """Should fall back to global settings if company settings not found."""
        # First query (company) returns None, second (global) returns settings
        mock_query = MagicMock()
        mock_query.filter.return_value.first.side_effect = [None, mock_radius_settings]
        mock_db.query.return_value = mock_query

        result = service.get_settings(company="test-company")

        assert isinstance(result, RADIUSSettingsData)
        assert result.server.host == "radius.example.com"

    def test_get_settings_returns_defaults_when_none_exist(self, service, mock_db):
        """Should return default settings when no settings exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_settings()

        assert isinstance(result, RADIUSSettingsData)
        assert result.server.host == "localhost"
        assert result.server.auth_port == 1812


class TestUpdateSettings:
    """Test update_settings method."""

    def test_update_server_settings(self, service, mock_db, mock_radius_settings):
        """Should update server settings."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        updates = RADIUSSettingsUpdate(
            server={"host": "new-radius.example.com", "auth_port": 1815}
        )
        result = service.update_settings(updates)

        assert mock_radius_settings.radius_host == "new-radius.example.com"
        assert mock_radius_settings.radius_auth_port == 1815
        mock_db.flush.assert_called_once()

    def test_update_creates_settings_if_not_exist(self, service, mock_db):
        """Should create new settings if they don't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        updates = RADIUSSettingsUpdate(server={"host": "new-server.com"})
        service.update_settings(updates)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_update_authentication_settings(self, service, mock_db, mock_radius_settings):
        """Should update authentication settings with valid enum."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        updates = RADIUSSettingsUpdate(
            authentication={"default_auth_type": "CHAP", "mac_auth_enabled": True}
        )
        result = service.update_settings(updates)

        assert mock_radius_settings.default_auth_type == AuthenticationType.CHAP
        assert mock_radius_settings.mac_auth_enabled is True

    def test_update_with_invalid_auth_type_raises(self, service, mock_db, mock_radius_settings):
        """Should raise ValidationError for invalid auth type."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        updates = RADIUSSettingsUpdate(
            authentication={"default_auth_type": "INVALID"}
        )

        with pytest.raises(ValidationError) as exc:
            service.update_settings(updates)
        assert "Invalid default_auth_type" in str(exc.value)

    def test_update_coa_settings(self, service, mock_db, mock_radius_settings):
        """Should update CoA settings."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        updates = RADIUSSettingsUpdate(
            coa={"enabled": False, "port": 3800, "timeout_seconds": 10}
        )
        service.update_settings(updates)

        assert mock_radius_settings.coa_enabled is False
        assert mock_radius_settings.coa_port == 3800
        assert mock_radius_settings.coa_timeout_seconds == 10

    def test_update_bandwidth_settings(self, service, mock_db, mock_radius_settings):
        """Should update bandwidth settings with valid enum."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        updates = RADIUSSettingsUpdate(
            bandwidth={"unit": "GBPS", "burst_enabled": True}
        )
        service.update_settings(updates)

        assert mock_radius_settings.bandwidth_unit == BandwidthUnit.GBPS
        assert mock_radius_settings.burst_enabled is True


class TestSeedDefaults:
    """Test seed_defaults method."""

    def test_seed_creates_settings(self, service, mock_db):
        """Should create new settings with seed."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.seed_defaults()

        mock_db.add.assert_called()  # Called for settings and default mappings
        mock_db.flush.assert_called()

    def test_seed_returns_existing(self, service, mock_db, mock_radius_settings):
        """Should return existing settings if they exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        result = service.seed_defaults()

        assert result == mock_radius_settings
        mock_db.add.assert_not_called()


# =============================================================================
# ATTRIBUTE MAPPING TESTS
# =============================================================================

class TestAttributeMappings:
    """Test attribute mapping CRUD operations."""

    def test_list_attribute_mappings(self, service, mock_db, mock_attribute_mapping):
        """Should list attribute mappings with pagination."""
        mock_paginate = MagicMock()
        mock_paginate.items = [mock_attribute_mapping]
        mock_paginate.total = 1

        with patch('app.services.subscriptions.radius_settings.paginate', return_value=mock_paginate):
            filters = AttributeMappingFilters()
            pagination = PaginationParams(offset=0, limit=50)
            result = service.list_attribute_mappings(filters, pagination)

            assert result.total == 1
            assert len(result.items) == 1

    def test_list_attribute_mappings_filter_by_nas_type(self, service, mock_db):
        """Should filter mappings by NAS type."""
        filters = AttributeMappingFilters(nas_type="MIKROTIK")

        with patch('app.services.subscriptions.radius_settings.paginate'):
            service.list_attribute_mappings(filters)

        # Verify filter was applied
        mock_db.query.return_value.filter.assert_called()

    def test_get_attribute_mapping_success(self, service, mock_db, mock_attribute_mapping):
        """Should return mapping by ID."""
        mock_db.get.return_value = mock_attribute_mapping

        result = service.get_attribute_mapping(1)

        assert result == mock_attribute_mapping
        mock_db.get.assert_called_once_with(RADIUSAttributeMapping, 1)

    def test_get_attribute_mapping_not_found(self, service, mock_db):
        """Should raise NotFoundError if mapping not found."""
        mock_db.get.return_value = None

        with pytest.raises(NotFoundError) as exc:
            service.get_attribute_mapping(999)
        assert "Attribute mapping 999 not found" in str(exc.value)

    def test_create_attribute_mapping(self, service, mock_db):
        """Should create a new attribute mapping."""
        data = AttributeMappingData(
            nas_type="MIKROTIK",
            attribute_name="test_attr",
            radius_attribute="Test-Attribute",
            radius_vendor_id=14988,
        )

        service.create_attribute_mapping(data)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_create_attribute_mapping_invalid_nas_type(self, service, mock_db):
        """Should raise ValidationError for invalid NAS type."""
        data = AttributeMappingData(
            nas_type="INVALID",
            attribute_name="test_attr",
            radius_attribute="Test-Attribute",
        )

        with pytest.raises(ValidationError) as exc:
            service.create_attribute_mapping(data)
        assert "Invalid nas_type" in str(exc.value)

    def test_update_attribute_mapping(self, service, mock_db, mock_attribute_mapping):
        """Should update an existing mapping."""
        mock_db.get.return_value = mock_attribute_mapping

        data = AttributeMappingData(
            nas_type="CISCO",
            attribute_name="updated_attr",
            radius_attribute="Updated-Attribute",
        )

        result = service.update_attribute_mapping(1, data)

        assert mock_attribute_mapping.nas_type == NASType.CISCO
        assert mock_attribute_mapping.attribute_name == "updated_attr"
        mock_db.flush.assert_called_once()

    def test_delete_attribute_mapping_soft_delete(self, service, mock_db, mock_attribute_mapping):
        """Should soft-delete mapping by setting is_active to False."""
        mock_db.get.return_value = mock_attribute_mapping

        service.delete_attribute_mapping(1)

        assert mock_attribute_mapping.is_active is False
        mock_db.flush.assert_called_once()

    def test_get_mappings_for_nas_type(self, service, mock_db, mock_attribute_mapping):
        """Should return all active mappings for a NAS type."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_attribute_mapping]

        result = service.get_mappings_for_nas_type("MIKROTIK")

        assert len(result) == 1
        assert result[0] == mock_attribute_mapping


# =============================================================================
# NAS CONFIG TESTS
# =============================================================================

class TestNASConfig:
    """Test NAS configuration CRUD operations."""

    def test_list_nas_configs(self, service, mock_db, mock_nas_config):
        """Should list NAS configs with pagination."""
        mock_paginate = MagicMock()
        mock_paginate.items = [mock_nas_config]
        mock_paginate.total = 1

        with patch('app.services.subscriptions.radius_settings.paginate', return_value=mock_paginate):
            filters = NASConfigFilters()
            pagination = PaginationParams(offset=0, limit=50)
            result = service.list_nas_configs(filters, pagination)

            assert result.total == 1

    def test_list_nas_configs_filter_by_router(self, service, mock_db):
        """Should filter configs by router_id."""
        filters = NASConfigFilters(router_id=100)

        with patch('app.services.subscriptions.radius_settings.paginate'):
            service.list_nas_configs(filters)

        mock_db.query.return_value.filter.assert_called()

    def test_get_nas_config_success(self, service, mock_db, mock_nas_config):
        """Should return config by ID."""
        mock_db.get.return_value = mock_nas_config

        result = service.get_nas_config(1)

        assert result == mock_nas_config

    def test_get_nas_config_not_found(self, service, mock_db):
        """Should raise NotFoundError if config not found."""
        mock_db.get.return_value = None

        with pytest.raises(NotFoundError) as exc:
            service.get_nas_config(999)
        assert "NAS config 999 not found" in str(exc.value)

    def test_get_nas_config_for_router(self, service, mock_db, mock_nas_config):
        """Should return config for a specific router."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_nas_config

        result = service.get_nas_config_for_router(100)

        assert result == mock_nas_config

    def test_create_nas_config_success(self, service, mock_db):
        """Should create a new NAS config."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = NASConfigData(
            router_id=100,
            nas_identifier="router-001",
            nas_type="MIKROTIK",
        )

        service.create_nas_config(data)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_create_nas_config_duplicate_router_raises(self, service, mock_db, mock_nas_config):
        """Should raise ValidationError if config already exists for router."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_nas_config

        data = NASConfigData(
            router_id=100,  # Same router_id as existing
            nas_identifier="new-router",
            nas_type="MIKROTIK",
        )

        with pytest.raises(ValidationError) as exc:
            service.create_nas_config(data)
        assert "already exists for router 100" in str(exc.value)

    def test_create_nas_config_invalid_nas_type(self, service, mock_db):
        """Should raise ValidationError for invalid NAS type."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = NASConfigData(
            router_id=100,
            nas_type="INVALID_TYPE",
        )

        with pytest.raises(ValidationError) as exc:
            service.create_nas_config(data)
        assert "Invalid nas_type" in str(exc.value)

    def test_update_nas_config(self, service, mock_db, mock_nas_config):
        """Should update an existing NAS config."""
        mock_db.get.return_value = mock_nas_config

        data = NASConfigData(
            router_id=100,
            nas_identifier="updated-router",
            nas_type="CISCO",
            coa_enabled=False,
        )

        result = service.update_nas_config(1, data)

        assert mock_nas_config.nas_identifier == "updated-router"
        assert mock_nas_config.nas_type == NASType.CISCO
        assert mock_nas_config.coa_enabled is False

    def test_delete_nas_config_soft_delete(self, service, mock_db, mock_nas_config):
        """Should soft-delete config by setting is_active to False."""
        mock_db.get.return_value = mock_nas_config

        service.delete_nas_config(1)

        assert mock_nas_config.is_active is False
        mock_db.flush.assert_called_once()


# =============================================================================
# DICTIONARY TESTS
# =============================================================================

class TestDictionary:
    """Test RADIUS dictionary CRUD operations."""

    def test_list_dictionary_entries(self, service, mock_db, mock_dictionary_entry):
        """Should list dictionary entries with pagination."""
        mock_paginate = MagicMock()
        mock_paginate.items = [mock_dictionary_entry]
        mock_paginate.total = 1

        with patch('app.services.subscriptions.radius_settings.paginate', return_value=mock_paginate):
            filters = DictionaryFilters()
            pagination = PaginationParams(offset=0, limit=50)
            result = service.list_dictionary_entries(filters, pagination)

            assert result.total == 1

    def test_list_dictionary_entries_filter_by_vendor(self, service, mock_db):
        """Should filter entries by vendor."""
        filters = DictionaryFilters(vendor_name="MikroTik", vendor_id=14988)

        with patch('app.services.subscriptions.radius_settings.paginate'):
            service.list_dictionary_entries(filters)

        mock_db.query.return_value.filter.assert_called()

    def test_get_dictionary_entry_success(self, service, mock_db, mock_dictionary_entry):
        """Should return entry by ID."""
        mock_db.get.return_value = mock_dictionary_entry

        result = service.get_dictionary_entry(1)

        assert result == mock_dictionary_entry

    def test_get_dictionary_entry_not_found(self, service, mock_db):
        """Should raise NotFoundError if entry not found."""
        mock_db.get.return_value = None

        with pytest.raises(NotFoundError) as exc:
            service.get_dictionary_entry(999)
        assert "Dictionary entry 999 not found" in str(exc.value)

    def test_create_dictionary_entry(self, service, mock_db):
        """Should create a new dictionary entry."""
        data = DictionaryEntryData(
            vendor_name="MikroTik",
            vendor_id=14988,
            attribute_name="Test-Attr",
            attribute_type=100,
            attribute_value_type="string",
        )

        service.create_dictionary_entry(data)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_update_dictionary_entry(self, service, mock_db, mock_dictionary_entry):
        """Should update an existing dictionary entry."""
        mock_db.get.return_value = mock_dictionary_entry

        data = DictionaryEntryData(
            vendor_name="Cisco",
            vendor_id=9,
            attribute_name="Updated-Attr",
            attribute_type=50,
        )

        result = service.update_dictionary_entry(1, data)

        assert mock_dictionary_entry.vendor_name == "Cisco"
        assert mock_dictionary_entry.vendor_id == 9
        mock_db.flush.assert_called_once()

    def test_delete_dictionary_entry_soft_delete(self, service, mock_db, mock_dictionary_entry):
        """Should soft-delete entry by setting is_active to False."""
        mock_db.get.return_value = mock_dictionary_entry

        service.delete_dictionary_entry(1)

        assert mock_dictionary_entry.is_active is False
        mock_db.flush.assert_called_once()

    def test_get_vendors(self, service, mock_db):
        """Should return list of vendors with attribute counts."""
        mock_result = MagicMock()
        mock_result.vendor_name = "MikroTik"
        mock_result.vendor_id = 14988
        mock_result.attribute_count = 10

        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [mock_result]

        result = service.get_vendors()

        assert len(result) == 1
        assert result[0]["vendor_name"] == "MikroTik"
        assert result[0]["vendor_id"] == 14988
        assert result[0]["attribute_count"] == 10


# =============================================================================
# DIAGNOSTICS TESTS
# =============================================================================

class TestDiagnostics:
    """Test diagnostic methods."""

    def test_test_radius_connection(self, service, mock_db, mock_radius_settings):
        """Should test RADIUS connection and return result."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        result = service.test_radius_connection()

        assert result.success is True
        assert result.server == "radius.example.com"
        assert result.port == 1812

    def test_test_radius_connection_with_custom_params(self, service, mock_db, mock_radius_settings):
        """Should use custom params if provided."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        result = service.test_radius_connection(
            host="custom.radius.com",
            port=1818,
            secret="custom_secret"
        )

        assert result.server == "custom.radius.com"
        assert result.port == 1818

    def test_test_coa(self, service):
        """Should test CoA connectivity."""
        result = service.test_coa(
            nas_ip="192.168.1.1",
            port=3799,
            action="DISCONNECT"
        )

        assert result.success is True
        assert result.nas_ip == "192.168.1.1"
        assert result.port == 3799
        assert result.action == "DISCONNECT"

    def test_get_health_status(self, service, mock_db, mock_radius_settings):
        """Should return health status."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_radius_settings

        result = service.get_health_status()

        assert result.primary_server_up is True
        assert result.database_connected is True


# =============================================================================
# HELPER METHOD TESTS
# =============================================================================

class TestHelperMethods:
    """Test internal helper methods."""

    def test_to_settings_data_converts_all_fields(self, service, mock_radius_settings):
        """Should convert model to DTO with all fields."""
        result = service._to_settings_data(mock_radius_settings)

        assert result.server.host == "radius.example.com"
        assert result.server.auth_port == 1812
        assert result.authentication.default_auth_type == "PAP"
        assert result.accounting.method == "RADIUS"
        assert result.session_limits.max_sessions_per_user == 1
        assert result.coa.enabled is True
        assert result.bandwidth.unit == "MBPS"
        assert result.ip_pool.ip_pool_enabled is True
        assert result.nas_defaults.default_nas_type == "MIKROTIK"
        assert result.database.enabled is True
        assert result.logging.log_auth_requests is True
