from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Database (uses psycopg3 driver)
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/dotmac_insights"

    # CORS Configuration
    cors_origins: str = ""  # Comma-separated list of allowed origins, empty = no CORS

    # JWT/OIDC Authentication (better-auth integration)
    jwt_issuer: str = ""  # e.g., "https://auth.example.com"
    jwks_url: str = ""  # e.g., "https://auth.example.com/.well-known/jwks.json"
    jwt_audience: Optional[str] = None  # Optional audience claim validation
    jwks_cache_ttl: int = 3600  # Seconds to cache JWKS keys (1 hour default)

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

    # Environment
    environment: str = "development"  # development, staging, production

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

# Validate JWT auth in production
if settings.is_production and not settings.jwks_url:
    raise ValueError("JWKS_URL must be set in production environment for JWT authentication")
