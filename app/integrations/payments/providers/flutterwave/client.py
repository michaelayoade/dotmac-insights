"""
Flutterwave Payment Gateway Client

Full implementation of Flutterwave (Rave) API for:
- Payment initialization and verification
- Recurring charges via tokenized cards
- Bank transfers (single and bulk)
- Virtual account creation
- Bank account resolution
- Webhook signature verification
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.integrations.payments.base import (
    BasePaymentGateway,
    InitializePaymentRequest,
    InitializePaymentResponse,
    PaymentVerificationResult,
    TransferRecipient,
    TransferRequest,
    TransferResult,
    BankInfo,
    AccountInfo,
    VirtualAccountRequest,
    VirtualAccountResponse,
)
from app.integrations.payments.enums import (
    PaymentProvider,
    TransactionStatus,
)
from app.integrations.payments.exceptions import (
    PaymentError,
    PaymentInitializationError,
    PaymentVerificationError,
    TransferError,
    TransferRecipientError,
    AccountResolutionError,
    VirtualAccountError,
    RefundError,
    ProviderUnavailableError,
    InsufficientBalanceError,
)
from app.integrations.payments.config import get_payment_settings

logger = logging.getLogger(__name__)


class FlutterwaveClient(BasePaymentGateway):
    """
    Flutterwave (Rave) payment gateway implementation.

    Supports:
    - Card payments
    - Bank transfers
    - USSD payments
    - Mobile money
    - Virtual accounts for collections
    - Recurring payments via card tokens
    - Payouts/transfers to bank accounts
    """

    provider = PaymentProvider.FLUTTERWAVE
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(
        self,
        secret_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        encryption_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Flutterwave client.

        Args:
            secret_key: Flutterwave secret key (defaults to env var)
            webhook_secret: Webhook signing secret (defaults to env var)
            encryption_key: Encryption key for card tokenization
            timeout: Request timeout in seconds
        """
        settings = get_payment_settings()
        self.secret_key = secret_key or settings.flutterwave_secret_key
        self.webhook_secret = webhook_secret or settings.flutterwave_webhook_secret
        self.encryption_key = encryption_key or settings.flutterwave_encryption_key
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError("Flutterwave secret key is required")

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

    async def __aenter__(self) -> "FlutterwaveClient":
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

            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    message=result.get("message", "Flutterwave service unavailable"),
                    code="service_unavailable",
                    provider="flutterwave",
                    details=result,
                )

            if response.status_code >= 400 or result.get("status") == "error":
                self._handle_error_response(result, response.status_code)

            return result

        except httpx.TimeoutException:
            logger.error(f"Flutterwave request timeout: {method} {endpoint}")
            raise ProviderUnavailableError(
                message="Request to Flutterwave timed out",
                code="timeout",
                provider="flutterwave",
            )
        except httpx.NetworkError as e:
            logger.error(f"Flutterwave network error: {e}")
            raise ProviderUnavailableError(
                message="Network error connecting to Flutterwave",
                code="network_error",
                provider="flutterwave",
            )

    def _handle_error_response(
        self, result: Dict[str, Any], status_code: int
    ) -> None:
        """Handle Flutterwave error responses."""
        message = result.get("message", "Unknown error")
        code = result.get("code", str(status_code))

        if "insufficient" in message.lower():
            raise InsufficientBalanceError(
                message=message, code=code, provider="flutterwave", details=result
            )

        raise PaymentError(
            message=message, code=code, provider="flutterwave", details=result
        )

    def _parse_status(self, status: str) -> TransactionStatus:
        """Map Flutterwave status to our enum."""
        status_map = {
            "successful": TransactionStatus.SUCCESS,
            "success": TransactionStatus.SUCCESS,
            "failed": TransactionStatus.FAILED,
            "pending": TransactionStatus.PENDING,
            "new": TransactionStatus.PENDING,
        }
        return status_map.get(status.lower(), TransactionStatus.PENDING)

    # =========================================================================
    # Payment Operations
    # =========================================================================

    async def initialize_payment(
        self, request: InitializePaymentRequest
    ) -> InitializePaymentResponse:
        """Initialize a payment transaction using Flutterwave Standard."""
        payload = {
            "tx_ref": request.reference,
            "amount": float(request.amount),
            "currency": request.currency,
            "customer": {
                "email": request.email,
            },
        }

        if request.callback_url:
            payload["redirect_url"] = request.callback_url
        if request.metadata:
            payload["meta"] = request.metadata
        if request.channels:
            # Flutterwave uses payment_options
            payload["payment_options"] = ",".join(request.channels)

        try:
            result = await self._request("POST", "/payments", data=payload)
            data = result.get("data", {})

            return InitializePaymentResponse(
                authorization_url=data["link"],
                access_code=data.get("id", request.reference),
                reference=request.reference,
                provider=self.provider,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentInitializationError(
                message=f"Failed to initialize payment: {str(e)}",
                provider="flutterwave",
            )

    async def verify_payment(self, reference: str) -> PaymentVerificationResult:
        """Verify a payment by transaction reference."""
        try:
            # Flutterwave uses transaction ID for verification
            # First, we need to get the transaction by tx_ref
            result = await self._request(
                "GET", f"/transactions/verify_by_reference",
                params={"tx_ref": reference}
            )
            data = result.get("data", {})

            paid_at = None
            if data.get("created_at"):
                try:
                    paid_at = datetime.fromisoformat(
                        data["created_at"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            return PaymentVerificationResult(
                reference=data.get("tx_ref", reference),
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=Decimal(str(data["amount"])),
                currency=data["currency"],
                paid_at=paid_at,
                channel=data.get("payment_type"),
                fees=Decimal(str(data.get("app_fee", 0))),
                metadata=data.get("meta"),
                customer_email=data.get("customer", {}).get("email"),
                customer_code=data.get("customer", {}).get("id"),
                authorization=data.get("card"),  # Card token for recurring
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentVerificationError(
                message=f"Failed to verify payment: {str(e)}",
                provider="flutterwave",
            )

    async def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: Decimal,
        reference: str,
        currency: str = "NGN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentVerificationResult:
        """Charge a tokenized card for recurring payments."""
        payload = {
            "token": authorization_code,
            "email": email,
            "amount": float(amount),
            "tx_ref": reference,
            "currency": currency,
        }

        if metadata:
            payload["meta"] = metadata

        try:
            result = await self._request(
                "POST", "/tokenized-charges", data=payload
            )
            data = result.get("data", {})

            return PaymentVerificationResult(
                reference=reference,
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=Decimal(str(data["amount"])),
                currency=data["currency"],
                paid_at=datetime.utcnow() if data["status"] == "successful" else None,
                channel="card",
                fees=Decimal(str(data.get("app_fee", 0))),
                customer_email=email,
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentVerificationError(
                message=f"Failed to charge token: {str(e)}",
                provider="flutterwave",
            )

    async def refund_payment(
        self,
        reference: str,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Refund a payment (full or partial)."""
        # Get the transaction first
        verification = await self.verify_payment(reference)

        payload = {}
        if amount is not None:
            payload["amount"] = float(amount)

        try:
            result = await self._request(
                "POST",
                f"/transactions/{verification.provider_reference}/refund",
                data=payload if payload else None,
            )
            return result.get("data", {})
        except PaymentError:
            raise
        except Exception as e:
            raise RefundError(
                message=f"Failed to refund payment: {str(e)}",
                provider="flutterwave",
            )

    # =========================================================================
    # Transfer Operations
    # =========================================================================

    async def create_transfer_recipient(
        self, recipient: TransferRecipient
    ) -> str:
        """
        Create a transfer beneficiary.
        Flutterwave doesn't require pre-registering beneficiaries,
        but we can validate the account.
        """
        # Resolve account to validate
        await self.resolve_account(recipient.account_number, recipient.bank_code)

        # Return a synthetic code (account_number:bank_code)
        return f"{recipient.account_number}:{recipient.bank_code}"

    async def initiate_transfer(
        self, request: TransferRequest
    ) -> TransferResult:
        """Initiate a bank transfer (payout)."""
        payload = {
            "account_bank": request.recipient.bank_code,
            "account_number": request.recipient.account_number,
            "amount": float(request.amount),
            "currency": request.currency,
            "reference": request.reference,
            "debit_currency": request.currency,
        }

        if request.narration:
            payload["narration"] = request.narration

        if request.metadata:
            payload["meta"] = request.metadata

        try:
            result = await self._request("POST", "/transfers", data=payload)
            data = result.get("data", {})

            return TransferResult(
                reference=data.get("reference", request.reference),
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=Decimal(str(data["amount"])),
                currency=data["currency"],
                recipient_code=f"{request.recipient.account_number}:{request.recipient.bank_code}",
                transfer_code=data.get("bank_name"),
                fee=Decimal(str(data.get("fee", 0))),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to initiate transfer: {str(e)}",
                provider="flutterwave",
            )

    async def verify_transfer(self, reference: str) -> TransferResult:
        """Verify a transfer by fetching its status."""
        try:
            # First get transfer by reference
            result = await self._request(
                "GET", "/transfers",
                params={"reference": reference}
            )
            transfers = result.get("data", [])

            if not transfers:
                raise TransferError(
                    message="Transfer not found",
                    provider="flutterwave",
                )

            data = transfers[0]

            return TransferResult(
                reference=data.get("reference", reference),
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=Decimal(str(data["amount"])),
                currency=data["currency"],
                recipient_code=f"{data.get('account_number', '')}:{data.get('bank_code', '')}",
                transfer_code=data.get("bank_name"),
                fee=Decimal(str(data.get("fee", 0))),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to verify transfer: {str(e)}",
                provider="flutterwave",
            )

    async def initiate_bulk_transfer(
        self, transfers: List[TransferRequest]
    ) -> List[TransferResult]:
        """Initiate multiple transfers in a batch."""
        bulk_data = []

        for transfer in transfers:
            bulk_data.append({
                "bank_code": transfer.recipient.bank_code,
                "account_number": transfer.recipient.account_number,
                "amount": float(transfer.amount),
                "currency": transfer.currency,
                "reference": transfer.reference,
                "narration": transfer.narration or "",
            })

        payload = {
            "title": f"Bulk Transfer {datetime.utcnow().isoformat()}",
            "bulk_data": bulk_data,
        }

        try:
            result = await self._request("POST", "/bulk-transfers", data=payload)
            data = result.get("data", {})

            # Bulk returns a single response, we map to individual results
            results = []
            for i, transfer in enumerate(transfers):
                results.append(
                    TransferResult(
                        reference=transfer.reference,
                        provider_reference=str(data.get("id", "")),
                        status=TransactionStatus.PENDING,
                        amount=transfer.amount,
                        currency=transfer.currency,
                        recipient_code=f"{transfer.recipient.account_number}:{transfer.recipient.bank_code}",
                        raw_response=data,
                    )
                )

            return results
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to initiate bulk transfer: {str(e)}",
                provider="flutterwave",
            )

    # =========================================================================
    # Bank Operations
    # =========================================================================

    async def get_banks(self, country: str = "NG") -> List[BankInfo]:
        """Get list of supported banks."""
        try:
            result = await self._request("GET", f"/banks/{country}")
            banks = []

            for bank in result.get("data", []):
                banks.append(
                    BankInfo(
                        code=bank["code"],
                        name=bank["name"],
                        slug=bank.get("slug", bank["code"].lower()),
                        is_active=True,
                        country=country,
                        currency="NGN" if country == "NG" else "USD",
                    )
                )

            return banks
        except Exception as e:
            logger.error(f"Failed to get banks: {e}")
            return []

    async def resolve_account(
        self, account_number: str, bank_code: str
    ) -> AccountInfo:
        """Resolve/verify a bank account."""
        payload = {
            "account_number": account_number,
            "account_bank": bank_code,
        }

        try:
            result = await self._request("POST", "/accounts/resolve", data=payload)
            data = result.get("data", {})

            return AccountInfo(
                account_number=data["account_number"],
                account_name=data["account_name"],
                bank_code=bank_code,
                bank_name=data.get("bank_name"),
            )
        except PaymentError:
            raise
        except Exception as e:
            raise AccountResolutionError(
                message=f"Failed to resolve account: {str(e)}",
                provider="flutterwave",
            )

    # =========================================================================
    # Virtual Account Operations
    # =========================================================================

    async def create_virtual_account(
        self, request: VirtualAccountRequest
    ) -> VirtualAccountResponse:
        """Create a virtual account for collections."""
        # Split name for Flutterwave
        name_parts = request.customer_name.split() if request.customer_name else ["Customer"]
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else first_name

        payload = {
            "email": request.customer_email,
            "is_permanent": request.is_permanent,
            "bvn": request.bvn or "",
            "firstname": first_name,
            "lastname": last_name,
            "narration": f"VA for {request.customer_email}",
        }

        if request.expected_amount:
            payload["amount"] = float(request.expected_amount)

        try:
            result = await self._request(
                "POST", "/virtual-account-numbers", data=payload
            )
            data = result.get("data", {})

            return VirtualAccountResponse(
                account_number=data["account_number"],
                account_name=data.get("account_name", request.customer_name),
                bank_name=data["bank_name"],
                bank_code=data.get("bank_code", ""),
                provider_reference=data.get("order_ref", ""),
                provider=self.provider,
                is_permanent=request.is_permanent,
                expires_at=request.expires_at,
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise VirtualAccountError(
                message=f"Failed to create virtual account: {str(e)}",
                provider="flutterwave",
            )

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify Flutterwave webhook signature.

        Flutterwave uses a secret hash in the verifi-hash header.
        """
        if not self.webhook_secret:
            # Fail closed in production - reject webhooks if secret not configured
            from app.config import settings
            if settings.is_production:
                logger.error(
                    "flutterwave_webhook_secret_missing: Webhook secret not configured in production - rejecting webhook"
                )
                return False
            logger.warning("Webhook secret not configured, skipping verification (dev mode)")
            return True

        return hmac.compare_digest(self.webhook_secret, signature)

    # =========================================================================
    # Balance & Account Info
    # =========================================================================

    async def get_balance(self, currency: str = "NGN") -> Dict[str, Decimal]:
        """Get available balance."""
        try:
            result = await self._request("GET", f"/balances/{currency}")
            data = result.get("data", {})

            return {
                f"{currency}_available": Decimal(str(data.get("available_balance", 0))),
                f"{currency}_ledger": Decimal(str(data.get("ledger_balance", 0))),
            }
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}

    async def get_transfer_fee(
        self, amount: Decimal, currency: str = "NGN"
    ) -> Decimal:
        """Get transfer fee for an amount."""
        try:
            result = await self._request(
                "GET", "/transfers/fee",
                params={"amount": float(amount), "currency": currency}
            )
            data = result.get("data", [])
            if data:
                return Decimal(str(data[0].get("fee", 0)))
            return Decimal("0")
        except Exception as e:
            logger.error(f"Failed to get transfer fee: {e}")
            return Decimal("0")
