"""Sync Chatwoot teams to Team model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.agent import Team

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


async def sync_teams(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync teams from Chatwoot to Team model.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored for teams - always full)
    """
    sync_client.start_sync("teams", "full")

    try:
        # GET /accounts/{id}/teams
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/teams",
        )

        teams = response if isinstance(response, list) else response.get("payload", [])
        sync_client.increment_fetched(len(teams))

        for team_data in teams:
            chatwoot_id = team_data.get("id")
            name = team_data.get("name", f"Team {chatwoot_id}")

            # Find existing by chatwoot_team_id
            existing = sync_client.db.query(Team).filter(
                Team.chatwoot_team_id == chatwoot_id
            ).first()

            # Map allow_auto_assign to assignment_rule
            auto_assign = team_data.get("allow_auto_assign", False)
            assignment_rule = "auto" if auto_assign else "manual"

            if existing:
                existing.name = name
                existing.description = team_data.get("description")
                existing.assignment_rule = assignment_rule
                existing.is_active = True
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
                logger.debug("chatwoot_team_updated", chatwoot_id=chatwoot_id, name=name)
            else:
                team = Team(
                    name=name,
                    description=team_data.get("description"),
                    domain="support",  # Chatwoot teams are support teams
                    assignment_rule=assignment_rule,
                    is_active=True,
                    chatwoot_team_id=chatwoot_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                sync_client.db.add(team)
                sync_client.increment_created()
                logger.debug("chatwoot_team_created", chatwoot_id=chatwoot_id, name=name)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_teams_synced",
            total=len(teams),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
