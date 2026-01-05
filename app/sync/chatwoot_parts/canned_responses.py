"""Sync Chatwoot canned responses to CannedResponse model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.support_canned import CannedResponse, CannedResponseScope

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


async def sync_canned_responses(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync canned responses from Chatwoot to CannedResponse model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored - always full)
    """
    sync_client.start_sync("canned_responses", "full")

    try:
        # GET /accounts/{id}/canned_responses
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/canned_responses",
        )

        responses = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(responses))

        for resp_data in responses:
            chatwoot_id = resp_data.get("id")
            short_code = resp_data.get("short_code", "")

            # Find existing by chatwoot_id
            existing = sync_client.db.query(CannedResponse).filter(
                CannedResponse.chatwoot_id == chatwoot_id
            ).first()

            # Chatwoot canned responses are global scope
            if existing:
                existing.name = short_code or f"Canned Response {chatwoot_id}"
                existing.shortcode = short_code if short_code else None
                existing.content = resp_data.get("content", "")
                existing.is_active = True
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_canned_response_updated", chatwoot_id=chatwoot_id, shortcode=short_code)
            else:
                # Check if shortcode already exists
                if short_code:
                    existing_by_code = sync_client.db.query(CannedResponse).filter(
                        CannedResponse.shortcode == short_code
                    ).first()
                    if existing_by_code:
                        # Link existing to Chatwoot
                        existing_by_code.chatwoot_id = chatwoot_id
                        existing_by_code.content = resp_data.get("content", existing_by_code.content)
                        existing_by_code.last_synced_at = datetime.now(timezone.utc)
                        sync_client.increment_updated()
                        logger.debug("chatwoot_canned_response_linked", chatwoot_id=chatwoot_id, shortcode=short_code)
                        continue

                canned = CannedResponse(
                    name=short_code or f"Canned Response {chatwoot_id}",
                    shortcode=short_code if short_code else None,
                    content=resp_data.get("content", ""),
                    scope=CannedResponseScope.GLOBAL.value,
                    is_active=True,
                    chatwoot_id=chatwoot_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                sync_client.db.add(canned)
                sync_client.increment_created()
                logger.debug("chatwoot_canned_response_created", chatwoot_id=chatwoot_id, shortcode=short_code)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_canned_responses_synced",
            total=len(responses),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
