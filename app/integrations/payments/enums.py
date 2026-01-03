"""
Enums for payment integrations.
"""

from enum import Enum


class PaymentProvider(str, Enum):
    """Supported payment gateway providers."""
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"


class OpenBankingProvider(str, Enum):
    """Supported open banking providers."""
    MONO = "mono"
    OKRA = "okra"


class TransactionStatus(str, Enum):
    """Gateway transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"
    ABANDONED = "abandoned"
    REFUNDED = "refunded"


class TransactionType(str, Enum):
    """Gateway transaction type."""
    PAYMENT = "payment"
    TRANSFER = "transfer"
    REFUND = "refund"
    CHARGEBACK = "chargeback"


class TransferStatus(str, Enum):
    """Bank transfer status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"


class TransferType(str, Enum):
    """Type of bank transfer."""
    SINGLE = "single"
    BULK = "bulk"
    PAYROLL = "payroll"
    VENDOR_PAYMENT = "vendor_payment"


class SubscriptionStatus(str, Enum):
    """Recurring subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    PAST_DUE = "past_due"


class SubscriptionInterval(str, Enum):
    """Subscription billing interval."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class VirtualAccountStatus(str, Enum):
    """Virtual account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


class ConnectionStatus(str, Enum):
    """Open banking connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REAUTHORIZATION_REQUIRED = "reauthorization_required"
    FAILED = "failed"


class PaymentChannel(str, Enum):
    """Payment channels supported by gateways."""
    CARD = "card"
    BANK = "bank"
    BANK_TRANSFER = "bank_transfer"
    USSD = "ussd"
    QR = "qr"
    MOBILE_MONEY = "mobile_money"
    VIRTUAL_ACCOUNT = "virtual_account"
