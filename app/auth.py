from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from typing import Optional
import secrets
import structlog

from app.config import settings

logger = structlog.get_logger()

# API Key can be passed via header or query parameter
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def verify_api_key(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
) -> str:
    """
    Verify the API key from either header or query parameter.
    Returns the API key if valid, raises HTTPException if not.
    """
    api_key = api_key_header_value or api_key_query_value

    if not api_key:
        logger.warning("api_key_missing")
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header or api_key query parameter.",
        )

    # Compare using constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.api_key):
        logger.warning("api_key_invalid", provided_key_prefix=api_key[:8] + "..." if len(api_key) > 8 else "***")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return api_key


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)
