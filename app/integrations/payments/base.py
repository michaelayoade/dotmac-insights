"""
Abstract base classes for payment gateway providers.

All payment gateway implementations must inherit from BasePaymentGateway
and implement all abstract methods.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.integrations.payments.enums import (
    PaymentProvider,
    TransactionStatus,
    PaymentChannel,
)


# =============================================================================
# Data Transfer Objects
# =============================================================================

@dataclass
class InitializePaymentRequest:
    """Request to initialize a payment."""
    amount: Decimal
    currency: str
    email: str
    reference: str  # Idempotency key
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    channels: Optional[List[str]] = None  # card, bank, ussd, etc.
    invoice_id: Optional[int] = None
    customer_id: Optional[int] = None
    split_code: Optional[str] = None  # For split payments
    subaccount: Optional[str] = None


@dataclass
class InitializePaymentResponse:
    """Response from payment initialization."""
    authorization_url: str
    access_code: str
    reference: str
    provider: PaymentProvider


@dataclass
class PaymentVerificationResult:
    """Result of payment verification."""
    reference: str
    provider_reference: str
    status: TransactionStatus
    amount: Decimal
    currency: str
    paid_at: Optional[datetime] = None
    channel: Optional[str] = None
    fees: Decimal = Decimal("0")
    metadata: Optional[Dict[str, Any]] = None
    customer_email: Optional[str] = None
    customer_code: Optional[str] = None
    authorization: Optional[Dict[str, Any]] = None  # For recurring
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferRecipient:
    """Transfer recipient details."""
    account_number: str
    bank_code: str
    account_name: Optional[str] = None
    recipient_code: Optional[str] = None  # Provider recipient ID
    currency: str = "NGN"


@dataclass
class TransferRequest:
    """Request to initiate a transfer."""
    amount: Decimal
    currency: str
    recipient: TransferRecipient
    reference: str
    reason: Optional[str] = None
    narration: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TransferResult:
    """Result of transfer initiation."""
    reference: str
    provider_reference: str
    status: TransactionStatus
    amount: Decimal
    currency: str
    recipient_code: str
    transfer_code: Optional[str] = None
    fee: Decimal = Decimal("0")
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BankInfo:
    """Bank information."""
    code: str
    name: str
    slug: str
    is_active: bool
    country: str = "NG"
    currency: str = "NGN"


@dataclass
class AccountInfo:
    """Resolved bank account information."""
    account_number: str
    account_name: str
    bank_code: str
    bank_name: Optional[str] = None


@dataclass
class VirtualAccountRequest:
    """Request to create a virtual account."""
    customer_email: str
    customer_name: str
    customer_id: Optional[int] = None
    preferred_bank: Optional[str] = None
    bvn: Optional[str] = None
    is_permanent: bool = True
    expected_amount: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class VirtualAccountResponse:
    """Response from virtual account creation."""
    account_number: str
    account_name: str
    bank_name: str
    bank_code: str
    provider_reference: str
    provider: PaymentProvider
    is_permanent: bool = True
    expires_at: Optional[datetime] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Abstract Base Class
# =============================================================================

class BasePaymentGateway(abc.ABC):
    """Abstract base class for payment gateway providers."""

    provider: PaymentProvider

    @abc.abstractmethod
    async def initialize_payment(
        self, request: InitializePaymentRequest
    ) -> InitializePaymentResponse:
        """
        Initialize a payment and get authorization URL.

        Args:
            request: Payment initialization request

        Returns:
            Response with authorization URL for customer redirect

        Raises:
            PaymentInitializationError: If initialization fails
        """
        pass

    @abc.abstractmethod
    async def verify_payment(self, reference: str) -> PaymentVerificationResult:
        """
        Verify a payment by reference.

        Args:
            reference: Payment reference (idempotency key)

        Returns:
            Verification result with status and details

        Raises:
            PaymentVerificationError: If verification fails
        """
        pass

    @abc.abstractmethod
    async def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: Decimal,
        reference: str,
        currency: str = "NGN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentVerificationResult:
        """
        Charge a saved authorization (recurring payment).

        Args:
            authorization_code: Saved authorization code from previous payment
            email: Customer email
            amount: Amount to charge
            reference: Unique reference for this charge
            currency: Currency code
            metadata: Optional metadata

        Returns:
            Verification result

        Raises:
            PaymentError: If charge fails
        """
        pass

    @abc.abstractmethod
    async def refund_payment(
        self,
        reference: str,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Refund a payment.

        Args:
            reference: Original payment reference
            amount: Amount to refund (None for full refund)

        Returns:
            Refund details

        Raises:
            RefundError: If refund fails
        """
        pass

    @abc.abstractmethod
    async def create_transfer_recipient(
        self, recipient: TransferRecipient
    ) -> str:
        """
        Create a transfer recipient and return recipient code.

        Args:
            recipient: Recipient details (account number, bank code)

        Returns:
            Provider's recipient code

        Raises:
            TransferRecipientError: If creation fails
        """
        pass

    @abc.abstractmethod
    async def initiate_transfer(
        self, request: TransferRequest
    ) -> TransferResult:
        """
        Initiate a bank transfer.

        Args:
            request: Transfer request details

        Returns:
            Transfer result with status

        Raises:
            TransferError: If transfer fails
        """
        pass

    @abc.abstractmethod
    async def verify_transfer(self, reference: str) -> TransferResult:
        """
        Verify transfer status.

        Args:
            reference: Transfer reference

        Returns:
            Transfer result with current status

        Raises:
            TransferError: If verification fails
        """
        pass

    @abc.abstractmethod
    async def initiate_bulk_transfer(
        self, transfers: List[TransferRequest]
    ) -> List[TransferResult]:
        """
        Initiate multiple transfers in one batch.

        Args:
            transfers: List of transfer requests

        Returns:
            List of transfer results

        Raises:
            TransferError: If bulk transfer fails
        """
        pass

    @abc.abstractmethod
    async def get_banks(self, country: str = "NG") -> List[BankInfo]:
        """
        Get list of supported banks.

        Args:
            country: Country code (default: Nigeria)

        Returns:
            List of bank information
        """
        pass

    @abc.abstractmethod
    async def resolve_account(
        self, account_number: str, bank_code: str
    ) -> AccountInfo:
        """
        Resolve/verify a bank account (NUBAN validation).

        Args:
            account_number: Bank account number
            bank_code: Bank code

        Returns:
            Account information including name

        Raises:
            AccountResolutionError: If resolution fails
        """
        pass

    @abc.abstractmethod
    async def create_virtual_account(
        self, request: VirtualAccountRequest
    ) -> VirtualAccountResponse:
        """
        Create a dedicated virtual account for collections.

        Args:
            request: Virtual account request details

        Returns:
            Virtual account details

        Raises:
            VirtualAccountError: If creation fails
        """
        pass

    @abc.abstractmethod
    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Verify webhook HMAC signature.

        Args:
            payload: Raw request body
            signature: Signature from header

        Returns:
            True if signature is valid
        """
        pass

    async def close(self) -> None:
        """Close any open connections. Override if needed."""
        pass
