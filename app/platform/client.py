"""
Platform Client

Lightweight HTTP client for talking to dotmac-platform-services with
retry/backoff and a simple circuit breaker. All calls are best-effort and
fail-open to avoid taking down the app if the control plane is unreachable.
"""
from __future__ import annotations

import random
import time
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Minimal circuit breaker with failure threshold and timeout."""

    def __init__(self, threshold: int, timeout: int):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.open_until: float = 0

    def allow(self) -> bool:
        now = time.time()
        if self.open_until > now:
            return False
        if self.open_until and now >= self.open_until:
            self.reset()
        return True

    def record_success(self) -> None:
        self.reset()

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.timeout
            logger.warning(
                "platform_circuit_opened",
                threshold=self.threshold,
                timeout=self.timeout,
            )

    def reset(self) -> None:
        self.failures = 0
        self.open_until = 0


class PlatformClient:
    """HTTP client for platform-services with retry/backoff and circuit breaker."""

    def __init__(self):
        self.base_url = (settings.platform_api_url or "").rstrip("/")
        self.api_key = settings.platform_api_key or ""
        self.timeout = settings.platform_client_timeout_seconds
        self.max_retries = settings.platform_client_max_retries
        self.retry_min = settings.platform_client_retry_min_wait
        self.retry_max = settings.platform_client_retry_max_wait
        self.circuit = CircuitBreaker(
            settings.platform_client_circuit_breaker_threshold,
            settings.platform_client_circuit_breaker_timeout,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, json: Optional[dict] = None) -> Optional[httpx.Response]:
        if not self.base_url:
            return None
        if not self.circuit.allow():
            logger.warning("platform_circuit_open", path=path)
            return None

        url = f"{self.base_url}{path}"
        attempt = 0
        backoff = self.retry_min

        while attempt <= self.max_retries:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.request(method, url, headers=self._headers(), json=json)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
                self.circuit.record_success()
                return resp
            except Exception as exc:  # noqa: BLE001
                attempt += 1
                self.circuit.record_failure()
                if attempt > self.max_retries:
                    logger.error("platform_request_failed", method=method, url=url, error=str(exc))
                    return None
                # Add jitter (±25%) to avoid thundering herd
                base_sleep = min(backoff, self.retry_max)
                jitter = base_sleep * 0.25 * (2 * random.random() - 1)  # ±25%
                sleep_for = max(0.1, base_sleep + jitter)
                logger.warning("platform_request_retry", attempt=attempt, url=url, wait=sleep_for, error=str(exc))
                time.sleep(sleep_for)
                backoff = min(backoff * 2, self.retry_max)
        return None

    def get_json(self, path: str) -> Optional[Any]:
        resp = self._request("GET", path)
        if resp and resp.content:
            try:
                return resp.json()
            except Exception:
                logger.error("platform_response_parse_error", path=path)
        return None

    def post_json(self, path: str, payload: dict) -> Optional[Any]:
        resp = self._request("POST", path, json=payload)
        if resp and resp.content:
            try:
                return resp.json()
            except Exception:
                logger.error("platform_response_parse_error", path=path)
        return None


# Singleton client
platform_client = PlatformClient()

