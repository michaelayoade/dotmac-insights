"""
Custom exceptions for payment integrations.
"""

from typing import Optional, Dict, Any


class PaymentError(Exception):
    """Base exception for payment errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.provider = provider
        self.details = details or {}
        super().__init__(self.message)


class PaymentInitializationError(PaymentError):
    """Failed to initialize payment."""
    pass


class PaymentVerificationError(PaymentError):
    """Failed to verify payment."""
    pass


class TransferError(PaymentError):
    """Transfer operation failed."""
    pass


class TransferRecipientError(PaymentError):
    """Failed to create/validate transfer recipient."""
    pass


class AccountResolutionError(PaymentError):
    """Failed to resolve bank account (NUBAN validation)."""
    pass


class WebhookVerificationError(PaymentError):
    """Webhook signature verification failed."""
    pass


class ProviderUnavailableError(PaymentError):
    """Payment provider is unavailable."""
    pass


class InsufficientBalanceError(PaymentError):
    """Insufficient balance for transfer."""
    pass


class InvalidAccountError(PaymentError):
    """Invalid bank account number."""
    pass


class DuplicateTransactionError(PaymentError):
    """Transaction with this reference already exists."""
    pass


class RefundError(PaymentError):
    """Refund operation failed."""
    pass


class SubscriptionError(PaymentError):
    """Subscription operation failed."""
    pass


class VirtualAccountError(PaymentError):
    """Virtual account operation failed."""
    pass


# Open Banking Errors

class OpenBankingError(Exception):
    """Base exception for open banking errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.provider = provider
        self.details = details or {}
        super().__init__(self.message)


class AccountLinkingError(OpenBankingError):
    """Failed to link bank account."""
    pass


class AccountSyncError(OpenBankingError):
    """Failed to sync account data."""
    pass


class ReauthorizationRequiredError(OpenBankingError):
    """Account connection needs reauthorization."""
    pass


class AccountNotFoundError(OpenBankingError):
    """Linked account not found."""
    pass
