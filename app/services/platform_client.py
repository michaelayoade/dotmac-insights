"""
Platform Client for DotMac Platform Services Integration.

This module provides:
- HTTP client with JWT/API key authentication
- Automatic token refresh
- License validation with caching
- Feature flag fetching
- Usage reporting with batching
- Circuit breaker and retry logic

Based on recommendations from platform architecture review:
- Always attach Authorization (JWT or API key) and X-Tenant-ID headers
- Refresh tokens via /api/v1/auth/refresh
- Cache license validation results
- Batch usage reports before sending
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Dict, List, Callable, TypeVar, cast
from functools import wraps

import httpx
import structlog
from pydantic import BaseModel, Field

from app.config import settings

logger = structlog.get_logger()

T = TypeVar("T")


# =============================================================================
# EXCEPTIONS
# =============================================================================


class PlatformClientError(Exception):
    """Base exception for platform client errors."""
    pass


class PlatformAuthenticationError(PlatformClientError):
    """Authentication failed with platform."""
    pass


class PlatformConnectionError(PlatformClientError):
    """Could not connect to platform."""
    pass


class PlatformRateLimitError(PlatformClientError):
    """Rate limited by platform."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class LicenseValidationError(PlatformClientError):
    """License validation failed."""
    pass


class LicenseExpiredError(LicenseValidationError):
    """License has expired."""
    pass


class LicenseInvalidError(LicenseValidationError):
    """License is invalid."""
    pass


# =============================================================================
# DATA MODELS
# =============================================================================


class LicenseStatus(str, Enum):
    """License status values."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    PENDING = "pending"


class LicenseType(str, Enum):
    """License type values."""
    SUBSCRIPTION = "subscription"
    PERPETUAL = "perpetual"
    TRIAL = "trial"
    EVALUATION = "evaluation"


@dataclass
class LicenseInfo:
    """Cached license information."""
    license_id: str
    license_key: str
    status: LicenseStatus
    license_type: LicenseType
    product_id: str
    tenant_id: str
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)
    max_users: int = 0
    expires_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    next_validation_at: Optional[datetime] = None
    grace_period_end: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        """Check if license is currently valid."""
        if self.status not in (LicenseStatus.ACTIVE, LicenseStatus.TRIAL):
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            # Check grace period
            if self.grace_period_end and datetime.now(timezone.utc) <= self.grace_period_end:
                return True
            return False
        return True

    @property
    def is_in_grace_period(self) -> bool:
        """Check if license is in grace period."""
        if not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        if now <= self.expires_at:
            return False
        if self.grace_period_end and now <= self.grace_period_end:
            return True
        return False

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Days until license expires."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def has_feature(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.features.get(feature, False)

    def get_limit(self, limit_name: str, default: int = 0) -> int:
        """Get a limit value."""
        return self.limits.get(limit_name, default)


@dataclass
class TenantInfo:
    """Tenant information from platform."""
    tenant_id: str
    name: str
    slug: str
    plan: str
    status: str
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TokenPair:
    """JWT token pair."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        """Check if access token is expired (with 60s buffer)."""
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(seconds=60))


class UsageMetric(BaseModel):
    """Usage metric for reporting."""
    metric: str
    value: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for platform calls."""

    threshold: int = 5
    timeout: int = 60

    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[float] = field(default=None, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) > self.timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker_opened",
                failure_count=self._failure_count,
                threshold=self.threshold,
            )

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False


# =============================================================================
# PLATFORM CLIENT
# =============================================================================


class PlatformClient:
    """
    Client for communicating with DotMac Platform Services.

    Features:
    - Automatic JWT/API key authentication
    - Token refresh handling
    - License validation with caching
    - Feature flag fetching
    - Usage reporting with batching
    - Circuit breaker for resilience

    Usage:
        client = PlatformClient()
        await client.initialize()

        # Validate license
        license_info = await client.validate_license()

        # Get tenant features
        tenant = await client.get_current_tenant()

        # Report usage
        await client.report_usage("api_calls", 100)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
        instance_id: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.platform_api_url or "").rstrip("/")
        self.api_key = api_key or settings.platform_api_key
        self.tenant_id = tenant_id or settings.platform_tenant_id
        self.instance_id = instance_id or settings.platform_instance_id

        # Token management
        self._tokens: Optional[TokenPair] = None
        self._token_lock = asyncio.Lock()

        # Caching
        self._license_cache: Optional[LicenseInfo] = None
        self._tenant_cache: Optional[TenantInfo] = None
        self._feature_cache: Dict[str, bool] = {}
        self._cache_lock = asyncio.Lock()

        # Usage batching
        self._usage_buffer: List[UsageMetric] = []
        self._usage_lock = asyncio.Lock()
        self._last_usage_flush: datetime = datetime.now(timezone.utc)

        # Circuit breaker
        self._circuit = CircuitBreaker(
            threshold=settings.platform_client_circuit_breaker_threshold,
            timeout=settings.platform_client_circuit_breaker_timeout,
        )

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if platform integration is configured."""
        return bool(self.base_url and (self.api_key or self._tokens))

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(settings.platform_client_timeout_seconds),
                follow_redirects=True,
            )
            logger.info("platform_client_initialized", base_url=self.base_url)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "PlatformClient":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    # =========================================================================
    # HTTP REQUEST HANDLING
    # =========================================================================

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with auth and tenant context."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"dotmac-insights/{settings.otel_service_name}",
        }

        # Add tenant ID
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id

        # Add instance ID
        if self.instance_id:
            headers["X-Instance-ID"] = self.instance_id

        # Add authorization
        if self._tokens and not self._tokens.is_expired:
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the platform.

        Handles:
        - Token refresh on 401
        - Retry with exponential backoff
        - Circuit breaker
        - Rate limiting
        """
        if not self._client:
            await self.initialize()
        if not self._client:
            raise PlatformConnectionError("Platform client not initialized")
        client = self._client

        # Check circuit breaker
        if not self._circuit.allow_request():
            raise PlatformConnectionError("Circuit breaker is open")

        # Refresh token if needed
        if self._tokens and self._tokens.is_expired:
            await self._refresh_token()

        headers = self._get_headers()
        # Build URL: /api/licensing/* endpoints use /api, others use /api/v1
        if endpoint.startswith("/api"):
            url = endpoint
        elif endpoint.startswith("/licensing/"):
            url = f"/api{endpoint}"
        else:
            url = f"/api/v1{endpoint}"

        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
            )

            # Handle 401 - try token refresh
            if response.status_code == 401:
                if self._tokens and retry_count == 0:
                    await self._refresh_token()
                    return await self._request(
                        method, endpoint, json=json, params=params, retry_count=1
                    )
                raise PlatformAuthenticationError("Authentication failed")

            # Handle 429 - rate limit
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise PlatformRateLimitError(
                    "Rate limited by platform",
                    retry_after=retry_after,
                )

            # Handle other errors
            if response.status_code >= 400:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("detail", error_detail)
                except Exception:
                    pass
                raise PlatformClientError(
                    f"Platform request failed: {response.status_code} - {error_detail}"
                )

            self._circuit.record_success()
            data = response.json()
            if not isinstance(data, dict):
                raise PlatformClientError("Unexpected response format from platform")
            return cast(Dict[str, Any], data)

        except httpx.RequestError as e:
            self._circuit.record_failure()
            logger.error("platform_request_error", error=str(e), endpoint=endpoint)

            # Retry with backoff
            if retry_count < settings.platform_client_max_retries:
                wait_time = min(
                    settings.platform_client_retry_min_wait * (2 ** retry_count),
                    settings.platform_client_retry_max_wait,
                )
                await asyncio.sleep(wait_time)
                return await self._request(
                    method, endpoint, json=json, params=params, retry_count=retry_count + 1
                )

            raise PlatformConnectionError(f"Failed to connect to platform: {e}")

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    async def login(self, email: str, password: str) -> TokenPair:
        """
        Authenticate with platform and get tokens.

        For user-facing login flow - forwards credentials to platform.
        """
        response = await self._request(
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
        )

        self._tokens = TokenPair(
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=response.get("expires_in", 900)
            ),
            token_type=response.get("token_type", "Bearer"),
        )

        logger.info("platform_login_success")
        return self._tokens

    async def _refresh_token(self) -> None:
        """Refresh the access token using refresh token."""
        if not self._tokens:
            raise PlatformAuthenticationError("No tokens to refresh")

        async with self._token_lock:
            # Double-check after acquiring lock
            if self._tokens and not self._tokens.is_expired:
                return

            try:
                if not self._client:
                    await self.initialize()
                if not self._client:
                    raise PlatformConnectionError("Platform client not initialized")
                response = await self._client.post(
                    "/api/v1/auth/refresh",
                    headers={"Content-Type": "application/json"},
                    json={"refresh_token": self._tokens.refresh_token},
                )

                if response.status_code != 200:
                    self._tokens = None
                    raise PlatformAuthenticationError("Token refresh failed")

                data = response.json()
                self._tokens = TokenPair(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", self._tokens.refresh_token),
                    expires_at=datetime.now(timezone.utc) + timedelta(
                        seconds=data.get("expires_in", 900)
                    ),
                )
                logger.debug("platform_token_refreshed")

            except httpx.RequestError as e:
                logger.error("platform_token_refresh_error", error=str(e))
                raise PlatformConnectionError(f"Token refresh failed: {e}")

    def set_tokens(self, access_token: str, refresh_token: str, expires_in: int = 900) -> None:
        """Set tokens directly (e.g., from cookie/session)."""
        self._tokens = TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )

    # =========================================================================
    # LICENSE VALIDATION
    # =========================================================================

    async def validate_license(
        self,
        license_key: Optional[str] = None,
        force_refresh: bool = False,
    ) -> LicenseInfo:
        """
        Validate license with platform.

        Uses caching to avoid excessive API calls.

        Args:
            license_key: License key to validate. Uses cached key if not provided.
            force_refresh: Force a new validation even if cached.

        Returns:
            LicenseInfo with validation results.

        Raises:
            LicenseValidationError: If validation fails.
        """
        async with self._cache_lock:
            # Check cache
            if not force_refresh and self._license_cache:
                cache_age = (datetime.now(timezone.utc) - self._license_cache.validated_at).total_seconds()
                if cache_age < settings.license_cache_ttl_seconds:
                    return self._license_cache

            # Build request
            payload = {}
            if license_key:
                payload["license_key"] = license_key
            elif self._license_cache:
                payload["license_key"] = self._license_cache.license_key

            # Add hardware fingerprint for stronger binding
            payload["product_id"] = "dotmac-insights"
            if self.instance_id:
                payload["hardware_fingerprint"] = self._generate_fingerprint()

            try:
                response = await self._request("POST", "/licensing/validate", json=payload)

                if not response.get("valid", False):
                    error_msg = response.get("error", "License validation failed")
                    raise LicenseInvalidError(error_msg)

                license_data = response.get("license", {})
                validation = response.get("validation_details", {})

                # Parse expiry
                expires_at = None
                if license_data.get("expires_at"):
                    expires_at = datetime.fromisoformat(
                        license_data["expires_at"].replace("Z", "+00:00")
                    )

                # Calculate grace period
                grace_period_end = None
                if expires_at:
                    grace_period_end = expires_at + timedelta(
                        hours=settings.license_grace_period_hours
                    )

                # Parse next validation time
                next_validation = None
                if validation.get("next_check_required"):
                    next_validation = datetime.fromisoformat(
                        validation["next_check_required"].replace("Z", "+00:00")
                    )

                self._license_cache = LicenseInfo(
                    license_id=license_data.get("id", ""),
                    license_key=license_data.get("license_key", payload.get("license_key", "")),
                    status=LicenseStatus(license_data.get("status", "active")),
                    license_type=LicenseType(license_data.get("type", "subscription")),
                    product_id=license_data.get("product_id", "dotmac-insights"),
                    tenant_id=license_data.get("tenant_id", self.tenant_id or ""),
                    features=license_data.get("features", {}),
                    limits=license_data.get("limits", {}),
                    max_users=license_data.get("max_users", 0),
                    expires_at=expires_at,
                    validated_at=datetime.now(timezone.utc),
                    next_validation_at=next_validation,
                    grace_period_end=grace_period_end,
                )

                logger.info(
                    "license_validated",
                    license_id=self._license_cache.license_id,
                    status=self._license_cache.status.value,
                    expires_at=str(expires_at) if expires_at else None,
                )

                return self._license_cache

            except PlatformClientError:
                raise
            except Exception as e:
                logger.error("license_validation_error", error=str(e))
                raise LicenseValidationError(f"License validation failed: {e}")

    async def validate_activation(self, activation_token: str) -> Dict[str, Any]:
        """
        Validate an activation token.

        Use this when you have an activation token instead of license key.
        """
        response = await self._request(
            "POST",
            "/licensing/activations/validate",
            json={"activation_token": activation_token},
        )

        if not response.get("valid", False):
            raise LicenseValidationError("Activation token invalid")

        return response

    def get_cached_license(self) -> Optional[LicenseInfo]:
        """Get cached license info without making API call."""
        return self._license_cache

    def _generate_fingerprint(self) -> str:
        """Generate a hardware fingerprint for this instance."""
        components = [
            self.instance_id or "",
            settings.database_url.split("@")[-1] if settings.database_url else "",
            settings.otel_service_name,
        ]
        return hashlib.sha256("|".join(components).encode()).hexdigest()[:32]

    # =========================================================================
    # TENANT & FEATURE FLAGS
    # =========================================================================

    async def get_current_tenant(self, force_refresh: bool = False) -> TenantInfo:
        """
        Get current tenant information including features and limits.

        Preferred method for feature gating.
        """
        async with self._cache_lock:
            # Check cache
            if not force_refresh and self._tenant_cache:
                cache_age = (datetime.now(timezone.utc) - self._tenant_cache.fetched_at).total_seconds()
                if cache_age < settings.feature_flags_cache_ttl_seconds:
                    return self._tenant_cache

            response = await self._request("GET", "/tenants/current")

            self._tenant_cache = TenantInfo(
                tenant_id=response.get("id", ""),
                name=response.get("name", ""),
                slug=response.get("slug", ""),
                plan=response.get("plan", ""),
                status=response.get("status", "active"),
                features=response.get("features", {}),
                limits=response.get("limits", {}),
                settings=response.get("settings", {}),
                metadata=response.get("metadata", {}),
            )

            # Update feature cache
            self._feature_cache = self._tenant_cache.features.copy()

            logger.debug(
                "tenant_info_fetched",
                tenant_id=self._tenant_cache.tenant_id,
                plan=self._tenant_cache.plan,
            )

            return self._tenant_cache

    async def check_feature_flag(
        self,
        flag_name: str,
        default: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check a feature flag.

        First checks local tenant features, then falls back to global flags.
        """
        # Check cached tenant features first
        if self._tenant_cache and flag_name in self._tenant_cache.features:
            return self._tenant_cache.features[flag_name]

        # Check feature cache
        if flag_name in self._feature_cache:
            return self._feature_cache[flag_name]

        # If platform precedence is enabled, fetch from global flags
        if settings.feature_flags_platform_precedence:
            try:
                response = await self._request(
                    "POST",
                    "/feature-flags/flags/check",
                    json={
                        "flag_key": flag_name,
                        "context": {
                            "tenant_id": self.tenant_id,
                            "instance_id": self.instance_id,
                            **(context or {}),
                        },
                    },
                )
                result = bool(response.get("enabled", default))
                self._feature_cache[flag_name] = result
                return result
            except PlatformClientError:
                pass

        return default

    def has_feature(self, feature: str) -> bool:
        """Quick sync check for a feature (uses cache only)."""
        if self._tenant_cache:
            return self._tenant_cache.features.get(feature, False)
        if self._license_cache:
            return self._license_cache.has_feature(feature)
        return False

    def get_limit(self, limit_name: str, default: int = 0) -> int:
        """Quick sync check for a limit (uses cache only)."""
        if self._tenant_cache:
            value = self._tenant_cache.limits.get(limit_name, default)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    return default
            return default
        if self._license_cache:
            return self._license_cache.get_limit(limit_name, default)
        return default

    # =========================================================================
    # USAGE REPORTING
    # =========================================================================

    async def report_usage(
        self,
        metric: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Buffer a usage metric for batch reporting.

        Metrics are batched and sent periodically to respect rate limits.
        """
        async with self._usage_lock:
            self._usage_buffer.append(UsageMetric(
                metric=metric,
                value=value,
                metadata=metadata or {},
            ))

            # Auto-flush if buffer is full
            if len(self._usage_buffer) >= settings.usage_report_batch_size:
                await self._flush_usage()

    async def _flush_usage(self) -> None:
        """Flush usage buffer to platform."""
        if not self._usage_buffer:
            return

        if not self.tenant_id:
            logger.warning("usage_flush_skipped", reason="no_tenant_id")
            return

        # Take buffer and clear
        metrics = self._usage_buffer.copy()
        self._usage_buffer.clear()

        try:
            # Format for platform API
            payload = {
                "metrics": [
                    {
                        "metric": m.metric,
                        "value": m.value,
                        "timestamp": m.timestamp.isoformat(),
                        "metadata": m.metadata,
                    }
                    for m in metrics
                ]
            }

            await self._request(
                "POST",
                f"/tenants/{self.tenant_id}/usage",
                json=payload,
            )

            self._last_usage_flush = datetime.now(timezone.utc)
            logger.debug("usage_flushed", count=len(metrics))

        except PlatformRateLimitError as e:
            # Put metrics back in buffer
            self._usage_buffer = metrics + self._usage_buffer
            logger.warning("usage_flush_rate_limited", retry_after=e.retry_after)

        except PlatformClientError as e:
            # Put metrics back in buffer
            self._usage_buffer = metrics + self._usage_buffer
            logger.error("usage_flush_error", error=str(e))

    async def flush_usage_if_needed(self) -> None:
        """Flush usage if interval has passed."""
        async with self._usage_lock:
            elapsed = (datetime.now(timezone.utc) - self._last_usage_flush).total_seconds()
            if elapsed >= settings.usage_report_interval_seconds:
                await self._flush_usage()

    # =========================================================================
    # HEALTH & HEARTBEAT
    # =========================================================================

    async def send_heartbeat(
        self,
        status: str = "healthy",
        components: Optional[Dict[str, str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send instance heartbeat to platform."""
        if not self.instance_id:
            return {"status": "skipped", "reason": "no_instance_id"}

        payload = {
            "instance_id": self.instance_id,
            "status": status,
            "version": "1.0.0",  # TODO: Get from package version
            "uptime_seconds": 0,  # TODO: Track uptime
            "metrics": metrics or {
                "active_users": 0,  # TODO: Track active users
            },
        }
        if components:
            payload["components"] = components

        try:
            response = await self._request(
                "POST",
                f"/deployment/instances/{self.instance_id}/health-check",
                json=payload,
            )
            logger.debug("heartbeat_sent")
            return response
        except PlatformClientError as e:
            logger.error("heartbeat_error", error=str(e))
            return {"status": "error", "error": str(e)}

    async def check_platform_health(self) -> bool:
        """Check if platform is reachable."""
        try:
            if not self._client:
                await self.initialize()
            if not self._client:
                raise PlatformConnectionError("Platform client not initialized")
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception:
            return False


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================


_platform_client: Optional[PlatformClient] = None


def get_platform_client() -> PlatformClient:
    """Get or create the platform client singleton."""
    global _platform_client
    if _platform_client is None:
        _platform_client = PlatformClient()
    return _platform_client


async def init_platform_client() -> PlatformClient:
    """Initialize the platform client."""
    client = get_platform_client()
    await client.initialize()
    return client


async def close_platform_client() -> None:
    """Close the platform client."""
    global _platform_client
    if _platform_client:
        await _platform_client.close()
        _platform_client = None
