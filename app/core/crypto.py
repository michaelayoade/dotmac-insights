"""
Cryptographic utilities for sensitive configuration values.

Used to encrypt/decrypt sensitive data like SMTP passwords stored in database.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _get_encryption_key() -> bytes:
    """Get or derive encryption key from environment.

    Uses CONFIG_ENCRYPTION_KEY if set, otherwise derives from SECRET_KEY.
    The key must be 32 bytes, base64-encoded for Fernet.
    """
    key = os.environ.get("CONFIG_ENCRYPTION_KEY")
    if key:
        # User provided a key - ensure it's valid Fernet key
        return key.encode()

    # Derive from SECRET_KEY (fallback for development)
    secret = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    # Hash to get exactly 32 bytes, then base64 encode for Fernet
    derived = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_sensitive_value(plaintext: str) -> str:
    """Encrypt a sensitive configuration value.

    Args:
        plaintext: The value to encrypt

    Returns:
        Base64-encoded encrypted value with 'enc:' prefix
    """
    if not plaintext:
        return ""

    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode())
    return f"enc:{encrypted.decode()}"


def decrypt_sensitive_value(encrypted: str) -> Optional[str]:
    """Decrypt a sensitive configuration value.

    Args:
        encrypted: The encrypted value (with 'enc:' prefix)

    Returns:
        Decrypted plaintext, or None if decryption fails
    """
    if not encrypted:
        return None

    # Handle unencrypted values (backwards compatibility)
    if not encrypted.startswith("enc:"):
        return encrypted

    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_data = encrypted[4:].encode()  # Remove 'enc:' prefix
        decrypted = f.decrypt(encrypted_data)
        return decrypted.decode()
    except (InvalidToken, ValueError):
        return None


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return value.startswith("enc:") if value else False


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive value for display.

    Args:
        value: The value to mask
        visible_chars: Number of characters to show at end

    Returns:
        Masked value like "****1234"
    """
    if not value or len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
