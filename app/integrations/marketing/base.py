"""Base client and helpers for marketing integrations."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.sync.base import CircuitBreaker, get_circuit_breaker
from app.config import settings
from app.integrations.marketing.webhooks import verify_hmac_signature


class MarketingClientError(Exception):
    """Base exception for marketing integration errors."""


class BaseMarketingClient:
    base_url: str
    platform: str

    def __init__(
        self,
        access_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._circuit_breaker: CircuitBreaker = get_circuit_breaker(f"marketing:{self.platform}")

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BaseMarketingClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def request(self, method: str, path: str, payload: Optional[dict] = None) -> httpx.Response:
        if self._circuit_breaker.is_open():
            raise MarketingClientError(f"Circuit open for {self.platform}")
        url = f"{self.base_url}{path}"
        try:
            response = await self._client.request(method, url, json=payload, headers=self._headers())
            response.raise_for_status()
            self._circuit_breaker.record_success()
            return response
        except httpx.HTTPError as exc:
            self._circuit_breaker.record_failure(exc)
            raise MarketingClientError(str(exc)) from exc

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return False
        return verify_hmac_signature(self.webhook_secret, payload, signature)
