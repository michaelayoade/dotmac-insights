"""Marketing integration clients and webhook helpers."""
from app.integrations.marketing.base import BaseMarketingClient, MarketingClientError
from app.integrations.marketing.meta_client import MetaBusinessClient
from app.integrations.marketing.twitter_client import TwitterClient
from app.integrations.marketing.linkedin_client import LinkedInClient
from app.integrations.marketing.whatsapp_client import WhatsAppBusinessClient
from app.integrations.marketing.webhooks import (
    compute_payload_hash,
    extract_event_id,
    extract_signature,
    get_webhook_secret,
    verify_linkedin_signature,
    verify_hmac_signature,
    verify_meta_signature,
    verify_platform_signature,
    verify_twitter_signature,
    verify_whatsapp_signature,
)

__all__ = [
    "BaseMarketingClient",
    "MarketingClientError",
    "MetaBusinessClient",
    "TwitterClient",
    "LinkedInClient",
    "WhatsAppBusinessClient",
    "compute_payload_hash",
    "extract_event_id",
    "extract_signature",
    "get_webhook_secret",
    "verify_linkedin_signature",
    "verify_hmac_signature",
    "verify_meta_signature",
    "verify_platform_signature",
    "verify_twitter_signature",
    "verify_whatsapp_signature",
]
