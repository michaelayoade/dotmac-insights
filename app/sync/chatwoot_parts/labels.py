"""Sync Chatwoot labels to TicketTag model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.support_tags import TicketTag

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


async def sync_labels(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync labels from Chatwoot to TicketTag model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored for labels - always full)
    """
    sync_client.start_sync("labels", "full")

    try:
        # GET /accounts/{id}/labels
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/labels",
        )

        labels = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(labels))

        for label_data in labels:
            chatwoot_id = label_data.get("id")
            title = label_data.get("title", f"Label {chatwoot_id}")

            # Find existing by chatwoot_label_id
            existing = sync_client.db.query(TicketTag).filter(
                TicketTag.chatwoot_label_id == chatwoot_id
            ).first()

            # Chatwoot colors are without # prefix
            color = label_data.get("color")
            if color and not color.startswith("#"):
                color = f"#{color}"

            if existing:
                existing.name = title
                existing.color = color
                existing.description = label_data.get("description")
                existing.is_active = True
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_label_updated", chatwoot_id=chatwoot_id, title=title)
            else:
                # Check if tag with same name exists (not from Chatwoot)
                existing_by_name = sync_client.db.query(TicketTag).filter(
                    TicketTag.name == title
                ).first()

                if existing_by_name:
                    # Link existing tag to Chatwoot
                    existing_by_name.chatwoot_label_id = chatwoot_id
                    existing_by_name.color = color or existing_by_name.color
                    existing_by_name.description = label_data.get("description") or existing_by_name.description
                    existing_by_name.last_synced_at = datetime.now(timezone.utc)
                    sync_client.increment_updated()
                    logger.debug("chatwoot_label_linked", chatwoot_id=chatwoot_id, title=title)
                else:
                    tag = TicketTag(
                        name=title,
                        color=color,
                        description=label_data.get("description"),
                        is_active=True,
                        chatwoot_label_id=chatwoot_id,
                        last_synced_at=datetime.now(timezone.utc),
                    )
                    sync_client.db.add(tag)
                    sync_client.increment_created()
                    logger.debug("chatwoot_label_created", chatwoot_id=chatwoot_id, title=title)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_labels_synced",
            total=len(labels),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
