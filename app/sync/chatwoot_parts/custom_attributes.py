"""Sync Chatwoot custom attribute definitions to TicketCustomField model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.support_tags import TicketCustomField, CustomFieldType

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


def _map_attribute_type(chatwoot_type: str) -> str:
    """Map Chatwoot attribute display type to CustomFieldType."""
    type_map = {
        "text": CustomFieldType.TEXT.value,
        "number": CustomFieldType.NUMBER.value,
        "link": CustomFieldType.URL.value,
        "date": CustomFieldType.DATE.value,
        "list": CustomFieldType.DROPDOWN.value,
        "checkbox": CustomFieldType.CHECKBOX.value,
    }
    return type_map.get(chatwoot_type, CustomFieldType.TEXT.value)


async def sync_custom_attributes(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync custom attribute definitions from Chatwoot to TicketCustomField model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored - always full)
    """
    sync_client.start_sync("custom_attributes", "full")

    try:
        # GET /accounts/{id}/custom_attribute_definitions
        # Filter for conversation_attribute (ticket-level attributes)
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/custom_attribute_definitions",
            params={"attribute_model": "conversation_attribute"},
        )

        attributes = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(attributes))

        for attr_data in attributes:
            chatwoot_id = attr_data.get("id")
            attr_key = attr_data.get("attribute_key", f"attr_{chatwoot_id}")
            display_name = attr_data.get("attribute_display_name", attr_key)

            # Find existing by chatwoot_attribute_id
            existing = sync_client.db.query(TicketCustomField).filter(
                TicketCustomField.chatwoot_attribute_id == chatwoot_id
            ).first()

            field_type = _map_attribute_type(attr_data.get("attribute_display_type", "text"))

            # Build options for list/dropdown types
            options = None
            attr_values = attr_data.get("attribute_values", [])
            if attr_values and field_type == CustomFieldType.DROPDOWN.value:
                options = [{"value": v, "label": v} for v in attr_values]

            if existing:
                existing.name = display_name
                existing.field_key = attr_key
                existing.field_type = field_type
                existing.options = options
                existing.default_value = attr_data.get("default_value")
                existing.description = attr_data.get("attribute_description")
                existing.is_active = True
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_custom_attr_updated", chatwoot_id=chatwoot_id, key=attr_key)
            else:
                # Check if field_key already exists
                existing_by_key = sync_client.db.query(TicketCustomField).filter(
                    TicketCustomField.field_key == attr_key
                ).first()

                if existing_by_key:
                    # Link existing to Chatwoot
                    existing_by_key.chatwoot_attribute_id = chatwoot_id
                    existing_by_key.name = display_name
                    existing_by_key.field_type = field_type
                    existing_by_key.options = options
                    sync_client.increment_updated()
                    logger.debug("chatwoot_custom_attr_linked", chatwoot_id=chatwoot_id, key=attr_key)
                    continue

                field = TicketCustomField(
                    name=display_name,
                    field_key=attr_key,
                    field_type=field_type,
                    options=options,
                    default_value=attr_data.get("default_value"),
                    description=attr_data.get("attribute_description"),
                    is_active=True,
                    chatwoot_attribute_id=chatwoot_id,
                )
                sync_client.db.add(field)
                sync_client.increment_created()
                logger.debug("chatwoot_custom_attr_created", chatwoot_id=chatwoot_id, key=attr_key)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_custom_attributes_synced",
            total=len(attributes),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
