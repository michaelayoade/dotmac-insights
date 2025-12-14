"""
Mono Open Banking Client

Implementation of Mono Connect API for:
- Bank account linking via Mono Connect widget
- Account balance and transaction fetching
- Customer identity verification
- Statement generation
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.integrations.payments.openbanking.base import (
    BaseOpenBankingProvider,
    LinkedAccount,
    AccountTransaction,
    AccountStatement,
    IdentityInfo,
)
from app.integrations.payments.enums import (
    OpenBankingProvider,
    ConnectionStatus,
)
from app.integrations.payments.exceptions import (
    OpenBankingError,
    AccountLinkingError,
    AccountSyncError,
    ReauthorizationRequiredError,
    AccountNotFoundError,
)
from app.integrations.payments.config import get_payment_settings

logger = logging.getLogger(__name__)


class MonoClient(BaseOpenBankingProvider):
    """
    Mono Connect open banking implementation.

    Supports:
    - Account linking via Mono Connect widget
    - Real-time balance fetching
    - Transaction history (up to 12 months)
    - Bank statement generation
    - BVN/identity verification
    """

    provider = OpenBankingProvider.MONO
    BASE_URL = "https://api.withmono.com"

    def __init__(
        self,
        secret_key: Optional[str] = None,
        public_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Mono client.

        Args:
            secret_key: Mono secret key (defaults to env var)
            public_key: Mono public key for widget
            webhook_secret: Webhook signing secret
            timeout: Request timeout in seconds
        """
        settings = get_payment_settings()
        self.secret_key = secret_key or settings.mono_secret_key
        self.public_key = public_key or settings.mono_public_key
        self.webhook_secret = webhook_secret or settings.mono_webhook_secret
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError("Mono secret key is required")

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "mono-sec-key": self.secret_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "MonoClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    # =========================================================================
    # HTTP Helpers
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated API request with retry logic."""
        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
            )

            result = response.json()

            if response.status_code >= 400:
                self._handle_error_response(result, response.status_code)

            return result

        except httpx.TimeoutException:
            logger.error(f"Mono request timeout: {method} {endpoint}")
            raise OpenBankingError(
                message="Request to Mono timed out",
                code="timeout",
                provider="mono",
            )
        except httpx.NetworkError as e:
            logger.error(f"Mono network error: {e}")
            raise OpenBankingError(
                message="Network error connecting to Mono",
                code="network_error",
                provider="mono",
            )

    def _handle_error_response(
        self, result: Dict[str, Any], status_code: int
    ) -> None:
        """Handle Mono error responses."""
        message = result.get("message", "Unknown error")
        code = result.get("code", str(status_code))

        # Check for reauthorization required
        if status_code == 401 or "reauthori" in message.lower():
            raise ReauthorizationRequiredError(
                message=message, code=code, provider="mono", details=result
            )

        if status_code == 404:
            raise AccountNotFoundError(
                message=message, code=code, provider="mono", details=result
            )

        raise OpenBankingError(
            message=message, code=code, provider="mono", details=result
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Mono date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # Account Linking
    # =========================================================================

    async def get_widget_token(
        self,
        customer_id: str,
        redirect_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get configuration for Mono Connect widget.

        Returns public key and any session data needed.
        """
        return {
            "public_key": self.public_key,
            "customer_id": customer_id,
            "redirect_url": redirect_url,
            "metadata": metadata or {},
            "widget_url": "https://connect.mono.co",
        }

    async def exchange_code(self, code: str) -> str:
        """
        Exchange authorization code for account ID.

        Args:
            code: Authorization code from Mono Connect callback

        Returns:
            Mono account ID
        """
        try:
            result = await self._request(
                "POST",
                "/account/auth",
                data={"code": code},
            )
            return result.get("id", "")
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountLinkingError(
                message=f"Failed to exchange code: {str(e)}",
                provider="mono",
            )

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def get_account_details(self, account_id: str) -> LinkedAccount:
        """Get linked account details."""
        try:
            result = await self._request("GET", f"/accounts/{account_id}")
            data = result.get("account", {})
            institution = data.get("institution", {})

            # Determine connection status
            status = ConnectionStatus.CONNECTED
            if data.get("status") == "reauthorisation_required":
                status = ConnectionStatus.REAUTHORIZATION_REQUIRED

            balance = None
            if data.get("balance") is not None:
                balance = Decimal(str(data["balance"])) / 100  # Convert from kobo

            return LinkedAccount(
                account_id=account_id,
                account_number=data.get("accountNumber", ""),
                bank_code=institution.get("bankCode", ""),
                bank_name=institution.get("name", ""),
                account_name=data.get("name", ""),
                account_type=data.get("type", "").lower(),
                currency=data.get("currency", "NGN"),
                balance=balance,
                balance_date=self._parse_date(data.get("balance_date")),
                bvn=data.get("bvn"),
                connection_status=status,
            )
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get account details: {str(e)}",
                provider="mono",
            )

    async def get_account_balance(self, account_id: str) -> Decimal:
        """Get current account balance."""
        account = await self.get_account_details(account_id)
        return account.balance or Decimal("0")

    async def get_transactions(
        self,
        account_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[AccountTransaction]:
        """Get account transactions."""
        params: Dict[str, Any] = {"paginate": False}

        if start_date:
            params["start"] = start_date.strftime("%d-%m-%Y")
        if end_date:
            params["end"] = end_date.strftime("%d-%m-%Y")

        try:
            result = await self._request(
                "GET",
                f"/accounts/{account_id}/transactions",
                params=params,
            )

            transactions = []
            for txn in result.get("data", [])[:limit]:
                amount = Decimal(str(txn.get("amount", 0))) / 100  # From kobo

                balance = None
                if txn.get("balance") is not None:
                    balance = Decimal(str(txn["balance"])) / 100

                transactions.append(
                    AccountTransaction(
                        transaction_id=txn.get("_id", ""),
                        date=self._parse_date(txn.get("date")) or datetime.utcnow(),
                        narration=txn.get("narration", ""),
                        type=txn.get("type", "").lower(),
                        amount=amount,
                        balance=balance,
                        category=txn.get("category"),
                        raw_data=txn,
                    )
                )

            return transactions
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get transactions: {str(e)}",
                provider="mono",
            )

    async def get_statement(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> AccountStatement:
        """Get account statement for a period."""
        # Get account details for opening balance estimation
        account = await self.get_account_details(account_id)

        # Get transactions for period
        transactions = await self.get_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        # Calculate balances from transactions
        closing_balance = account.balance or Decimal("0")

        # Sum credits and debits to estimate opening balance
        total_credits = sum(
            t.amount for t in transactions if t.type == "credit"
        )
        total_debits = sum(
            t.amount for t in transactions if t.type == "debit"
        )
        opening_balance = closing_balance - total_credits + total_debits

        return AccountStatement(
            account_id=account_id,
            account_number=account.account_number,
            start_date=start_date,
            end_date=end_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            transactions=transactions,
        )

    # =========================================================================
    # Identity
    # =========================================================================

    async def get_identity(self, account_id: str) -> IdentityInfo:
        """Get customer identity from linked account."""
        try:
            result = await self._request("GET", f"/accounts/{account_id}/identity")
            data = result.get("data", {})

            return IdentityInfo(
                bvn=data.get("bvn"),
                full_name=data.get("fullName", ""),
                first_name=data.get("firstName"),
                last_name=data.get("lastName"),
                email=data.get("email"),
                phone=data.get("phone"),
                date_of_birth=self._parse_dob(data.get("dateOfBirth")),
                address=data.get("address"),
                raw_data=data,
            )
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get identity: {str(e)}",
                provider="mono",
            )

    def _parse_dob(self, dob_str: Optional[str]) -> Optional[date]:
        """Parse date of birth string."""
        if not dob_str:
            return None
        try:
            return datetime.strptime(dob_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # Account Management
    # =========================================================================

    async def reauthorize(self, account_id: str) -> str:
        """Get reauthorization URL for expired connection."""
        try:
            result = await self._request(
                "POST",
                f"/accounts/{account_id}/reauthorise",
            )
            return result.get("reauthorisation_url", "")
        except OpenBankingError:
            raise
        except Exception as e:
            raise ReauthorizationRequiredError(
                message=f"Failed to get reauthorization URL: {str(e)}",
                provider="mono",
            )

    async def unlink_account(self, account_id: str) -> bool:
        """Unlink a connected account."""
        try:
            await self._request("POST", f"/accounts/{account_id}/unlink")
            return True
        except Exception as e:
            logger.error(f"Failed to unlink account: {e}")
            return False

    # =========================================================================
    # Manual Sync
    # =========================================================================

    async def sync_account(self, account_id: str) -> bool:
        """
        Trigger manual data sync for an account.

        Mono automatically syncs periodically, but this forces an immediate sync.
        """
        try:
            await self._request("POST", f"/accounts/{account_id}/sync")
            return True
        except Exception as e:
            logger.error(f"Failed to sync account: {e}")
            return False

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify Mono webhook signature.

        Mono uses HMAC-SHA512 for webhook verification.
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True

        expected = hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    # =========================================================================
    # BVN Lookup (Direct API)
    # =========================================================================

    async def lookup_bvn(self, bvn: str) -> Dict[str, Any]:
        """
        Look up BVN details directly (requires additional permissions).

        Args:
            bvn: 11-digit BVN

        Returns:
            BVN holder information
        """
        try:
            result = await self._request(
                "GET",
                "/v1/lookup/bvn",
                params={"bvn": bvn},
            )
            return result.get("data", {})
        except Exception as e:
            logger.error(f"BVN lookup failed: {e}")
            return {}
