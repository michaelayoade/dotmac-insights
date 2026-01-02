"""Sync Chatwoot reports/metrics to ChatwootMetricSnapshot model."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Dict, Any

import httpx
import structlog

from app.models.chatwoot_metrics import ChatwootMetricSnapshot, MetricPeriod, MetricLevel
from app.models.employee import Employee
from app.models.omni import OmniChannel
from app.models.agent import Team

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


async def _fetch_report_summary(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    report_type: str,
    since: int,
    until: int,
    entity_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch report summary from Chatwoot API.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client
        report_type: One of 'account', 'agent', 'inbox', 'team'
        since: Unix timestamp for start
        until: Unix timestamp for end
        entity_id: ID of the entity (agent_id, inbox_id, team_id)

    Returns:
        Report data dict or None if not available
    """
    try:
        params = {
            "type": report_type,
            "since": since,
            "until": until,
        }
        if entity_id and report_type != "account":
            params["id"] = entity_id

        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/reports/summary",
            params=params,
        )
        return response
    except Exception as e:
        logger.warning(
            "chatwoot_report_fetch_failed",
            report_type=report_type,
            entity_id=entity_id,
            error=str(e),
        )
        return None


async def sync_reports(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync report metrics from Chatwoot.

    Fetches account-level, agent-level, inbox-level, and team-level metrics
    for the previous day (or last 30 days if full_sync).

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to sync last 30 days or just previous day
    """
    sync_client.start_sync("reports", "full" if full_sync else "incremental")

    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if full_sync:
            # Sync last 30 days
            days_to_sync = 30
        else:
            # Sync previous day only
            days_to_sync = 1

        for day_offset in range(1, days_to_sync + 1):
            period_end = today_start - timedelta(days=day_offset - 1)
            period_start = today_start - timedelta(days=day_offset)

            since_ts = int(period_start.timestamp())
            until_ts = int(period_end.timestamp())

            # Check if we already have account-level metrics for this period
            existing = sync_client.db.query(ChatwootMetricSnapshot).filter(
                ChatwootMetricSnapshot.metric_level == MetricLevel.ACCOUNT.value,
                ChatwootMetricSnapshot.period_type == MetricPeriod.DAILY.value,
                ChatwootMetricSnapshot.period_start == period_start,
            ).first()

            if existing and not full_sync:
                continue  # Already have this day's metrics

            # Fetch account-level metrics
            account_data = await _fetch_report_summary(
                sync_client, client, "account", since_ts, until_ts
            )

            if account_data:
                _save_metric_snapshot(
                    sync_client,
                    level=MetricLevel.ACCOUNT,
                    period_start=period_start,
                    period_end=period_end,
                    data=account_data,
                )

            # Fetch agent-level metrics
            employees = sync_client.db.query(Employee).filter(
                Employee.chatwoot_agent_id.isnot(None)
            ).all()

            for employee in employees:
                agent_data = await _fetch_report_summary(
                    sync_client, client, "agent", since_ts, until_ts,
                    entity_id=employee.chatwoot_agent_id
                )
                if agent_data:
                    _save_metric_snapshot(
                        sync_client,
                        level=MetricLevel.AGENT,
                        period_start=period_start,
                        period_end=period_end,
                        data=agent_data,
                        agent_id=employee.id,
                        chatwoot_agent_id=employee.chatwoot_agent_id,
                    )

            # Fetch inbox-level metrics
            inboxes = sync_client.db.query(OmniChannel).filter(
                OmniChannel.chatwoot_inbox_id.isnot(None)
            ).all()

            for inbox in inboxes:
                inbox_data = await _fetch_report_summary(
                    sync_client, client, "inbox", since_ts, until_ts,
                    entity_id=inbox.chatwoot_inbox_id
                )
                if inbox_data:
                    _save_metric_snapshot(
                        sync_client,
                        level=MetricLevel.INBOX,
                        period_start=period_start,
                        period_end=period_end,
                        data=inbox_data,
                        inbox_id=inbox.id,
                        chatwoot_inbox_id=inbox.chatwoot_inbox_id,
                    )

            # Fetch team-level metrics
            teams = sync_client.db.query(Team).filter(
                Team.chatwoot_team_id.isnot(None)
            ).all()

            for team in teams:
                team_data = await _fetch_report_summary(
                    sync_client, client, "team", since_ts, until_ts,
                    entity_id=team.chatwoot_team_id
                )
                if team_data:
                    _save_metric_snapshot(
                        sync_client,
                        level=MetricLevel.TEAM,
                        period_start=period_start,
                        period_end=period_end,
                        data=team_data,
                        team_id=team.id,
                        chatwoot_team_id=team.chatwoot_team_id,
                    )

            sync_client.increment_fetched(1)  # Count days processed

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_reports_synced",
            days_synced=days_to_sync,
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


def _save_metric_snapshot(
    sync_client: "ChatwootSync",
    level: MetricLevel,
    period_start: datetime,
    period_end: datetime,
    data: Dict[str, Any],
    agent_id: Optional[int] = None,
    inbox_id: Optional[int] = None,
    team_id: Optional[int] = None,
    chatwoot_agent_id: Optional[int] = None,
    chatwoot_inbox_id: Optional[int] = None,
    chatwoot_team_id: Optional[int] = None,
) -> None:
    """Save a metric snapshot record."""
    # Check for existing record
    query = sync_client.db.query(ChatwootMetricSnapshot).filter(
        ChatwootMetricSnapshot.metric_level == level.value,
        ChatwootMetricSnapshot.period_type == MetricPeriod.DAILY.value,
        ChatwootMetricSnapshot.period_start == period_start,
    )

    if agent_id:
        query = query.filter(ChatwootMetricSnapshot.agent_id == agent_id)
    if inbox_id:
        query = query.filter(ChatwootMetricSnapshot.inbox_id == inbox_id)
    if team_id:
        query = query.filter(ChatwootMetricSnapshot.team_id == team_id)

    existing = query.first()

    # Extract metrics from data
    conversations_count = data.get("conversations_count", 0)
    incoming = data.get("incoming_messages_count", 0)
    outgoing = data.get("outgoing_messages_count", 0)
    resolved = data.get("resolutions_count", 0)
    avg_first_response = data.get("avg_first_response_time")
    avg_resolution = data.get("avg_resolution_time")

    # CSAT metrics
    csat_total = data.get("csat_total_count", 0)
    csat_positive = data.get("csat_positive_count", 0)
    csat_score = None
    if csat_total > 0:
        csat_score = Decimal(str(csat_positive / csat_total * 100))

    if existing:
        existing.conversations_count = conversations_count
        existing.incoming_messages_count = incoming
        existing.outgoing_messages_count = outgoing
        existing.resolved_count = resolved
        existing.avg_first_response_time = avg_first_response
        existing.avg_resolution_time = avg_resolution
        existing.csat_total_responses = csat_total
        existing.csat_positive_responses = csat_positive
        existing.csat_score = csat_score
        existing.raw_metrics = data
        existing.synced_at = datetime.now(timezone.utc)
        sync_client.increment_updated()
    else:
        snapshot = ChatwootMetricSnapshot(
            period_type=MetricPeriod.DAILY.value,
            period_start=period_start,
            period_end=period_end,
            metric_level=level.value,
            agent_id=agent_id,
            inbox_id=inbox_id,
            team_id=team_id,
            chatwoot_agent_id=chatwoot_agent_id,
            chatwoot_inbox_id=chatwoot_inbox_id,
            chatwoot_team_id=chatwoot_team_id,
            conversations_count=conversations_count,
            incoming_messages_count=incoming,
            outgoing_messages_count=outgoing,
            resolved_count=resolved,
            avg_first_response_time=avg_first_response,
            avg_resolution_time=avg_resolution,
            csat_total_responses=csat_total,
            csat_positive_responses=csat_positive,
            csat_score=csat_score,
            raw_metrics=data,
            synced_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        sync_client.db.add(snapshot)
        sync_client.increment_created()
