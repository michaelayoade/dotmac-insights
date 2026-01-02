"""Sync Chatwoot automation rules to AutomationRule model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.support_automation import AutomationRule, AutomationTrigger

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


def _map_event_to_trigger(event_name: str) -> str:
    """Map Chatwoot event name to AutomationTrigger."""
    event_map = {
        "conversation_created": AutomationTrigger.TICKET_CREATED.value,
        "conversation_updated": AutomationTrigger.TICKET_UPDATED.value,
        "message_created": AutomationTrigger.CUSTOMER_REPLIED.value,
        "conversation_status_changed": AutomationTrigger.TICKET_STATUS_CHANGED.value,
        "conversation_assigned": AutomationTrigger.TICKET_ASSIGNED.value,
    }
    return event_map.get(event_name, AutomationTrigger.TICKET_UPDATED.value)


async def sync_automation_rules(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync automation rules from Chatwoot to AutomationRule model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored - always full)
    """
    sync_client.start_sync("automation_rules", "full")

    try:
        # GET /accounts/{id}/automation_rules
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/automation_rules",
        )

        rules = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(rules))

        for rule_data in rules:
            chatwoot_id = rule_data.get("id")
            name = rule_data.get("name", f"Rule {chatwoot_id}")

            # Find existing by chatwoot_rule_id
            existing = sync_client.db.query(AutomationRule).filter(
                AutomationRule.chatwoot_rule_id == chatwoot_id
            ).first()

            trigger = _map_event_to_trigger(rule_data.get("event_name", ""))

            # Chatwoot conditions and actions are already in JSON format
            conditions = rule_data.get("conditions", [])
            actions = rule_data.get("actions", [])

            if existing:
                existing.name = name
                existing.description = rule_data.get("description")
                existing.trigger = trigger
                existing.conditions = conditions
                existing.actions = actions
                existing.is_active = rule_data.get("active", True)
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_automation_rule_updated", chatwoot_id=chatwoot_id, name=name)
            else:
                rule = AutomationRule(
                    name=name,
                    description=rule_data.get("description"),
                    trigger=trigger,
                    conditions=conditions,
                    actions=actions,
                    is_active=rule_data.get("active", True),
                    chatwoot_rule_id=chatwoot_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                sync_client.db.add(rule)
                sync_client.increment_created()
                logger.debug("chatwoot_automation_rule_created", chatwoot_id=chatwoot_id, name=name)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_automation_rules_synced",
            total=len(rules),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
