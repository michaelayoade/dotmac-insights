"""LinkedIn Marketing API client."""
from __future__ import annotations

from typing import Optional, Iterable
from urllib.parse import urlencode, quote

from app.config import settings
from app.integrations.marketing.base import BaseMarketingClient


class LinkedInClient(BaseMarketingClient):
    platform = "linkedin"
    base_url = "https://api.linkedin.com/v2"
    oauth_base_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    def __init__(
        self,
        access_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(
            access_token=access_token,
            webhook_secret=webhook_secret or settings.linkedin_webhook_secret,
            timeout=timeout,
        )

    async def get_profile(self) -> dict:
        response = await self.request("GET", "/me")
        return response.json()

    async def create_post(self, author: str, text: str) -> dict:
        if not author:
            raise ValueError("LinkedIn author is required")
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        headers = self._headers()
        headers["X-Restli-Protocol-Version"] = "2.0.0"
        response = await self._client.post(f"{self.base_url}/ugcPosts", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def get_post_metrics(self, urn: str) -> dict:
        if not urn:
            raise ValueError("LinkedIn post URN is required")
        encoded = quote(urn, safe="")
        response = await self._client.get(
            f"{self.base_url}/socialActions/{encoded}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_authorization_url(
        self,
        redirect_uri: Optional[str],
        state: str,
        scopes: Optional[Iterable[str]] = None,
    ) -> str:
        redirect = redirect_uri or settings.linkedin_redirect_uri
        if not settings.linkedin_client_id or not redirect:
            raise ValueError("LinkedIn OAuth configuration missing")
        scope_value = " ".join(scopes or ["r_liteprofile", "w_member_social", "r_organization_social"])
        query = urlencode(
            {
                "response_type": "code",
                "client_id": settings.linkedin_client_id,
                "redirect_uri": redirect,
                "state": state,
                "scope": scope_value,
            }
        )
        return f"{self.oauth_base_url}?{query}"

    async def exchange_code(self, code: str, redirect_uri: Optional[str]) -> dict:
        redirect = redirect_uri or settings.linkedin_redirect_uri
        if not settings.linkedin_client_id or not settings.linkedin_client_secret or not redirect:
            raise ValueError("LinkedIn OAuth configuration missing")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret,
            "redirect_uri": redirect,
        }
        response = await self._client.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        if not settings.linkedin_client_id or not settings.linkedin_client_secret:
            raise ValueError("LinkedIn OAuth configuration missing")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret,
        }
        response = await self._client.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()
