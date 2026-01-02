"""
Currency helpers shared across templates and services.
"""

from __future__ import annotations

from typing import Dict


# Currency code to symbol mapping
CURRENCY_SYMBOLS: Dict[str, str] = {
    "NGN": "₦",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "KES": "KSh",
    "GHS": "₵",
    "ZAR": "R",
    "XOF": "CFA",
    "XAF": "FCFA",
}


def get_currency_symbol(currency_code: str) -> str:
    """Get the symbol for a currency code."""
    return CURRENCY_SYMBOLS.get(currency_code, currency_code)
