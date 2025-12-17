"""
Okra Open Banking Client

Implementation of Okra API for:
- Bank account linking via Okra widget
- Account balance and transaction fetching
- Customer identity verification
- Income verification
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


class OkraClient(BaseOpenBankingProvider):
    """
    Okra open banking implementation.

    Supports:
    - Account linking via Okra widget
    - Real-time balance fetching
    - Transaction history
    - Identity verification
    - Income verification
    """

    provider = OpenBankingProvider.OKRA
    BASE_URL = "https://api.okra.ng/v2"

    def __init__(
        self,
        secret_key: Optional[str] = None,
        public_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Okra client.

        Args:
            secret_key: Okra secret key (defaults to env var)
            public_key: Okra public key for widget
            webhook_secret: Webhook signing secret
            timeout: Request timeout in seconds
        """
        settings = get_payment_settings()
        self.secret_key = secret_key or settings.okra_secret_key
        self.public_key = public_key or settings.okra_public_key
        self.webhook_secret = webhook_secret or settings.okra_webhook_secret
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError("Okra secret key is required")

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OkraClient":
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

            if response.status_code >= 400 or result.get("status") == "error":
                self._handle_error_response(result, response.status_code)

            return result

        except httpx.TimeoutException:
            logger.error(f"Okra request timeout: {method} {endpoint}")
            raise OpenBankingError(
                message="Request to Okra timed out",
                code="timeout",
                provider="okra",
            )
        except httpx.NetworkError as e:
            logger.error(f"Okra network error: {e}")
            raise OpenBankingError(
                message="Network error connecting to Okra",
                code="network_error",
                provider="okra",
            )

    def _handle_error_response(
        self, result: Dict[str, Any], status_code: int
    ) -> None:
        """Handle Okra error responses."""
        message = result.get("message", "Unknown error")
        code = result.get("code", str(status_code))

        if status_code == 401 or "reauth" in message.lower():
            raise ReauthorizationRequiredError(
                message=message, code=code, provider="okra", details=result
            )

        if status_code == 404:
            raise AccountNotFoundError(
                message=message, code=code, provider="okra", details=result
            )

        raise OpenBankingError(
            message=message, code=code, provider="okra", details=result
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Okra date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            try:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
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
        Get configuration for Okra widget.

        Returns public key and configuration needed for widget.
        """
        return {
            "public_key": self.public_key,
            "customer_id": customer_id,
            "callback_url": redirect_url,
            "metadata": metadata or {},
            "widget_url": "https://widget.okra.ng",
            "products": ["auth", "balance", "transactions", "identity"],
        }

    async def exchange_code(self, code: str) -> str:
        """
        Exchange record ID for account details.

        In Okra, the widget returns a record_id directly.
        """
        # Okra returns the record ID directly, which serves as the account ID
        # We verify it's valid by fetching account details
        try:
            result = await self._request(
                "POST",
                "/accounts/getById",
                data={"id": code},
            )
            data = result.get("data", {})
            return data.get("_id", code)
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountLinkingError(
                message=f"Failed to verify account: {str(e)}",
                provider="okra",
            )

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def get_account_details(self, account_id: str) -> LinkedAccount:
        """Get linked account details."""
        try:
            result = await self._request(
                "POST",
                "/accounts/getById",
                data={"id": account_id},
            )
            data = result.get("data", {})
            bank = data.get("bank", {})

            # Determine connection status
            status = ConnectionStatus.CONNECTED
            if data.get("reauth_required"):
                status = ConnectionStatus.REAUTHORIZATION_REQUIRED

            balance = None
            if data.get("balance") is not None:
                balance = Decimal(str(data["balance"]))

            return LinkedAccount(
                account_id=account_id,
                account_number=data.get("nuban", ""),
                bank_code=bank.get("code", ""),
                bank_name=bank.get("name", ""),
                account_name=data.get("name", ""),
                account_type=data.get("type", "").lower(),
                currency=data.get("currency", "NGN"),
                balance=balance,
                balance_date=self._parse_date(data.get("last_updated")),
                bvn=data.get("bvn"),
                connection_status=status,
            )
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get account details: {str(e)}",
                provider="okra",
            )

    async def get_account_balance(self, account_id: str) -> Decimal:
        """Get current account balance."""
        try:
            result = await self._request(
                "POST",
                "/balance/getById",
                data={"account_id": account_id},
            )
            data = result.get("data", {})

            # Okra returns balance in available_balance and ledger_balance
            available = data.get("available_balance", 0)
            return Decimal(str(available))
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get balance: {str(e)}",
                provider="okra",
            )

    async def get_transactions(
        self,
        account_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[AccountTransaction]:
        """Get account transactions."""
        payload: Dict[str, Any] = {
            "account_id": account_id,
            "limit": limit,
        }

        if start_date:
            payload["from"] = start_date.isoformat()
        if end_date:
            payload["to"] = end_date.isoformat()

        try:
            result = await self._request(
                "POST",
                "/transactions/getByAccount",
                data=payload,
            )

            transactions = []
            for txn in result.get("data", {}).get("transactions", []):
                amount = Decimal(str(abs(txn.get("amount", 0))))

                # Determine type based on amount sign or type field
                txn_type = txn.get("type", "").lower()
                if not txn_type:
                    txn_type = "credit" if txn.get("amount", 0) > 0 else "debit"

                balance = None
                if txn.get("balance") is not None:
                    balance = Decimal(str(txn["balance"]))

                transactions.append(
                    AccountTransaction(
                        transaction_id=txn.get("_id", ""),
                        date=self._parse_date(txn.get("date")) or datetime.utcnow(),
                        narration=txn.get("narration", "") or txn.get("notes", ""),
                        type=txn_type,
                        amount=amount,
                        balance=balance,
                        category=txn.get("category"),
                        reference=txn.get("ref"),
                        counterparty=txn.get("beneficiary"),
                        raw_data=txn,
                    )
                )

            return transactions
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get transactions: {str(e)}",
                provider="okra",
            )

    async def get_statement(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> AccountStatement:
        """Get account statement for a period."""
        # Get account details
        account = await self.get_account_details(account_id)

        # Get transactions for period
        transactions = await self.get_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        # Calculate balances
        closing_balance = account.balance or Decimal("0")
        total_credits = sum(t.amount for t in transactions if t.type == "credit")
        total_debits = sum(t.amount for t in transactions if t.type == "debit")
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
            result = await self._request(
                "POST",
                "/identity/getByAccount",
                data={"account_id": account_id},
            )
            data = result.get("data", {})

            # Okra may return identity in nested structure
            identity = data.get("identity", data)

            return IdentityInfo(
                bvn=identity.get("bvn"),
                full_name=identity.get("fullname", ""),
                first_name=identity.get("firstname"),
                last_name=identity.get("lastname"),
                email=identity.get("email"),
                phone=identity.get("phone"),
                date_of_birth=self._parse_dob(identity.get("dob")),
                address=identity.get("address"),
                raw_data=identity,
            )
        except OpenBankingError:
            raise
        except Exception as e:
            raise AccountSyncError(
                message=f"Failed to get identity: {str(e)}",
                provider="okra",
            )

    def _parse_dob(self, dob_str: Optional[str]) -> Optional[date]:
        """Parse date of birth string."""
        if not dob_str:
            return None
        try:
            return datetime.strptime(dob_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            try:
                return datetime.strptime(dob_str, "%d-%m-%Y").date()
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
                "/accounts/reauth",
                data={"account_id": account_id},
            )
            return result.get("data", {}).get("reauth_url", "")
        except OpenBankingError:
            raise
        except Exception as e:
            raise ReauthorizationRequiredError(
                message=f"Failed to get reauthorization URL: {str(e)}",
                provider="okra",
            )

    async def unlink_account(self, account_id: str) -> bool:
        """Unlink a connected account."""
        try:
            await self._request(
                "POST",
                "/accounts/remove",
                data={"account_id": account_id},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to unlink account: {e}")
            return False

    # =========================================================================
    # Income Verification
    # =========================================================================

    async def get_income(self, account_id: str) -> Dict[str, Any]:
        """
        Get income verification data for an account.

        Returns analyzed income patterns and verification status.
        """
        try:
            result = await self._request(
                "POST",
                "/income/getByAccount",
                data={"account_id": account_id},
            )
            return result.get("data", {})
        except Exception as e:
            logger.error(f"Failed to get income data: {e}")
            return {}

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify Okra webhook signature.

        Okra uses SHA-256 HMAC for webhook verification.
        """
        if not self.webhook_secret:
            # Fail closed in production - reject webhooks if secret not configured
            from app.config import settings
            if settings.is_production:
                logger.error(
                    "okra_webhook_secret_missing: Webhook secret not configured in production - rejecting webhook"
                )
                return False
            logger.warning("Webhook secret not configured, skipping verification (dev mode)")
            return True

        expected = hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
