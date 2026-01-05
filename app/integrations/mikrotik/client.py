"""
MikroTik RouterOS REST API Client

Async client for interacting with MikroTik routers via the REST API.
Supports all major resource operations: PPPoE secrets, Hotspot users,
DHCP leases, address lists, and active session management.

Usage:
    router = db.get(Router, router_id)
    async with MikroTikClient(router) as client:
        secrets = await client.get_ppp_secrets()
        await client.create_ppp_secret(name="user1", password="pass123")
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.integrations.mikrotik.exceptions import (
    MikroTikError,
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    APIError,
    ResourceNotFoundError,
    ResourceExistsError,
    RouterUnavailableError,
)

if TYPE_CHECKING:
    from app.models.router import Router

logger = logging.getLogger(__name__)


class MikroTikClient:
    """
    Async client for MikroTik RouterOS REST API.

    The REST API is available on RouterOS 7.1+ and provides a simpler
    interface than the legacy API protocol.

    Attributes:
        router: The Router model instance with connection details
        base_url: Constructed REST API base URL
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        router: Router,
        timeout: float = 10.0,
        verify_ssl: bool = False,
    ):
        """
        Initialize the MikroTik client.

        Args:
            router: Router model with ip, api_port, api_login, api_password
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates (usually False for self-signed)
        """
        self.router = router
        self.router_id = router.id
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Construct base URL
        port = router.api_port or 443
        protocol = "https" if port == 443 else "http"
        self.base_url = f"{protocol}://{router.ip}:{port}/rest"

        # Will be initialized in __aenter__
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "MikroTikClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.router.api_login or "", self.router.api_password or ""),
            verify=self.verify_ssl,
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()

    # =========================================================================
    # Core HTTP Methods
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make an authenticated API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            path: API path (e.g., "/ppp/secret")
            data: Request body for POST/PATCH
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            MikroTikError: On API errors
        """
        if not self._client:
            raise MikroTikError("Client not initialized. Use async with context manager.")

        try:
            response = await self._client.request(
                method=method,
                url=path,
                json=data,
                params=params,
            )

            # Handle response
            return self._handle_response(response)

        except httpx.TimeoutException:
            logger.error(f"MikroTik request timeout: {method} {path}", extra={"router_id": self.router_id})
            raise TimeoutError(
                f"Request timed out after {self.timeout}s",
                router_id=self.router_id,
            )
        except httpx.NetworkError as e:
            logger.error(f"MikroTik network error: {e}", extra={"router_id": self.router_id})
            raise ConnectionError(
                f"Network error connecting to router: {e}",
                router_id=self.router_id,
            )

    def _handle_response(self, response: httpx.Response) -> Any:
        """
        Handle API response and raise appropriate exceptions.

        Args:
            response: The httpx Response object

        Returns:
            Parsed JSON data

        Raises:
            Various MikroTikError subclasses based on status code
        """
        # Success responses
        if response.status_code in (200, 201):
            if response.content:
                return response.json()
            return {}

        # No content (successful delete)
        if response.status_code == 204:
            return {}

        # Error responses
        try:
            error_data = response.json() if response.content else {}
        except Exception:
            error_data = {"raw": response.text}

        error_message = error_data.get("message", error_data.get("error", "Unknown error"))
        detail = error_data.get("detail", "")
        if detail:
            error_message = f"{error_message}: {detail}"

        # Map status codes to exceptions
        if response.status_code == 401:
            raise AuthenticationError(
                "Invalid credentials or access denied",
                router_id=self.router_id,
                details=error_data,
            )

        if response.status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=404,
                router_id=self.router_id,
                details=error_data,
            )

        if response.status_code == 400:
            # Check for duplicate/exists errors
            if "already" in error_message.lower() or "exists" in error_message.lower():
                raise ResourceExistsError(
                    error_message,
                    status_code=400,
                    router_id=self.router_id,
                    details=error_data,
                )
            raise APIError(
                error_message,
                status_code=400,
                router_id=self.router_id,
                details=error_data,
            )

        if response.status_code >= 500:
            raise RouterUnavailableError(
                f"Router error: {error_message}",
                router_id=self.router_id,
                details=error_data,
            )

        # Generic error
        raise APIError(
            error_message,
            status_code=response.status_code,
            router_id=self.router_id,
            details=error_data,
        )

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """GET request - returns list of resources."""
        result = await self._request("GET", path, params=params)
        if isinstance(result, list):
            return result
        return [result] if result else []

    async def get_one(self, path: str, id: str) -> Optional[Dict[str, Any]]:
        """GET single resource by ID."""
        try:
            result = await self._request("GET", f"{path}/{quote(id, safe='')}")
            return result if isinstance(result, dict) else None
        except ResourceNotFoundError:
            return None

    async def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request - create new resource."""
        result = await self._request("POST", path, data=data)
        return result if isinstance(result, dict) else {}

    async def patch(self, path: str, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH request - update existing resource."""
        result = await self._request("PATCH", f"{path}/{quote(id, safe='')}", data=data)
        return result if isinstance(result, dict) else {}

    async def delete(self, path: str, id: str) -> bool:
        """DELETE request - remove resource."""
        await self._request("DELETE", f"{path}/{quote(id, safe='')}")
        return True

    # =========================================================================
    # Connection Test
    # =========================================================================

    async def test_connection(self) -> bool:
        """
        Test if the router is reachable and credentials are valid.

        Returns:
            True if connection successful

        Raises:
            MikroTikError: If connection fails
        """
        try:
            await self.get("/system/resource")
            return True
        except Exception as e:
            logger.warning(f"Router connection test failed: {e}", extra={"router_id": self.router_id})
            raise

    async def get_system_info(self) -> Dict[str, Any]:
        """Get router system information."""
        resources = await self.get("/system/resource")
        return resources[0] if resources else {}

    # =========================================================================
    # PPPoE Secret Management
    # =========================================================================

    async def get_ppp_secrets(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get PPPoE secrets.

        Args:
            name: Optional filter by username

        Returns:
            List of PPPoE secrets
        """
        params = {"name": name} if name else None
        return await self.get("/ppp/secret", params=params)

    async def get_ppp_secret(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single PPPoE secret by name."""
        secrets = await self.get_ppp_secrets(name=name)
        return secrets[0] if secrets else None

    async def create_ppp_secret(
        self,
        name: str,
        password: str,
        *,
        service: str = "pppoe",
        profile: str = "default",
        remote_address: Optional[str] = None,
        local_address: Optional[str] = None,
        comment: Optional[str] = None,
        disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new PPPoE secret.

        Args:
            name: Username for the PPPoE client
            password: Password for authentication
            service: Service type (pppoe, pptp, l2tp, etc.)
            profile: PPP profile to use (often "radius" for RADIUS auth)
            remote_address: IP address to assign to client
            local_address: Local IP for the PPP link
            comment: Optional comment (used for tracking)
            disabled: Whether the secret is disabled

        Returns:
            Created secret data
        """
        data: Dict[str, Any] = {
            "name": name,
            "password": password,
            "service": service,
            "profile": profile,
            "disabled": "yes" if disabled else "no",
        }

        if remote_address:
            data["remote-address"] = remote_address
        if local_address:
            data["local-address"] = local_address
        if comment:
            data["comment"] = comment

        return await self.post("/ppp/secret", data)

    async def update_ppp_secret(
        self,
        id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Update an existing PPPoE secret.

        Args:
            id: The MikroTik internal ID (.id field)
            **kwargs: Fields to update

        Returns:
            Updated secret data
        """
        # Convert Python names to MikroTik format
        data = {}
        field_mapping = {
            "remote_address": "remote-address",
            "local_address": "local-address",
        }
        for key, value in kwargs.items():
            mk_key = field_mapping.get(key, key)
            if key == "disabled":
                data[mk_key] = "yes" if value else "no"
            else:
                data[mk_key] = value

        return await self.patch("/ppp/secret", id, data)

    async def delete_ppp_secret(self, name: str) -> bool:
        """
        Delete a PPPoE secret by name.

        Args:
            name: Username to delete

        Returns:
            True if deleted
        """
        secret = await self.get_ppp_secret(name)
        if secret and ".id" in secret:
            return await self.delete("/ppp/secret", secret[".id"])
        return False

    async def disable_ppp_secret(self, name: str) -> bool:
        """Disable a PPPoE secret (soft delete)."""
        secret = await self.get_ppp_secret(name)
        if secret and ".id" in secret:
            await self.update_ppp_secret(secret[".id"], disabled=True)
            return True
        return False

    async def enable_ppp_secret(self, name: str) -> bool:
        """Enable a disabled PPPoE secret."""
        secret = await self.get_ppp_secret(name)
        if secret and ".id" in secret:
            await self.update_ppp_secret(secret[".id"], disabled=False)
            return True
        return False

    # =========================================================================
    # PPP Active Sessions
    # =========================================================================

    async def get_ppp_active(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active PPP connections."""
        params = {"name": name} if name else None
        return await self.get("/ppp/active", params=params)

    async def disconnect_ppp_session(self, name: str) -> bool:
        """
        Disconnect an active PPP session.

        Args:
            name: Username of the session to disconnect

        Returns:
            True if session was disconnected
        """
        sessions = await self.get_ppp_active(name=name)
        if sessions:
            for session in sessions:
                if ".id" in session:
                    await self.delete("/ppp/active", session[".id"])
            return True
        return False

    # =========================================================================
    # Hotspot User Management
    # =========================================================================

    async def get_hotspot_users(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get hotspot users."""
        params = {"name": name} if name else None
        return await self.get("/ip/hotspot/user", params=params)

    async def get_hotspot_user(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single hotspot user by name."""
        users = await self.get_hotspot_users(name=name)
        return users[0] if users else None

    async def create_hotspot_user(
        self,
        name: str,
        password: str,
        *,
        profile: str = "default",
        address: Optional[str] = None,
        mac_address: Optional[str] = None,
        comment: Optional[str] = None,
        disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new hotspot user.

        Args:
            name: Username
            password: Password
            profile: Hotspot profile to use
            address: IP address to bind
            mac_address: MAC address to bind
            comment: Optional comment
            disabled: Whether user is disabled

        Returns:
            Created user data
        """
        data: Dict[str, Any] = {
            "name": name,
            "password": password,
            "profile": profile,
            "disabled": "yes" if disabled else "no",
        }

        if address:
            data["address"] = address
        if mac_address:
            data["mac-address"] = mac_address
        if comment:
            data["comment"] = comment

        return await self.post("/ip/hotspot/user", data)

    async def delete_hotspot_user(self, name: str) -> bool:
        """Delete a hotspot user by name."""
        user = await self.get_hotspot_user(name)
        if user and ".id" in user:
            return await self.delete("/ip/hotspot/user", user[".id"])
        return False

    async def get_hotspot_active(self, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active hotspot sessions."""
        params = {"user": user} if user else None
        return await self.get("/ip/hotspot/active", params=params)

    async def disconnect_hotspot_session(self, user: str) -> bool:
        """Disconnect an active hotspot session."""
        sessions = await self.get_hotspot_active(user=user)
        if sessions:
            for session in sessions:
                if ".id" in session:
                    await self.delete("/ip/hotspot/active", session[".id"])
            return True
        return False

    # =========================================================================
    # DHCP Lease Management
    # =========================================================================

    async def get_dhcp_leases(
        self,
        mac_address: Optional[str] = None,
        address: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get DHCP leases."""
        params = {}
        if mac_address:
            params["mac-address"] = mac_address
        if address:
            params["address"] = address
        return await self.get("/ip/dhcp-server/lease", params=params or None)

    async def get_dhcp_lease(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """Get a DHCP lease by MAC address."""
        leases = await self.get_dhcp_leases(mac_address=mac_address)
        return leases[0] if leases else None

    async def create_dhcp_static(
        self,
        mac_address: str,
        address: str,
        *,
        server: str = "default",
        comment: Optional[str] = None,
        always_broadcast: bool = True,
        disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a static DHCP lease (binding).

        Args:
            mac_address: MAC address to bind
            address: IP address to assign
            server: DHCP server name
            comment: Optional comment
            always_broadcast: Whether to always broadcast
            disabled: Whether binding is disabled

        Returns:
            Created lease data
        """
        data: Dict[str, Any] = {
            "mac-address": mac_address,
            "address": address,
            "server": server,
            "always-broadcast": "yes" if always_broadcast else "no",
            "disabled": "yes" if disabled else "no",
        }

        if comment:
            data["comment"] = comment

        return await self.post("/ip/dhcp-server/lease", data)

    async def delete_dhcp_lease(self, mac_address: str) -> bool:
        """Delete a DHCP lease by MAC address."""
        lease = await self.get_dhcp_lease(mac_address)
        if lease and ".id" in lease:
            return await self.delete("/ip/dhcp-server/lease", lease[".id"])
        return False

    # =========================================================================
    # Firewall Address List Management
    # =========================================================================

    async def get_address_list_entries(
        self,
        list_name: str,
        address: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get entries in an address list."""
        params = {"list": list_name}
        if address:
            params["address"] = address
        return await self.get("/ip/firewall/address-list", params=params)

    async def add_to_address_list(
        self,
        list_name: str,
        address: str,
        *,
        comment: Optional[str] = None,
        timeout: Optional[str] = None,
        disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Add an IP to an address list.

        Args:
            list_name: Name of the address list
            address: IP address or subnet
            comment: Optional comment
            timeout: Optional timeout (e.g., "1d", "1h")
            disabled: Whether entry is disabled

        Returns:
            Created entry data
        """
        data: Dict[str, Any] = {
            "list": list_name,
            "address": address,
            "disabled": "yes" if disabled else "no",
        }

        if comment:
            data["comment"] = comment
        if timeout:
            data["timeout"] = timeout

        return await self.post("/ip/firewall/address-list", data)

    async def remove_from_address_list(self, list_name: str, address: str) -> bool:
        """Remove an IP from an address list."""
        entries = await self.get_address_list_entries(list_name, address=address)
        if entries:
            for entry in entries:
                if ".id" in entry:
                    await self.delete("/ip/firewall/address-list", entry[".id"])
            return True
        return False

    # =========================================================================
    # Simple Queue Management (for bandwidth limiting without RADIUS)
    # =========================================================================

    async def get_simple_queues(self, target: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get simple queues."""
        params = {"target": target} if target else None
        return await self.get("/queue/simple", params=params)

    async def create_simple_queue(
        self,
        name: str,
        target: str,
        max_limit: str,
        *,
        comment: Optional[str] = None,
        disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a simple queue for bandwidth limiting.

        Args:
            name: Queue name
            target: Target IP or subnet
            max_limit: Max rate (e.g., "10M/5M" for 10M down, 5M up)
            comment: Optional comment
            disabled: Whether queue is disabled

        Returns:
            Created queue data
        """
        data: Dict[str, Any] = {
            "name": name,
            "target": target,
            "max-limit": max_limit,
            "disabled": "yes" if disabled else "no",
        }

        if comment:
            data["comment"] = comment

        return await self.post("/queue/simple", data)

    async def delete_simple_queue(self, name: str) -> bool:
        """Delete a simple queue by name."""
        queues = await self.get_simple_queues()
        for queue in queues:
            if queue.get("name") == name and ".id" in queue:
                return await self.delete("/queue/simple", queue[".id"])
        return False
