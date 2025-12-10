from __future__ import annotations

import httpx
import hashlib
import time
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient, CircuitBreakerOpenError
from app.models.sync_log import SyncSource
from app.sync.splynx_parts.locations import sync_locations
from app.sync.splynx_parts.customers import sync_customers
from app.sync.splynx_parts.services import sync_services
from app.sync.splynx_parts.invoices import sync_invoices
from app.sync.splynx_parts.payments import sync_payments
from app.sync.splynx_parts.credit_notes import sync_credit_notes
from app.sync.splynx_parts.tickets import sync_tickets
from app.sync.splynx_parts.tariffs import sync_tariffs
from app.sync.splynx_parts.routers import sync_routers
from app.sync.splynx_parts.customer_notes import sync_customer_notes
from app.sync.splynx_parts.administrators import sync_administrators
from app.sync.splynx_parts.network_monitors import sync_network_monitors
from app.sync.splynx_parts.leads import sync_leads
from app.sync.splynx_parts.ipv4_addresses import sync_ipv4_addresses
from app.sync.splynx_parts.ticket_messages import sync_ticket_messages
from app.sync.splynx_parts.transaction_categories import sync_transaction_categories
from app.sync.splynx_parts.ipv4_networks import sync_ipv4_networks
from app.sync.splynx_parts.ipv6_networks import sync_ipv6_networks
from app.sync.splynx_parts.payment_methods import sync_payment_methods

logger = structlog.get_logger()


class SplynxSync(BaseSyncClient):
    """Sync client for Splynx ISP billing system."""

    source = SyncSource.SPLYNX

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.splynx_api_url.rstrip("/")
        self.api_key = settings.splynx_api_key
        self.api_secret = settings.splynx_api_secret
        self.auth_basic = settings.splynx_auth_basic  # Base64 encoded credentials
        self.access_token: Optional[str] = None
        self.token_expires: Optional[float] = None

        # Determine auth method: Basic Auth takes priority if set
        self.use_basic_auth = bool(self.auth_basic)

    def _generate_signature(self, nonce: str) -> str:
        """Generate HMAC signature for Splynx API authentication."""
        message = f"{nonce}{self.api_key}"
        signature = hashlib.sha256(
            (message + self.api_secret).encode()
        ).hexdigest()
        return signature

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for Basic Auth."""
        return {
            "Authorization": f"Basic {self.auth_basic}",
            "Content-Type": "application/json",
        }

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        """Get or refresh access token (for token-based auth)."""
        if self.access_token and self.token_expires and time.time() < self.token_expires:
            return self.access_token

        nonce = str(int(time.time() * 1000))
        signature = self._generate_signature(nonce)

        response = await client.post(
            f"{self.base_url}/admin/auth/tokens",
            json={
                "auth_type": "api_key",
                "key": self.api_key,
                "signature": signature,
                "nonce": nonce,
            },
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data.get("access_token")
        # Token typically expires in 1 hour, refresh 5 min early
        self.token_expires = time.time() + 3300

        return self.access_token

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make authenticated request to Splynx API with circuit breaker protection."""
        # Check circuit breaker before making request
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker for {self.source.value} is open"
            )

        if self.use_basic_auth:
            headers = self._get_auth_headers()
        else:
            token = await self._get_access_token(client)
            headers = {"Authorization": f"Splynx-EA (access_token={token})"}

        url = f"{self.base_url}{endpoint}"
        logger.debug("splynx_request", method=method, url=url, params=params)

        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
            )

            if response.status_code != 200:
                logger.error(
                    "splynx_request_failed",
                    status=response.status_code,
                    url=url,
                    response_text=response.text[:500] if response.text else None,
                )

            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure(e)
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all records with pagination."""
        all_records = []
        page = 0
        per_page = 100
        seen_ids = set()
        max_pages = 1000  # safety guard to avoid infinite loops if API ignores pagination params

        while True:
            request_params = {"page": page, "per_page": per_page, **(params or {})}
            data = await self._request(client, "GET", endpoint, params=request_params)

            if not data:
                break

            # Avoid infinite loops if the API returns the same page repeatedly
            new_items = []
            for item in data:
                item_id = item.get("id")
                if item_id is None or item_id not in seen_ids:
                    new_items.append(item)
                    if item_id is not None:
                        seen_ids.add(item_id)

            if not new_items:
                logger.warning(
                    "splynx_pagination_repeat",
                    endpoint=endpoint,
                    page=page,
                    per_page=per_page,
                    seen=len(seen_ids),
                )
                break

            all_records.extend(new_items)
            self.increment_fetched(len(new_items))

            if len(data) < per_page:
                break

            page += 1
            if page >= max_pages:
                logger.warning(
                    "splynx_pagination_max_pages_reached",
                    endpoint=endpoint,
                    pages=max_pages,
                )
                break

        return all_records

    async def test_connection(self) -> bool:
        """Test if Splynx API connection is working."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if not self.use_basic_auth:
                    await self._get_access_token(client)
                # Try to fetch a small amount of data
                result = await self._request(client, "GET", "/admin/customers/customer", params={"per_page": 1})
                logger.info("splynx_connection_test_success", records_found=len(result) if isinstance(result, list) else 1)
            return True
        except Exception as e:
            logger.error("splynx_connection_test_failed", error=str(e))
            return False

    async def sync_all(self, full_sync: bool = False):
        """Sync all entities from Splynx."""
        # Use longer timeout for large data syncs (5 minutes per request)
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_locations(self, client, full_sync)
            await sync_customers(self, client, full_sync)
            await sync_services(self, client, full_sync)
            await sync_invoices(self, client, full_sync)
            await sync_payments(self, client, full_sync)
            await sync_credit_notes(self, client, full_sync)
            await sync_tickets(self, client, full_sync)
            await sync_tariffs(self, client, full_sync)
            await sync_routers(self, client, full_sync)
            await sync_customer_notes(self, client, full_sync)
            await sync_administrators(self, client, full_sync)
            await sync_network_monitors(self, client, full_sync)
            await sync_leads(self, client, full_sync)
            await sync_ipv4_addresses(self, client, full_sync)
            await sync_ticket_messages(self, client, full_sync)
            await sync_transaction_categories(self, client, full_sync)
            await sync_ipv4_networks(self, client, full_sync)
            await sync_ipv6_networks(self, client, full_sync)
            await sync_payment_methods(self, client, full_sync)

    # Individual task methods for Celery (create their own HTTP clients)
    async def sync_customers_task(self, full_sync: bool = False):
        """Sync customers - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_locations(self, client, full_sync)  # Sync locations first for FK
            await sync_customers(self, client, full_sync)

    async def sync_invoices_task(self, full_sync: bool = False):
        """Sync invoices - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_invoices(self, client, full_sync)

    async def sync_payments_task(self, full_sync: bool = False):
        """Sync payments - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_payments(self, client, full_sync)

    async def sync_services_task(self, full_sync: bool = False):
        """Sync services - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_services(self, client, full_sync)

    async def sync_credit_notes_task(self, full_sync: bool = False):
        """Sync credit notes - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_credit_notes(self, client, full_sync)

    async def sync_tickets_task(self, full_sync: bool = False):
        """Sync tickets - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_tickets(self, client, full_sync)

    async def sync_tariffs_task(self, full_sync: bool = False):
        """Sync tariffs - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_tariffs(self, client, full_sync)

    async def sync_routers_task(self, full_sync: bool = False):
        """Sync routers - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_routers(self, client, full_sync)

    async def sync_customer_notes_task(self, full_sync: bool = False):
        """Sync customer notes - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_customer_notes(self, client, full_sync)

    async def sync_administrators_task(self, full_sync: bool = False):
        """Sync administrators - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_administrators(self, client, full_sync)

    async def sync_network_monitors_task(self, full_sync: bool = False):
        """Sync network monitors - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_network_monitors(self, client, full_sync)

    async def sync_leads_task(self, full_sync: bool = False):
        """Sync leads - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_leads(self, client, full_sync)

    async def sync_ipv4_addresses_task(self, full_sync: bool = False):
        """Sync IPv4 addresses - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_ipv4_addresses(self, client, full_sync)

    async def sync_ticket_messages_task(self, full_sync: bool = False):
        """Sync ticket messages - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_ticket_messages(self, client, full_sync)

    async def sync_transaction_categories_task(self, full_sync: bool = False):
        """Sync transaction categories - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_transaction_categories(self, client, full_sync)

    async def sync_ipv4_networks_task(self, full_sync: bool = False):
        """Sync IPv4 networks - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_ipv4_networks(self, client, full_sync)

    async def sync_ipv6_networks_task(self, full_sync: bool = False):
        """Sync IPv6 networks - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_ipv6_networks(self, client, full_sync)

    async def sync_payment_methods_task(self, full_sync: bool = False):
        """Sync payment methods - standalone task version."""
        async with httpx.AsyncClient(timeout=300) as client:
            await sync_payment_methods(self, client, full_sync)
