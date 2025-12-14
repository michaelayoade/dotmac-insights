"""
Payment gateway provider implementations.
"""

from typing import Optional

from app.integrations.payments.base import BasePaymentGateway
from app.integrations.payments.enums import PaymentProvider
from app.integrations.payments.config import get_payment_settings


def get_payment_gateway(
    provider: Optional[str] = None
) -> BasePaymentGateway:
    """
    Get a payment gateway client by provider name.

    Args:
        provider: Provider name (paystack, flutterwave).
                  If None, uses default from settings.

    Returns:
        Payment gateway client instance

    Raises:
        ValueError: If provider is not supported
    """
    settings = get_payment_settings()
    provider = (provider or settings.default_payment_provider).lower()

    if provider == PaymentProvider.PAYSTACK.value:
        from app.integrations.payments.providers.paystack.client import PaystackClient
        return PaystackClient()
    elif provider == PaymentProvider.FLUTTERWAVE.value:
        from app.integrations.payments.providers.flutterwave.client import FlutterwaveClient
        return FlutterwaveClient()
    else:
        raise ValueError(f"Unsupported payment provider: {provider}")


__all__ = ["get_payment_gateway"]
