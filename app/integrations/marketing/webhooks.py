"""Webhook helpers for marketing integrations."""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Mapping, Optional

from app.config import settings


def compute_payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_signature(signature: str, prefix: Optional[str] = None) -> str:
    value = signature.strip()
    if prefix and value.startswith(prefix):
        return value[len(prefix):]
    return value


def verify_hmac_signature(secret: str, payload: bytes, signature: str, prefix: Optional[str] = None) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = _normalize_signature(signature, prefix)
    return hmac.compare_digest(expected, provided)


def get_webhook_secret(platform: str) -> Optional[str]:
    mapping = {
        "meta": settings.meta_webhook_secret,
        "twitter": settings.twitter_webhook_secret,
        "linkedin": settings.linkedin_webhook_secret,
        "whatsapp": settings.whatsapp_webhook_secret,
    }
    return mapping.get(platform)


def extract_signature(platform: str, headers: Mapping[str, str]) -> Optional[str]:
    key_map = {
        "meta": "x-hub-signature-256",
        "twitter": "x-twitter-webhooks-signature",
        "linkedin": "x-li-signature",
        "whatsapp": "x-hub-signature-256",
    }
    header_key = key_map.get(platform)
    if not header_key:
        return None
    return headers.get(header_key) or headers.get(header_key.title())


def verify_meta_signature(secret: str, payload: bytes, signature: str) -> bool:
    prefix = "sha256=" if signature.startswith("sha256=") else None
    return verify_hmac_signature(secret, payload, signature, prefix=prefix)


def verify_whatsapp_signature(secret: str, payload: bytes, signature: str) -> bool:
    return verify_meta_signature(secret, payload, signature)


def verify_twitter_signature(secret: str, payload: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def verify_linkedin_signature(secret: str, payload: bytes, signature: str) -> bool:
    return verify_hmac_signature(secret, payload, signature)


def verify_platform_signature(platform: str, headers: Mapping[str, str], payload: bytes) -> bool:
    secret = get_webhook_secret(platform)
    signature = extract_signature(platform, headers)
    if not secret or not signature:
        return False
    if platform == "meta":
        return verify_meta_signature(secret, payload, signature)
    if platform == "whatsapp":
        return verify_whatsapp_signature(secret, payload, signature)
    if platform == "twitter":
        return verify_twitter_signature(secret, payload, signature)
    if platform == "linkedin":
        return verify_linkedin_signature(secret, payload, signature)
    return False


def extract_event_id(payload: dict, headers: Mapping[str, str]) -> Optional[str]:
    for key in ("x-event-id", "x-request-id", "x-hub-signature-256"):
        if key in headers:
            return headers[key]
    for candidate in ("event_id", "eventId", "id"):
        value = payload.get(candidate)
        if value:
            return str(value)
    return None
