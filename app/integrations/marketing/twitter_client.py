"""Twitter/X API client."""
from __future__ import annotations

from typing import Optional, Iterable
from urllib.parse import urlencode

from app.config import settings
from app.integrations.marketing.base import BaseMarketingClient


class TwitterClient(BaseMarketingClient):
    platform = "twitter"
    base_url = "https://api.twitter.com/2"
    oauth_base_url = "https://twitter.com/i/oauth2/authorize"
    token_url = "https://api.twitter.com/2/oauth2/token"

    def __init__(
        self,
        access_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(
            access_token=access_token,
            webhook_secret=webhook_secret or settings.twitter_webhook_secret,
            timeout=timeout,
        )

    async def post_tweet(self, text: str) -> dict:
        response = await self.request("POST", "/tweets", payload={"text": text})
        return response.json()

    async def get_user(self, user_id: str) -> dict:
        response = await self.request("GET", f"/users/{user_id}")
        return response.json()

    async def get_tweet_metrics(self, tweet_id: str) -> dict:
        response = await self._client.get(
            f"{self.base_url}/tweets/{tweet_id}",
            params={"tweet.fields": "public_metrics"},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_authorization_url(
        self,
        redirect_uri: Optional[str],
        state: str,
        code_challenge: str,
        scopes: Optional[Iterable[str]] = None,
    ) -> str:
        redirect = redirect_uri or settings.twitter_redirect_uri
        if not settings.twitter_client_id or not redirect:
            raise ValueError("Twitter OAuth configuration missing")
        scope_value = " ".join(scopes or ["tweet.read", "tweet.write", "users.read", "offline.access"])
        query = urlencode(
            {
                "response_type": "code",
                "client_id": settings.twitter_client_id,
                "redirect_uri": redirect,
                "scope": scope_value,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.oauth_base_url}?{query}"

    async def exchange_code(self, code: str, redirect_uri: Optional[str], code_verifier: str) -> dict:
        redirect = redirect_uri or settings.twitter_redirect_uri
        if not settings.twitter_client_id or not redirect:
            raise ValueError("Twitter OAuth configuration missing")
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.twitter_client_id,
            "code": code,
            "redirect_uri": redirect,
            "code_verifier": code_verifier,
        }
        auth = None
        if settings.twitter_client_secret:
            auth = (settings.twitter_client_id, settings.twitter_client_secret)
        response = await self._client.post(self.token_url, data=data, auth=auth)
        response.raise_for_status()
        return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        if not settings.twitter_client_id:
            raise ValueError("Twitter OAuth configuration missing")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.twitter_client_id,
        }
        auth = None
        if settings.twitter_client_secret:
            auth = (settings.twitter_client_id, settings.twitter_client_secret)
        response = await self._client.post(self.token_url, data=data, auth=auth)
        response.raise_for_status()
        return response.json()
