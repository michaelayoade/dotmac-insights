"""
Payment integrations module.

Provides unified interfaces for:
- Payment collection (Paystack, Flutterwave)
- Bank transfers (Paystack, Flutterwave)
- Open banking (Mono, Okra)
- Virtual accounts
- Recurring subscriptions
"""

from app.integrations.payments.config import (
    payment_settings,
    PaymentSettings,
    get_payment_settings,
)
from app.integrations.payments.enums import (
    PaymentProvider,
    OpenBankingProvider,
    TransactionStatus,
    TransactionType,
    TransferStatus,
    TransferType,
    SubscriptionStatus,
    SubscriptionInterval,
    VirtualAccountStatus,
    ConnectionStatus,
)
from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.openbanking import MonoClient, OkraClient
from app.integrations.payments.webhooks import webhook_processor

__all__ = [
    # Config
    "payment_settings",
    "PaymentSettings",
    "get_payment_settings",
    # Enums
    "PaymentProvider",
    "OpenBankingProvider",
    "TransactionStatus",
    "TransactionType",
    "TransferStatus",
    "TransferType",
    "SubscriptionStatus",
    "SubscriptionInterval",
    "VirtualAccountStatus",
    "ConnectionStatus",
    # Clients
    "PaystackClient",
    "FlutterwaveClient",
    "MonoClient",
    "OkraClient",
    # Webhooks
    "webhook_processor",
]
