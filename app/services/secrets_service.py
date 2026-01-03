"""
OpenBao Transit Secrets Service

Provides encryption/decryption via OpenBao's Transit secrets engine.
Falls back to local Fernet encryption in development when OpenBao is unavailable.
"""

import base64
import json
import os
from typing import Optional

import httpx
import structlog
from cryptography.fernet import Fernet

from app.config import settings

logger = structlog.get_logger()


class SecretsServiceError(Exception):
    """Base exception for secrets service errors."""
    pass


class OpenBaoSecretsService:
    """
    Encrypts/decrypts data using OpenBao Transit secrets engine.

    Requires:
    - OPENBAO_URL: OpenBao server URL (e.g., http://localhost:8200)
    - OPENBAO_TOKEN: Authentication token
    - Transit engine enabled with key named 'settings'

    Setup commands:
        bao secrets enable transit
        bao write -f transit/keys/settings type=aes256-gcm96
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        key_name: str = "settings",
    ):
        resolved_url = url or os.getenv("OPENBAO_URL") or ""
        self.url: str = resolved_url.rstrip("/")
        self.token: str = token or os.getenv("OPENBAO_TOKEN") or ""
        self.key_name = key_name
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.url,
                headers={"X-Vault-Token": self.token},
                timeout=10.0,
            )
        return self._client

    @property
    def is_configured(self) -> bool:
        """Check if OpenBao is configured."""
        return bool(self.url and self.token)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using OpenBao Transit.

        Returns ciphertext in format: vault:v1:base64...
        """
        if not self.is_configured:
            raise SecretsServiceError("OpenBao not configured")

        # OpenBao expects base64-encoded plaintext
        plaintext_b64 = base64.b64encode(plaintext.encode()).decode()

        try:
            response = self.client.post(
                f"/v1/transit/encrypt/{self.key_name}",
                json={"plaintext": plaintext_b64},
            )
            response.raise_for_status()
            data = response.json()
            ciphertext: str = data["data"]["ciphertext"]

            logger.debug("openbao_encrypt_success", key=self.key_name)
            return ciphertext

        except httpx.HTTPStatusError as e:
            logger.error("openbao_encrypt_failed", status=e.response.status_code, error=str(e))
            raise SecretsServiceError(f"Encryption failed: {e.response.text}") from e
        except Exception as e:
            logger.error("openbao_encrypt_error", error=str(e))
            raise SecretsServiceError(f"Encryption error: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext using OpenBao Transit.

        Expects ciphertext in format: vault:v1:base64...
        """
        if not self.is_configured:
            raise SecretsServiceError("OpenBao not configured")

        try:
            response = self.client.post(
                f"/v1/transit/decrypt/{self.key_name}",
                json={"ciphertext": ciphertext},
            )
            response.raise_for_status()
            data = response.json()
            plaintext_b64 = data["data"]["plaintext"]
            plaintext = base64.b64decode(plaintext_b64).decode()

            logger.debug("openbao_decrypt_success", key=self.key_name)
            return plaintext

        except httpx.HTTPStatusError as e:
            logger.error("openbao_decrypt_failed", status=e.response.status_code, error=str(e))
            raise SecretsServiceError(f"Decryption failed: {e.response.text}") from e
        except Exception as e:
            logger.error("openbao_decrypt_error", error=str(e))
            raise SecretsServiceError(f"Decryption error: {e}") from e

    def rotate_key(self) -> dict:
        """
        Rotate the encryption key.

        Old ciphertexts can still be decrypted; new encryptions use the new key.
        """
        if not self.is_configured:
            raise SecretsServiceError("OpenBao not configured")

        try:
            response = self.client.post(
                f"/v1/transit/keys/{self.key_name}/rotate",
            )
            response.raise_for_status()

            logger.info("openbao_key_rotated", key=self.key_name)
            return {"status": "rotated", "key": self.key_name}

        except httpx.HTTPStatusError as e:
            logger.error("openbao_rotate_failed", status=e.response.status_code, error=str(e))
            raise SecretsServiceError(f"Key rotation failed: {e.response.text}") from e

    def rewrap(self, ciphertext: str) -> str:
        """
        Re-encrypt ciphertext with the latest key version.

        Use after key rotation to update stored ciphertexts.
        """
        if not self.is_configured:
            raise SecretsServiceError("OpenBao not configured")

        try:
            response = self.client.post(
                f"/v1/transit/rewrap/{self.key_name}",
                json={"ciphertext": ciphertext},
            )
            response.raise_for_status()
            data = response.json()
            new_ciphertext: str = data["data"]["ciphertext"]

            logger.debug("openbao_rewrap_success", key=self.key_name)
            return new_ciphertext

        except httpx.HTTPStatusError as e:
            logger.error("openbao_rewrap_failed", status=e.response.status_code, error=str(e))
            raise SecretsServiceError(f"Rewrap failed: {e.response.text}") from e

    def health_check(self) -> dict:
        """Check OpenBao connectivity and key availability."""
        if not self.is_configured:
            return {"status": "not_configured", "url": self.url}

        try:
            # Check health
            response = self.client.get("/v1/sys/health")
            health = response.json()

            # Check key exists
            key_response = self.client.get(f"/v1/transit/keys/{self.key_name}")
            key_response.raise_for_status()
            key_info = key_response.json()

            return {
                "status": "healthy",
                "initialized": health.get("initialized", False),
                "sealed": health.get("sealed", True),
                "key_name": self.key_name,
                "key_version": key_info["data"].get("latest_version", 1),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


class LocalSecretsService:
    """
    Local Fernet encryption for development.

    Uses a static key from environment or generates one.
    NOT FOR PRODUCTION USE.
    """

    PREFIX = "local:v1:"

    def __init__(self, key: Optional[str] = None):
        key_str = key or os.getenv("DEV_ENCRYPTION_KEY")
        if key_str:
            self._key = key_str.encode() if isinstance(key_str, str) else key_str
        else:
            # Generate a deterministic key for dev (based on a seed)
            # In real dev, set DEV_ENCRYPTION_KEY in .env
            self._key = Fernet.generate_key()
            logger.warning(
                "dev_encryption_key_generated",
                message="Using generated encryption key. Set DEV_ENCRYPTION_KEY in .env for persistence."
            )
        self._fernet = Fernet(self._key)

    @property
    def is_configured(self) -> bool:
        return True

    def encrypt(self, plaintext: str) -> str:
        """Encrypt using local Fernet."""
        ciphertext = self._fernet.encrypt(plaintext.encode())
        return f"{self.PREFIX}{ciphertext.decode()}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt using local Fernet."""
        if ciphertext.startswith(self.PREFIX):
            ciphertext = ciphertext[len(self.PREFIX):]
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def rotate_key(self) -> dict:
        """Not supported in local mode."""
        return {"status": "not_supported", "message": "Key rotation not available in local mode"}

    def rewrap(self, ciphertext: str) -> str:
        """No-op in local mode."""
        return ciphertext

    def health_check(self) -> dict:
        return {"status": "healthy", "mode": "local", "warning": "Not for production use"}

    def close(self):
        pass


def get_secrets_service() -> OpenBaoSecretsService | LocalSecretsService:
    """
    Factory function to get the appropriate secrets service.

    Uses OpenBao in production/staging, local Fernet in development.
    """
    openbao_url = os.getenv("OPENBAO_URL")
    openbao_token = os.getenv("OPENBAO_TOKEN")

    if openbao_url and openbao_token:
        service = OpenBaoSecretsService(url=openbao_url, token=openbao_token)
        health = service.health_check()
        if health["status"] == "healthy":
            logger.info("secrets_service_initialized", mode="openbao", url=openbao_url)
            return service
        else:
            logger.warning("openbao_unhealthy", health=health)

    # Fall back to local encryption
    if settings.environment == "production":
        raise SecretsServiceError(
            "OpenBao is required in production. Set OPENBAO_URL and OPENBAO_TOKEN."
        )

    logger.info("secrets_service_initialized", mode="local")
    return LocalSecretsService()


# Singleton instance
_secrets_service: Optional[OpenBaoSecretsService | LocalSecretsService] = None


def get_secrets() -> OpenBaoSecretsService | LocalSecretsService:
    """Get the singleton secrets service instance."""
    global _secrets_service
    if _secrets_service is None:
        _secrets_service = get_secrets_service()
    return _secrets_service
