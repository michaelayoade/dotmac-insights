"""
Paystack Payment Gateway Client

Full implementation of Paystack API for:
- Payment initialization and verification
- Recurring charges via authorization
- Bank transfers (single and bulk)
- Virtual account creation
- Bank account resolution (NUBAN)
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
    PaymentInitializationError,
    PaymentVerificationError,
    TransferError,
    TransferRecipientError,
    AccountResolutionError,
    VirtualAccountError,
    RefundError,
    ProviderUnavailableError,
    InsufficientBalanceError,
    DuplicateTransactionError,
)
from app.integrations.payments.config import get_payment_settings

logger = logging.getLogger(__name__)


class PaystackClient(BasePaymentGateway):
    """
    Paystack payment gateway implementation.

    Supports:
    - Card payments with 3D Secure
    - Bank transfers
    - USSD payments
    - Bank account (direct debit)
    - Virtual accounts for collections
    - Recurring payments via authorization
    - Payouts/transfers to bank accounts
    """

    provider = PaymentProvider.PAYSTACK
    BASE_URL = "https://api.paystack.co"

    def __init__(
        self,
        secret_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Paystack client.

        Args:
            secret_key: Paystack secret key (defaults to env var)
            webhook_secret: Webhook signing secret (defaults to env var)
            timeout: Request timeout in seconds
        """
        settings = get_payment_settings()
        self.secret_key = secret_key or settings.paystack_secret_key
        self.webhook_secret = webhook_secret or settings.paystack_webhook_secret
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError("Paystack secret key is required")

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

    async def __aenter__(self) -> "PaystackClient":
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
                    message=result.get("message", "Paystack service unavailable"),
                    code="service_unavailable",
                    provider="paystack",
                    details=result,
                )

            if response.status_code >= 400:
                self._handle_error_response(result, response.status_code)

            return result

        except httpx.TimeoutException:
            logger.error(f"Paystack request timeout: {method} {endpoint}")
            raise ProviderUnavailableError(
                message="Request to Paystack timed out",
                code="timeout",
                provider="paystack",
            )
        except httpx.NetworkError as e:
            logger.error(f"Paystack network error: {e}")
            raise ProviderUnavailableError(
                message="Network error connecting to Paystack",
                code="network_error",
                provider="paystack",
            )

    def _handle_error_response(
        self, result: Dict[str, Any], status_code: int
    ) -> None:
        """Handle Paystack error responses."""
        message = result.get("message", "Unknown error")
        code = result.get("code", str(status_code))

        # Map common error codes
        if "duplicate" in message.lower():
            raise DuplicateTransactionError(
                message=message, code=code, provider="paystack", details=result
            )
        if "insufficient" in message.lower() or "balance" in message.lower():
            raise InsufficientBalanceError(
                message=message, code=code, provider="paystack", details=result
            )

        # Generic error based on endpoint context (handled by caller)
        raise PaymentError(
            message=message, code=code, provider="paystack", details=result
        )

    def _parse_status(self, status: str) -> TransactionStatus:
        """Map Paystack status to our enum."""
        status_map = {
            "success": TransactionStatus.SUCCESS,
            "failed": TransactionStatus.FAILED,
            "pending": TransactionStatus.PENDING,
            "processing": TransactionStatus.PROCESSING,
            "abandoned": TransactionStatus.ABANDONED,
            "reversed": TransactionStatus.REVERSED,
            "refunded": TransactionStatus.REFUNDED,
        }
        return status_map.get(status.lower(), TransactionStatus.PENDING)

    def _to_kobo(self, amount: Decimal) -> int:
        """Convert Naira to kobo (smallest unit)."""
        return int(amount * 100)

    def _from_kobo(self, kobo: int) -> Decimal:
        """Convert kobo to Naira."""
        return Decimal(kobo) / 100

    # =========================================================================
    # Payment Operations
    # =========================================================================

    async def initialize_payment(
        self, request: InitializePaymentRequest
    ) -> InitializePaymentResponse:
        """Initialize a payment transaction."""
        payload = {
            "email": request.email,
            "amount": self._to_kobo(request.amount),
            "reference": request.reference,
            "currency": request.currency,
        }

        if request.callback_url:
            payload["callback_url"] = request.callback_url
        if request.metadata:
            payload["metadata"] = request.metadata
        if request.channels:
            payload["channels"] = request.channels
        if request.split_code:
            payload["split_code"] = request.split_code
        if request.subaccount:
            payload["subaccount"] = request.subaccount

        try:
            result = await self._request("POST", "/transaction/initialize", data=payload)
            data = result.get("data", {})

            return InitializePaymentResponse(
                authorization_url=data["authorization_url"],
                access_code=data["access_code"],
                reference=data["reference"],
                provider=self.provider,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentInitializationError(
                message=f"Failed to initialize payment: {str(e)}",
                provider="paystack",
            )

    async def verify_payment(self, reference: str) -> PaymentVerificationResult:
        """Verify a payment by reference."""
        try:
            result = await self._request("GET", f"/transaction/verify/{reference}")
            data = result.get("data", {})

            paid_at = None
            if data.get("paid_at"):
                paid_at = datetime.fromisoformat(
                    data["paid_at"].replace("Z", "+00:00")
                )

            return PaymentVerificationResult(
                reference=data["reference"],
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=self._from_kobo(data["amount"]),
                currency=data["currency"],
                paid_at=paid_at,
                channel=data.get("channel"),
                fees=self._from_kobo(data.get("fees", 0)),
                metadata=data.get("metadata"),
                customer_email=data.get("customer", {}).get("email"),
                customer_code=data.get("customer", {}).get("customer_code"),
                authorization=data.get("authorization"),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentVerificationError(
                message=f"Failed to verify payment: {str(e)}",
                provider="paystack",
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
        """Charge a saved card authorization (for recurring payments)."""
        payload = {
            "authorization_code": authorization_code,
            "email": email,
            "amount": self._to_kobo(amount),
            "reference": reference,
            "currency": currency,
        }

        if metadata:
            payload["metadata"] = metadata

        try:
            result = await self._request(
                "POST", "/transaction/charge_authorization", data=payload
            )
            data = result.get("data", {})

            paid_at = None
            if data.get("paid_at"):
                paid_at = datetime.fromisoformat(
                    data["paid_at"].replace("Z", "+00:00")
                )

            return PaymentVerificationResult(
                reference=data["reference"],
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=self._from_kobo(data["amount"]),
                currency=data["currency"],
                paid_at=paid_at,
                channel=data.get("channel"),
                fees=self._from_kobo(data.get("fees", 0)),
                metadata=data.get("metadata"),
                customer_email=email,
                authorization=data.get("authorization"),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise PaymentVerificationError(
                message=f"Failed to charge authorization: {str(e)}",
                provider="paystack",
            )

    async def refund_payment(
        self,
        reference: str,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Refund a payment (full or partial)."""
        # First get the transaction
        verification = await self.verify_payment(reference)

        payload = {
            "transaction": verification.provider_reference,
        }

        if amount is not None:
            payload["amount"] = self._to_kobo(amount)

        try:
            result = await self._request("POST", "/refund", data=payload)
            return result.get("data", {})
        except PaymentError:
            raise
        except Exception as e:
            raise RefundError(
                message=f"Failed to refund payment: {str(e)}",
                provider="paystack",
            )

    # =========================================================================
    # Transfer Operations
    # =========================================================================

    async def create_transfer_recipient(
        self, recipient: TransferRecipient
    ) -> str:
        """Create a transfer recipient and return the recipient code."""
        payload = {
            "type": "nuban",
            "name": recipient.account_name or "Recipient",
            "account_number": recipient.account_number,
            "bank_code": recipient.bank_code,
            "currency": recipient.currency,
        }

        try:
            result = await self._request("POST", "/transferrecipient", data=payload)
            data = result.get("data", {})
            return data["recipient_code"]
        except PaymentError:
            raise
        except Exception as e:
            raise TransferRecipientError(
                message=f"Failed to create transfer recipient: {str(e)}",
                provider="paystack",
            )

    async def initiate_transfer(
        self, request: TransferRequest
    ) -> TransferResult:
        """Initiate a bank transfer."""
        # Ensure we have a recipient code
        recipient_code = request.recipient.recipient_code
        if not recipient_code:
            recipient_code = await self.create_transfer_recipient(request.recipient)

        payload = {
            "source": "balance",
            "amount": self._to_kobo(request.amount),
            "recipient": recipient_code,
            "reference": request.reference,
            "currency": request.currency,
        }

        if request.reason:
            payload["reason"] = request.reason

        try:
            result = await self._request("POST", "/transfer", data=payload)
            data = result.get("data", {})

            return TransferResult(
                reference=data["reference"],
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=self._from_kobo(data["amount"]),
                currency=data["currency"],
                recipient_code=recipient_code,
                transfer_code=data.get("transfer_code"),
                fee=self._from_kobo(data.get("fee", 0)),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to initiate transfer: {str(e)}",
                provider="paystack",
            )

    async def verify_transfer(self, reference: str) -> TransferResult:
        """Verify a transfer status."""
        try:
            result = await self._request("GET", f"/transfer/verify/{reference}")
            data = result.get("data", {})

            return TransferResult(
                reference=data["reference"],
                provider_reference=str(data["id"]),
                status=self._parse_status(data["status"]),
                amount=self._from_kobo(data["amount"]),
                currency=data["currency"],
                recipient_code=data.get("recipient", {}).get("recipient_code", ""),
                transfer_code=data.get("transfer_code"),
                fee=self._from_kobo(data.get("fee", 0)),
                raw_response=data,
            )
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to verify transfer: {str(e)}",
                provider="paystack",
            )

    async def initiate_bulk_transfer(
        self, transfers: List[TransferRequest]
    ) -> List[TransferResult]:
        """Initiate multiple transfers in a batch."""
        # Prepare recipient codes
        transfer_list = []
        for transfer in transfers:
            recipient_code = transfer.recipient.recipient_code
            if not recipient_code:
                recipient_code = await self.create_transfer_recipient(
                    transfer.recipient
                )

            transfer_list.append({
                "amount": self._to_kobo(transfer.amount),
                "recipient": recipient_code,
                "reference": transfer.reference,
                "reason": transfer.reason or "",
            })

        payload = {
            "source": "balance",
            "currency": transfers[0].currency if transfers else "NGN",
            "transfers": transfer_list,
        }

        try:
            result = await self._request("POST", "/transfer/bulk", data=payload)
            data_list = result.get("data", [])

            results = []
            for data in data_list:
                results.append(
                    TransferResult(
                        reference=data["reference"],
                        provider_reference=str(data.get("id", "")),
                        status=self._parse_status(data.get("status", "pending")),
                        amount=self._from_kobo(data["amount"]),
                        currency=data.get("currency", "NGN"),
                        recipient_code=data.get("recipient", ""),
                        transfer_code=data.get("transfer_code"),
                        raw_response=data,
                    )
                )

            return results
        except PaymentError:
            raise
        except Exception as e:
            raise TransferError(
                message=f"Failed to initiate bulk transfer: {str(e)}",
                provider="paystack",
            )

    # =========================================================================
    # Bank Operations
    # =========================================================================

    async def get_banks(self, country: str = "NG") -> List[BankInfo]:
        """Get list of supported banks."""
        params = {
            "country": country.lower(),
            "use_cursor": False,
            "perPage": 100,
        }

        try:
            result = await self._request("GET", "/bank", params=params)
            banks = []

            for bank in result.get("data", []):
                banks.append(
                    BankInfo(
                        code=bank["code"],
                        name=bank["name"],
                        slug=bank.get("slug", ""),
                        is_active=bank.get("active", True),
                        country=country,
                        currency=bank.get("currency", "NGN"),
                    )
                )

            return banks
        except Exception as e:
            logger.error(f"Failed to get banks: {e}")
            return []

    async def resolve_account(
        self, account_number: str, bank_code: str
    ) -> AccountInfo:
        """Resolve/verify a bank account (NUBAN validation)."""
        params = {
            "account_number": account_number,
            "bank_code": bank_code,
        }

        try:
            result = await self._request("GET", "/bank/resolve", params=params)
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
                provider="paystack",
            )

    # =========================================================================
    # Virtual Account Operations
    # =========================================================================

    async def create_virtual_account(
        self, request: VirtualAccountRequest
    ) -> VirtualAccountResponse:
        """Create a dedicated virtual account for collections."""
        # First create or get the customer
        customer_payload = {
            "email": request.customer_email,
            "first_name": request.customer_name.split()[0] if request.customer_name else "",
            "last_name": " ".join(request.customer_name.split()[1:]) if request.customer_name and len(request.customer_name.split()) > 1 else "",
        }

        try:
            customer_result = await self._request(
                "POST", "/customer", data=customer_payload
            )
            customer_code = customer_result.get("data", {}).get("customer_code")
        except DuplicateTransactionError:
            # Customer exists, fetch them
            customers = await self._request(
                "GET", "/customer", params={"email": request.customer_email}
            )
            customer_data = customers.get("data", [])
            if customer_data:
                customer_code = customer_data[0].get("customer_code")
            else:
                raise VirtualAccountError(
                    message="Could not find or create customer",
                    provider="paystack",
                )

        # Create dedicated account
        dva_payload = {
            "customer": customer_code,
        }

        if request.preferred_bank:
            dva_payload["preferred_bank"] = request.preferred_bank

        try:
            result = await self._request(
                "POST", "/dedicated_account", data=dva_payload
            )
            data = result.get("data", {})

            bank = data.get("bank", {})

            return VirtualAccountResponse(
                account_number=data["account_number"],
                account_name=data["account_name"],
                bank_name=bank.get("name", ""),
                bank_code=bank.get("id", ""),
                provider_reference=str(data.get("id", "")),
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
                provider="paystack",
            )

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify Paystack webhook HMAC-SHA512 signature.

        Args:
            payload: Raw request body bytes
            signature: x-paystack-signature header value

        Returns:
            True if signature is valid

        Raises:
            ValueError: In production if webhook secret is not configured
        """
        if not self.webhook_secret:
            # Fail closed in production - reject webhooks if secret not configured
            from app.config import settings
            if settings.is_production:
                logger.error(
                    "paystack_webhook_secret_missing: Webhook secret not configured in production - rejecting webhook"
                )
                return False
            logger.warning("Webhook secret not configured, skipping verification (dev mode)")
            return True

        expected = hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    # =========================================================================
    # Balance & Account Info
    # =========================================================================

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get available and ledger balance."""
        try:
            result = await self._request("GET", "/balance")
            data = result.get("data", [])

            balances = {}
            for balance in data:
                currency = balance.get("currency", "NGN")
                balances[f"{currency}_available"] = self._from_kobo(
                    balance.get("balance", 0)
                )

            return balances
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}

    async def get_bank_transfer_details(self) -> Dict[str, Any]:
        """Get bank transfer payment page details."""
        try:
            result = await self._request("GET", "/dedicated_account")
            return result.get("data", {})
        except Exception as e:
            logger.error(f"Failed to get bank transfer details: {e}")
            return {}


# Import PaymentError for error handling
from app.integrations.payments.exceptions import PaymentError
