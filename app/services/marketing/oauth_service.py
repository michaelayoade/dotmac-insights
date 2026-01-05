"""OAuth helpers for marketing integrations."""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx

from app.config import settings
from app.services.errors import ValidationError
from app.services.marketing.integration_service import IntegrationService


@dataclass
class OAuthProviderConfig:
    auth_url: str
    token_url: str
    client_id: Optional[str]
    client_secret: Optional[str]
    scopes: str
    use_pkce: bool = False


PROVIDERS: Dict[str, OAuthProviderConfig] = {
    "meta": OAuthProviderConfig(
        auth_url="https://www.facebook.com/v18.0/dialog/oauth",
        token_url="https://graph.facebook.com/v18.0/oauth/access_token",
        client_id=settings.meta_app_id,
        client_secret=settings.meta_app_secret,
        scopes="pages_show_list,pages_manage_posts,read_insights",
    ),
    "linkedin": OAuthProviderConfig(
        auth_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        client_id=settings.linkedin_client_id,
        client_secret=settings.linkedin_client_secret,
        scopes="r_liteprofile r_emailaddress w_member_social",
    ),
    "twitter": OAuthProviderConfig(
        auth_url="https://twitter.com/i/oauth2/authorize",
        token_url="https://api.twitter.com/2/oauth2/token",
        client_id=settings.twitter_client_id,
        client_secret=settings.twitter_client_secret,
        scopes="tweet.read tweet.write users.read offline.access",
        use_pkce=True,
    ),
    "whatsapp": OAuthProviderConfig(
        auth_url="https://www.facebook.com/v18.0/dialog/oauth",
        token_url="https://graph.facebook.com/v18.0/oauth/access_token",
        client_id=settings.meta_app_id,
        client_secret=settings.meta_app_secret,
        scopes="whatsapp_business_messaging",
    ),
}


class MarketingOAuthService:
    def __init__(self, integration_service: IntegrationService):
        self.integration_service = integration_service

    def build_authorize_url(self, provider: str, callback_base_url: str) -> str:
        config = _get_provider(provider)
        if not config.client_id:
            raise ValidationError(f"Missing client_id for {provider}")

        state = secrets.token_urlsafe(32)
        code_verifier = None
        code_challenge = None
        if config.use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = _pkce_challenge(code_verifier)

        callback_url = _callback_url(callback_base_url, provider)

        params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": callback_url,
            "scope": config.scopes,
            "state": state,
        }
        if config.use_pkce:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        integration = self.integration_service.get_or_create_by_type(provider)
        settings = integration.settings or {}
        settings.update(
            {
                "oauth_state": state,
                "code_verifier": code_verifier,
                "callback_base_url": callback_base_url,
            }
        )
        integration.settings = settings

        return f"{config.auth_url}?{urllib.parse.urlencode(params)}"

    async def handle_callback(self, provider: str, code: str, state: str, callback_base_url: str) -> None:
        config = _get_provider(provider)
        if not config.client_id:
            raise ValidationError(f"Missing client_id for {provider}")

        integration = self.integration_service.get_or_create_by_type(provider)
        settings = integration.settings or {}
        if settings.get("oauth_state") != state:
            raise ValidationError("Invalid OAuth state")

        code_verifier = settings.get("code_verifier")
        token_payload = await _exchange_code(
            config,
            code,
            _callback_url(callback_base_url, provider),
            code_verifier,
        )
        now = datetime.now(timezone.utc)
        token_payload["fetched_at"] = now.isoformat()
        expires_in = token_payload.get("expires_in")
        if expires_in:
            try:
                expires_at = now + timedelta(seconds=int(expires_in))
                token_payload["expires_at"] = expires_at.isoformat()
            except (TypeError, ValueError):
                pass
        self.integration_service.store_credentials(integration, token_payload)

        settings.pop("oauth_state", None)
        settings.pop("code_verifier", None)
        integration.settings = settings

    async def refresh_token(self, provider: str, refresh_token: str) -> Dict[str, str]:
        config = _get_provider(provider)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
        }
        if config.client_secret:
            data["client_secret"] = config.client_secret
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(config.token_url, data=data)
            response.raise_for_status()
            payload = response.json()
        now = datetime.now(timezone.utc)
        payload["fetched_at"] = now.isoformat()
        expires_in = payload.get("expires_in")
        if expires_in:
            try:
                payload["expires_at"] = (now + timedelta(seconds=int(expires_in))).isoformat()
            except (TypeError, ValueError):
                pass
        return payload


def _callback_url(callback_base_url: str, provider: str) -> str:
    base = callback_base_url.rstrip("/")
    return f"{base}/marketing/integrations/{provider}/callback"


def _get_provider(provider: str) -> OAuthProviderConfig:
    config = PROVIDERS.get(provider)
    if not config:
        raise ValidationError("Unsupported provider")
    return config


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


async def _exchange_code(
    config: OAuthProviderConfig,
    code: str,
    redirect_uri: str,
    code_verifier: Optional[str],
) -> Dict[str, str]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config.client_id,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth = None

    if config.client_secret:
        data["client_secret"] = config.client_secret
        if config.use_pkce:
            basic = f"{config.client_id}:{config.client_secret}".encode("utf-8")
            headers["Authorization"] = f"Basic {base64.b64encode(basic).decode('utf-8')}"

    if config.use_pkce and code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(config.token_url, data=data, headers=headers, auth=auth)
        response.raise_for_status()
        return response.json()
