"""Authentication and Authorization module.

This module provides:
- JWT verification with JWKS caching (for better-auth/auth.js integration)
- Service token authentication (for machine-to-machine)
- RBAC scope enforcement via require() decorator
- User/principal management
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime
from functools import wraps
from typing import Optional, Union, Callable, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket

import bcrypt
import httpx
import structlog
from fastapi import HTTPException, Depends, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from jose.exceptions import JWKError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import User, ServiceToken, TokenDenylist
from app.middleware.metrics import increment_contacts_auth_failure

logger = structlog.get_logger()

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
AUTH_COOKIE_NAME = "dotmac_access_token"


# ============================================================================
# Origin Validation (CSRF/CSWSH Protection)
# ============================================================================


def validate_origin(origin: Optional[str], allowed_origins: List[str]) -> bool:
    """Validate Origin header against allowed CORS origins.

    Used for CSRF protection on login endpoints and CSWSH protection on WebSockets.

    Args:
        origin: The Origin header value (may be None)
        allowed_origins: List of allowed origin URLs from settings.cors_origins_list

    Returns:
        True if origin is valid, False otherwise
    """
    if not origin:
        return False

    # Normalize origin (strip trailing slash)
    origin = origin.rstrip("/").lower()

    for allowed in allowed_origins:
        allowed_normalized = allowed.rstrip("/").lower()
        if origin == allowed_normalized:
            return True

    return False


def get_origin_from_request(request: Request) -> Optional[str]:
    """Extract Origin header from request, falling back to Referer if needed."""
    origin = request.headers.get("origin")
    if origin:
        return origin

    # Fall back to Referer header (extract origin portion)
    referer = request.headers.get("referer")
    if referer:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            pass

    return None


def get_origin_from_websocket(websocket: "WebSocket") -> Optional[str]:
    """Extract Origin header from WebSocket connection."""
    return websocket.headers.get("origin")


# ============================================================================
# Pydantic Models for Auth
# ============================================================================


class JWTClaims(BaseModel):
    """Parsed JWT claims from better-auth."""
    sub: str  # User ID from better-auth
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = None
    scopes: Optional[List[str]] = None


class Principal(BaseModel):
    """Authenticated principal (user or service token)."""
    type: str  # "user" or "service_token"
    id: int  # User ID or ServiceToken ID
    external_id: Optional[str] = None  # better-auth user ID (for users)
    email: Optional[str] = None
    name: Optional[str] = None
    is_superuser: bool = False
    scopes: set[str] = set()  # Available permission scopes
    raw_claims: Optional[dict] = None  # Original JWT claims (for users)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def has_scope(self, scope: str) -> bool:
        """Check if principal has a specific permission scope."""
        if self.is_superuser:
            return True
        if "*" in self.scopes:
            return True
        if scope in self.scopes:
            return True
        # Check wildcard permissions
        for s in self.scopes:
            if s.endswith(":*"):
                prefix = s[:-1]
                if scope.startswith(prefix):
                    return True
        return False


# ============================================================================
# JWKS Cache
# ============================================================================


class JWKSCache:
    """Caches JWKS keys with TTL to avoid repeated fetches."""

    def __init__(self) -> None:
        self._keys: dict = {}
        self._fetched_at: float = 0
        self._ttl: int = settings.jwks_cache_ttl

    async def get_keys(self) -> dict:
        """Get JWKS keys, fetching if cache is expired."""
        now = time.time()

        if self._keys and (now - self._fetched_at) < self._ttl:
            return self._keys

        if not settings.jwks_url:
            logger.warning("jwks_url_not_configured")
            return {}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(settings.jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            # Convert JWKS to key dict indexed by kid
            self._keys = {}
            for key_data in jwks_data.get("keys", []):
                kid = key_data.get("kid")
                if kid:
                    self._keys[kid] = key_data

            self._fetched_at = now
            logger.info("jwks_refreshed", key_count=len(self._keys))
            return self._keys

        except Exception as e:
            logger.error("jwks_fetch_failed", error=str(e))
            # Return stale cache if available
            if self._keys:
                logger.warning("using_stale_jwks_cache")
                return self._keys
            return {}

    def invalidate(self) -> None:
        """Force cache invalidation."""
        self._fetched_at = 0


# Singleton JWKS cache
_jwks_cache = JWKSCache()


# ============================================================================
# JWT Verification
# ============================================================================


async def verify_jwt(token: str) -> JWTClaims:
    """Verify a JWT token using JWKS.

    Args:
        token: The JWT token string

    Returns:
        JWTClaims with verified claims

    Raises:
        HTTPException: If token is invalid, expired, or verification fails
    """
    # E2E testing mode: allow HS256 JWT tokens when E2E auth is configured
    if settings.e2e_jwt_secret and settings.e2e_auth_enabled:
        try:
            payload = jwt.decode(
                token,
                settings.e2e_jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True, "verify_aud": False, "verify_iss": False},
            )
            return JWTClaims(**payload)
        except JWTError:
            # Fall through to JWKS auth if E2E token decode fails
            pass

    if not settings.jwks_url:
        raise HTTPException(
            status_code=500,
            detail="JWT authentication not configured (JWKS_URL not set)"
        )

    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(status_code=401, detail="JWT missing kid in header")

        # Get JWKS keys
        keys = await _jwks_cache.get_keys()
        if kid not in keys:
            # Try refreshing cache in case of key rotation
            _jwks_cache.invalidate()
            keys = await _jwks_cache.get_keys()

        if kid not in keys:
            logger.warning("jwt_kid_not_found", kid=kid)
            raise HTTPException(status_code=401, detail="JWT signing key not found")

        # Build public key
        key_data = keys[kid]
        public_key = jwk.construct(key_data)

        # Verify and decode
        options = {
            "verify_exp": True,
            "verify_iss": bool(settings.jwt_issuer),
            "verify_aud": bool(settings.jwt_audience),
        }

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            issuer=settings.jwt_issuer or None,
            audience=settings.jwt_audience or None,
            options=options,
        )

        return JWTClaims(**payload)

    except JWTError as e:
        logger.warning("jwt_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {str(e)}")
    except JWKError as e:
        logger.error("jwk_error", error=str(e))
        raise HTTPException(status_code=401, detail="JWT key error")


# ============================================================================
# Service Token Verification
# ============================================================================


def hash_service_token(token: str) -> str:
    """Hash a service token using bcrypt."""
    return bcrypt.hashpw(
        token.encode("utf-8"),
        bcrypt.gensalt(rounds=settings.service_token_hash_rounds)
    ).decode("utf-8")


def verify_service_token_hash(token: str, token_hash: str) -> bool:
    """Verify a service token against its hash."""
    return bcrypt.checkpw(token.encode("utf-8"), token_hash.encode("utf-8"))


async def verify_service_token(token: str, db: Session) -> ServiceToken:
    """Verify a service token and return the token record.

    Args:
        token: The service token string (format: prefix_secret)
        db: Database session

    Returns:
        ServiceToken record if valid

    Raises:
        HTTPException: If token is invalid, expired, or revoked
    """
    # Extract prefix (first 8 chars used for lookup)
    if len(token) < 12:
        raise HTTPException(status_code=401, detail="Invalid service token format")

    prefix = token[:8]

    # Find token by prefix
    service_token = db.query(ServiceToken).filter(
        ServiceToken.token_prefix == prefix,
        ServiceToken.is_active == True,
    ).first()

    if not service_token:
        logger.warning("service_token_not_found", prefix=prefix)
        raise HTTPException(status_code=401, detail="Invalid service token")

    # Check expiration
    if service_token.expires_at and datetime.utcnow() > service_token.expires_at:
        logger.warning("service_token_expired", token_id=service_token.id)
        raise HTTPException(status_code=401, detail="Service token expired")

    # Check revocation
    if service_token.revoked_at:
        logger.warning("service_token_revoked", token_id=service_token.id)
        raise HTTPException(status_code=401, detail="Service token revoked")

    # Verify hash
    if not verify_service_token_hash(token, service_token.token_hash):
        logger.warning("service_token_hash_mismatch", token_id=service_token.id)
        raise HTTPException(status_code=401, detail="Invalid service token")

    # Update usage stats
    service_token.last_used_at = datetime.utcnow()
    service_token.use_count += 1
    db.commit()

    return service_token


def generate_service_token() -> tuple[str, str, str]:
    """Generate a new service token.

    Returns:
        Tuple of (full_token, prefix, hash)
    """
    # Generate 32 bytes of random data
    secret = secrets.token_urlsafe(32)
    prefix = secret[:8]
    token_hash = hash_service_token(secret)
    return secret, prefix, token_hash


# ============================================================================
# Token Denylist
# ============================================================================


async def is_token_denylisted(jti: str, db: Session) -> bool:
    """Check if a JWT is in the denylist."""
    if not jti:
        return False
    return db.query(TokenDenylist).filter(TokenDenylist.jti == jti).first() is not None


async def denylist_token(jti: str, expires_at: datetime, reason: str, db: Session) -> None:
    """Add a JWT to the denylist."""
    entry = TokenDenylist(jti=jti, expires_at=expires_at, reason=reason)
    db.add(entry)
    db.commit()


# ============================================================================
# User Resolution
# ============================================================================


async def get_or_create_user(claims: JWTClaims, db: Session) -> User:
    """Get or create a user from JWT claims.

    On first login, creates a user record linked to better-auth via external_id.
    On subsequent logins, updates user info from JWT claims.

    Security:
    - Users are matched by external_id (sub claim) only in production
    - Email fallback is only allowed in E2E test mode to handle test user variations
    - This prevents cross-account linking if an OAuth provider misconfigures email claims

    Note: Users are created without superuser privileges. Promote explicitly via admin tooling.
    """
    # First try to find by external_id (primary identity)
    user = db.query(User).filter(User.external_id == claims.sub).first()

    # Security: Email fallback is ONLY allowed in E2E test mode
    # In production, users must match by external_id to prevent account takeover
    # via misconfigured OAuth provider email claims
    if not user and claims.email and settings.e2e_auth_enabled and settings.e2e_jwt_secret:
        user = db.query(User).filter(User.email == claims.email).first()
        if user:
            # Update external_id to match current token (for E2E tests only)
            logger.info(
                "user_external_id_updated_e2e",
                user_id=user.id,
                old_external_id=user.external_id,
                new_external_id=claims.sub,
            )
            user.external_id = claims.sub

    if not user:
        # Check if this is the first user in the system (for bootstrap audit)
        is_first_user = db.query(User).count() == 0

        # Create new user
        user = User(
            external_id=claims.sub,
            email=claims.email or f"{claims.sub}@unknown",
            name=claims.name,
            picture=claims.picture,
            is_active=True,
            is_superuser=False,
            last_login_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        if is_first_user:
            logger.warning(
                "first_user_created_without_superuser",
                user_id=user.id,
                external_id=claims.sub,
                email=claims.email,
            )
        else:
            logger.info("user_created", user_id=user.id, external_id=claims.sub)
    else:
        # Update user info from claims
        if claims.email and claims.email != user.email:
            user.email = claims.email
        if claims.name:
            user.name = claims.name
        if claims.picture:
            user.picture = claims.picture
        user.last_login_at = datetime.utcnow()
        db.commit()

    return user


# ============================================================================
# FastAPI Dependencies
# ============================================================================


async def get_current_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    """Get the current authenticated principal from the request.

    Supports multiple authentication methods:
    1. Bearer token (JWT from better-auth)
    2. Service token (Bearer token without dots - for machine-to-machine auth)

    Returns:
        Principal object with user/token info and scopes

    Raises:
        HTTPException: If no valid authentication provided
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        token = request.cookies.get(AUTH_COOKIE_NAME)

    # Try Bearer token or cookie token
    if token:

        # Check if it's a service token (shorter, no dots)
        if "." not in token:
            # Service token authentication
            service_token = await verify_service_token(token, db)
            return Principal(
                type="service_token",
                id=service_token.id,
                external_id=None,
                email=None,
                name=service_token.name,
                is_superuser=False,
                scopes=set(service_token.scope_list),
            )
        else:
            # JWT authentication
            claims = await verify_jwt(token)

            # Check denylist
            if claims.jti and await is_token_denylisted(claims.jti, db):
                raise HTTPException(status_code=401, detail="Token has been revoked")

            # Get or create user
            user = await get_or_create_user(claims, db)

            if not user.is_active:
                raise HTTPException(status_code=403, detail="User account is disabled")

            principal_scopes = user.all_permissions
            is_superuser = user.is_superuser
            # In E2E mode, use scopes from the test JWT instead of user permissions
            if settings.e2e_jwt_secret and settings.e2e_auth_enabled and claims.scopes is not None:
                principal_scopes = set(claims.scopes or [])
                is_superuser = False

            return Principal(
                type="user",
                id=user.id,
                external_id=user.external_id,
                email=user.email,
                name=user.name,
                is_superuser=is_superuser,
                scopes=principal_scopes,
                raw_claims=claims.model_dump(),
            )

    # No valid authentication
    increment_contacts_auth_failure("401")
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Bearer token (JWT or service token).",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[Principal]:
    """Get the current principal if authenticated, None otherwise.

    Use this for endpoints that work differently for authenticated vs anonymous users.
    """
    try:
        return await get_current_principal(request, credentials, db)
    except HTTPException:
        return None


# ============================================================================
# Scope Enforcement - require() decorator
# ============================================================================


def require(*scopes: str) -> Callable:
    """Decorator to require specific permission scopes.

    Usage:
        @router.get("/data")
        @require("explorer:read")
        async def get_data(principal: Principal = Depends(get_current_principal)):
            ...

        @router.post("/sync")
        @require("sync:splynx:write")
        async def trigger_sync(principal: Principal = Depends(get_current_principal)):
            ...

        # Multiple scopes (any one grants access)
        @router.get("/admin")
        @require("admin:users:read", "admin:roles:read")
        async def admin_dashboard(principal: Principal = Depends(get_current_principal)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Find principal in kwargs
            principal: Optional[Principal] = kwargs.get("principal")

            if not principal:
                # Try to find in args by looking for Principal type
                for arg in args:
                    if isinstance(arg, Principal):
                        principal = arg
                        break

            if not principal:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )

            # Check if principal has any of the required scopes
            has_permission = any(principal.has_scope(scope) for scope in scopes)

            if not has_permission:
                logger.warning(
                    "permission_denied",
                    principal_type=principal.type,
                    principal_id=principal.id,
                    required_scopes=list(scopes),
                    available_scopes=list(principal.scopes),
                )
                increment_contacts_auth_failure("403")
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied. Required: {', '.join(scopes)}",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


class Require:
    """Dependency class for scope enforcement.

    Alternative to @require decorator, useful when you need more control.

    Usage:
        @router.get("/data")
        async def get_data(
            principal: Principal = Depends(get_current_principal),
            _: None = Depends(Require("explorer:read")),
        ):
            ...
    """

    def __init__(self, *scopes: str):
        self.scopes = scopes

    async def __call__(
        self,
        principal: Principal = Depends(get_current_principal),
    ) -> None:
        has_permission = any(principal.has_scope(scope) for scope in self.scopes)

        if not has_permission:
            logger.warning(
                "permission_denied",
                principal_type=principal.type,
                principal_id=principal.id,
                required_scopes=list(self.scopes),
            )
            increment_contacts_auth_failure("403")
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied. Required: {', '.join(self.scopes)}",
            )
