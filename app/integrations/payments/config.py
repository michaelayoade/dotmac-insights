"""
Payment integration configuration.

All settings are loaded from environment variables.
"""

from typing import Optional
from pydantic_settings import BaseSettings


class PaymentSettings(BaseSettings):
    """Payment provider configuration from environment."""

    # Paystack credentials
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_webhook_secret: str = ""

    # Flutterwave credentials
    flutterwave_secret_key: str = ""
    flutterwave_public_key: str = ""
    flutterwave_encryption_key: str = ""
    flutterwave_webhook_secret: str = ""

    # Mono (Open Banking) credentials
    mono_secret_key: str = ""
    mono_public_key: str = ""
    mono_webhook_secret: str = ""

    # Okra (Open Banking) credentials
    okra_secret_key: str = ""
    okra_public_key: str = ""
    okra_webhook_secret: str = ""

    # Provider preferences
    default_payment_provider: str = "paystack"
    default_transfer_provider: str = "paystack"
    default_open_banking_provider: str = "mono"

    # Feature flags
    enable_virtual_accounts: bool = True
    enable_recurring_payments: bool = True
    enable_bulk_transfers: bool = True
    enable_open_banking: bool = True

    # Transfer settings
    transfer_requires_approval_above: Optional[float] = None  # Amount threshold
    bulk_transfer_max_size: int = 100

    # Retry settings
    payment_max_retries: int = 3
    transfer_max_retries: int = 3
    webhook_max_retries: int = 3

    # Timeout settings (seconds)
    api_timeout: int = 30
    webhook_timeout: int = 10

    class Config:
        env_file = ".env"
        env_prefix = ""
        extra = "ignore"


# Singleton instance
payment_settings = PaymentSettings()


def get_payment_settings() -> PaymentSettings:
    """
    Return loaded payment settings.

    Using a helper keeps import sites consistent and avoids multiple
    instantiations when modules import the settings lazily.
    """
    return payment_settings
