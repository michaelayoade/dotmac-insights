"""Meta (Facebook/Instagram) Graph API client."""
from __future__ import annotations

from typing import Optional, Iterable
from urllib.parse import urlencode

from app.config import settings
from app.integrations.marketing.base import BaseMarketingClient


class MetaBusinessClient(BaseMarketingClient):
    platform = "meta"
    base_url = "https://graph.facebook.com/v18.0"
    oauth_base_url = "https://www.facebook.com/v18.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"

    def __init__(
        self,
        access_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(
            access_token=access_token,
            webhook_secret=webhook_secret or settings.meta_webhook_secret,
            timeout=timeout,
        )

    async def list_pages(self) -> dict:
        response = await self.request("GET", "/me/accounts")
        return response.json()

    async def create_post(self, page_id: str, message: str) -> dict:
        response = await self.request("POST", f"/{page_id}/feed", payload={"message": message})
        return response.json()

    async def create_photo_post(self, page_id: str, url: str, caption: str | None = None) -> dict:
        payload = {"url": url}
        if caption:
            payload["caption"] = caption
        response = await self.request("POST", f"/{page_id}/photos", payload=payload)
        return response.json()

    async def create_instagram_media(
        self,
        ig_user_id: str,
        url: str,
        caption: str | None = None,
        media_type: str | None = None,
    ) -> dict:
        payload = {"image_url": url}
        if media_type:
            payload["media_type"] = media_type
            if media_type.upper() == "VIDEO":
                payload.pop("image_url", None)
                payload["video_url"] = url
        if caption:
            payload["caption"] = caption
        response = await self.request("POST", f"/{ig_user_id}/media", payload=payload)
        return response.json()

    async def publish_instagram_media(self, ig_user_id: str, creation_id: str) -> dict:
        response = await self.request(
            "POST",
            f"/{ig_user_id}/media_publish",
            payload={"creation_id": creation_id},
        )
        return response.json()

    async def get_post_metrics(self, post_id: str) -> dict:
        response = await self._client.get(
            f"{self.base_url}/{post_id}",
            params={"fields": "permalink_url,comments.summary(true),reactions.summary(true),shares"},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_instagram_media_metrics(self, media_id: str) -> dict:
        response = await self._client.get(
            f"{self.base_url}/{media_id}",
            params={"fields": "like_count,comments_count,permalink,media_type"},
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
        redirect = redirect_uri or settings.meta_redirect_uri
        if not settings.meta_app_id or not redirect:
            raise ValueError("Meta OAuth configuration missing")
        scope_value = ",".join(scopes or ["pages_show_list", "pages_read_engagement", "pages_manage_posts"])
        query = urlencode(
            {
                "client_id": settings.meta_app_id,
                "redirect_uri": redirect,
                "state": state,
                "scope": scope_value,
                "response_type": "code",
            }
        )
        return f"{self.oauth_base_url}?{query}"

    async def exchange_code(self, code: str, redirect_uri: Optional[str]) -> dict:
        redirect = redirect_uri or settings.meta_redirect_uri
        if not settings.meta_app_id or not settings.meta_app_secret or not redirect:
            raise ValueError("Meta OAuth configuration missing")
        payload = {
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": redirect,
            "code": code,
        }
        response = await self._client.get(self.token_url, params=payload)
        response.raise_for_status()
        return response.json()

    async def refresh_access_token(self, access_token: str) -> dict:
        if not settings.meta_app_id or not settings.meta_app_secret:
            raise ValueError("Meta OAuth configuration missing")
        payload = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "fb_exchange_token": access_token,
        }
        response = await self._client.get(self.token_url, params=payload)
        response.raise_for_status()
        return response.json()
