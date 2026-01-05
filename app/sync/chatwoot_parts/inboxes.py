"""Sync Chatwoot inboxes to OmniChannel model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.omni import OmniChannel, OmniChannelType

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


def _map_channel_type(chatwoot_type: str) -> str:
    """Map Chatwoot channel type to OmniChannelType."""
    type_map = {
        "Channel::WebWidget": OmniChannelType.WEB.value,
        "Channel::Email": OmniChannelType.EMAIL.value,
        "Channel::Sms": OmniChannelType.SMS.value,
        "Channel::Whatsapp": OmniChannelType.WHATSAPP.value,
        "Channel::Api": OmniChannelType.CUSTOM.value,
        "Channel::FacebookPage": OmniChannelType.CUSTOM.value,
        "Channel::TwitterProfile": OmniChannelType.CUSTOM.value,
        "Channel::TelegramChannel": OmniChannelType.CUSTOM.value,
        "Channel::Line": OmniChannelType.CUSTOM.value,
    }
    return type_map.get(chatwoot_type, OmniChannelType.CHATWOOT.value)


async def sync_inboxes(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync inboxes from Chatwoot to OmniChannel model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored for inboxes - always full)
    """
    sync_client.start_sync("inboxes", "full")

    try:
        # GET /accounts/{id}/inboxes
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/inboxes",
        )

        inboxes = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(inboxes))

        for inbox_data in inboxes:
            chatwoot_id = inbox_data.get("id")
            name = inbox_data.get("name", f"Inbox {chatwoot_id}")

            # Find existing by chatwoot_inbox_id
            existing = sync_client.db.query(OmniChannel).filter(
                OmniChannel.chatwoot_inbox_id == chatwoot_id
            ).first()

            # Build config from inbox data
            config = {
                "chatwoot_channel_type": inbox_data.get("channel_type"),
                "email": inbox_data.get("email"),
                "phone_number": inbox_data.get("phone_number"),
                "greeting_enabled": inbox_data.get("greeting_enabled"),
                "greeting_message": inbox_data.get("greeting_message"),
                "working_hours_enabled": inbox_data.get("working_hours_enabled"),
                "out_of_office_message": inbox_data.get("out_of_office_message"),
                "timezone": inbox_data.get("timezone"),
                "enable_auto_assignment": inbox_data.get("enable_auto_assignment"),
            }

            channel_type = _map_channel_type(inbox_data.get("channel_type", ""))

            if existing:
                existing.name = name
                existing.type = channel_type
                existing.config = config
                existing.is_active = inbox_data.get("active", True)
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_inbox_updated", chatwoot_id=chatwoot_id, name=name)
            else:
                channel = OmniChannel(
                    name=name,
                    type=channel_type,
                    config=config,
                    is_active=inbox_data.get("active", True),
                    chatwoot_inbox_id=chatwoot_id,
                )
                sync_client.db.add(channel)
                sync_client.increment_created()
                logger.debug("chatwoot_inbox_created", chatwoot_id=chatwoot_id, name=name)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_inboxes_synced",
            total=len(inboxes),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
