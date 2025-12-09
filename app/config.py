from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Database (uses psycopg3 driver)
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/dotmac_insights"

    # API Security
    api_key: str = ""  # Required for production - set via environment variable
    cors_origins: str = ""  # Comma-separated list of allowed origins, empty = no CORS

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

# Validate API key in production
if settings.is_production and not settings.api_key:
    raise ValueError("API_KEY must be set in production environment")
