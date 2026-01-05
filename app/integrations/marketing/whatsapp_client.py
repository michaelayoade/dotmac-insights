"""WhatsApp Business API client."""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.integrations.marketing.base import BaseMarketingClient
from app.integrations.marketing.meta_client import MetaBusinessClient


class WhatsAppBusinessClient(BaseMarketingClient):
    platform = "whatsapp"
    base_url = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        access_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(
            access_token=access_token or settings.whatsapp_access_token,
            webhook_secret=webhook_secret or settings.whatsapp_webhook_secret,
            timeout=timeout,
        )

    async def send_message(self, phone_number_id: str, payload: dict) -> dict:
        response = await self.request("POST", f"/{phone_number_id}/messages", payload=payload)
        return response.json()

    async def refresh_access_token(self, access_token: str) -> dict:
        meta = MetaBusinessClient(access_token=access_token)
        try:
            return await meta.refresh_access_token(access_token)
        finally:
            await meta.close()
