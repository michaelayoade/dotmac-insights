"""
Integrations module for external service connections.

This module contains integrations with:
- Payment gateways (Paystack, Flutterwave)
- Open banking providers (Mono, Okra)
"""

from app.integrations.payments import payment_settings

__all__ = ["payment_settings"]
