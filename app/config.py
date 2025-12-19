from pydantic_settings import BaseSettings
from typing import Optional, List
import os


def _default_database_url() -> str:
    # Prefer explicit test DB, then DATABASE_URL, then local sqlite
    return os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite:///./dotmac.db"


class Settings(BaseSettings):
    # Database (uses psycopg3 driver unless overridden)
    database_url: str = _default_database_url()

    # CORS Configuration
    cors_origins: str = ""  # Comma-separated list of allowed origins, empty = no CORS

    # JWT/OIDC Authentication (better-auth integration)
    jwt_issuer: str = ""  # e.g., "https://auth.example.com"
    jwks_url: str = ""  # e.g., "https://auth.example.com/.well-known/jwks.json"
    jwt_audience: Optional[str] = None  # Optional audience claim validation
    jwks_cache_ttl: int = 3600  # Seconds to cache JWKS keys (1 hour default)
    # Test-only JWT secret for E2E runs (HS256)
    e2e_jwt_secret: Optional[str] = None
    e2e_auth_enabled: bool = False

    # Service token settings
    service_token_hash_rounds: int = 12  # bcrypt rounds for hashing service tokens

    # Splynx
    splynx_api_url: str = ""
    splynx_api_key: str = ""
    splynx_api_secret: str = ""
    splynx_auth_basic: str = ""  # Base64 encoded "key:secret" for Basic Auth

    # ERPNext
    erpnext_api_url: str = ""
    erpnext_api_key: str = ""
    erpnext_api_secret: str = ""

    # Chatwoot
    chatwoot_api_url: str = ""
    chatwoot_api_token: str = ""
    chatwoot_account_id: int = 1

    # Sync settings
    sync_interval_minutes: int = 15
    full_sync_hour: int = 2

    # Batch sizes for sync operations
    sync_batch_size: int = 500  # Default batch size
    sync_batch_size_customers: int = 500
    sync_batch_size_invoices: int = 500
    sync_batch_size_payments: int = 500
    sync_batch_size_tickets: int = 500
    sync_batch_size_messages: int = 1000  # Higher for messages

    # Circuit breaker settings
    circuit_breaker_fail_max: int = 5  # Failures before opening circuit
    circuit_breaker_reset_timeout: int = 60  # Seconds before attempting reset

    # Retry settings
    retry_max_attempts: int = 3
    retry_min_wait: int = 2  # seconds
    retry_max_wait: int = 30  # seconds

    # Redis
    redis_url: Optional[str] = None

    # Notifications
    notification_templates_path: str = "data/notification_templates.json"

    # OpenBao (secrets management)
    openbao_url: Optional[str] = None  # e.g., http://localhost:8200
    openbao_token: Optional[str] = None

    # Analytics
    analytics_statement_timeout_ms: Optional[int] = 15000  # per-request DB timeout

    # Environment
    environment: str = "development"  # development, staging, production

    # Currency
    # Default currency for Nigerian financial transactions.
    # API schemas may use different defaults for international modules (e.g., tax_core uses USD).
    default_currency: str = "NGN"
    base_currency: str = "NGN"  # Functional currency for multi-currency conversion

    # =====================================================================
    # Platform Integration (Phase 5)
    # =====================================================================

    # Instance identity
    platform_instance_id: Optional[str] = None
    platform_tenant_id: Optional[str] = None
    platform_api_url: Optional[str] = None
    platform_api_key: Optional[str] = None

    # Client resilience
    platform_client_timeout_seconds: int = 10
    platform_client_max_retries: int = 3
    platform_client_retry_min_wait: int = 1
    platform_client_retry_max_wait: int = 30
    platform_client_circuit_breaker_threshold: int = 5
    platform_client_circuit_breaker_timeout: int = 60
    platform_response_cache_ttl_seconds: int = 300

    # License validation
    license_check_interval_seconds: int = 3600  # 1 hour
    license_grace_period_hours: int = 72
    license_cache_ttl_seconds: int = 3600
    license_fail_open_on_startup: bool = True

    # Feature flags bridge
    feature_flags_refresh_interval_seconds: int = 300
    feature_flags_cache_ttl_seconds: int = 300
    feature_flags_platform_precedence: bool = True

    # Usage reporting
    usage_report_interval_seconds: int = 3600
    usage_report_batch_size: int = 100
    usage_report_retry_max_attempts: int = 5
    usage_report_dlq_enabled: bool = True

    # Health/heartbeat
    heartbeat_interval_seconds: int = 300
    heartbeat_timeout_seconds: int = 5
    health_check_include_details: bool = True

    # OTEL observability
    otel_enabled: bool = False
    otel_exporter_endpoint: Optional[str] = None
    otel_service_name: str = "dotmac-insights"
    otel_service_namespace: str = "dotmac"
    otel_trace_sample_rate: float = 0.1  # 10% sampling default to avoid overhead

    # Payroll
    payroll_cache_ttl_seconds: int = 300

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Override with explicit test database if provided, regardless of DATABASE_URL
test_db_override = os.getenv("TEST_DATABASE_URL")
if test_db_override:
    settings.database_url = test_db_override

# When running tests, fall back to a local SQLite DB unless explicitly overridden
if os.getenv("PYTEST_CURRENT_TEST"):
    settings.database_url = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")

# Validate JWT auth in production
if settings.is_production and not settings.jwks_url:
    raise ValueError("JWKS_URL must be set in production environment for JWT authentication")
if settings.is_production and (settings.e2e_jwt_secret or settings.e2e_auth_enabled):
    raise ValueError("E2E auth must not be enabled in production")

# Production safety checks
if settings.is_production and not os.getenv("PYTEST_CURRENT_TEST"):
    if not settings.database_url or settings.database_url.startswith("sqlite"):
        raise ValueError("DATABASE_URL must be set to a non-sqlite database in production")
    if not settings.cors_origins_list:
        raise ValueError("CORS_ORIGINS must be configured in production to restrict origins")
