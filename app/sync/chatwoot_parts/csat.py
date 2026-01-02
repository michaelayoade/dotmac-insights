"""Sync Chatwoot CSAT survey responses."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import httpx
import structlog

from app.models.conversation import Conversation, ConversationStatus
from app.models.support_csat import CSATResponse, CSATSurvey, SurveyType
from app.models.customer import Customer
from app.models.employee import Employee

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


async def sync_csat(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync CSAT survey responses from Chatwoot conversations.

    Iterates through resolved conversations and fetches their CSAT data.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to sync all resolved conversations or just recent ones
    """
    sync_client.start_sync("csat", "full" if full_sync else "incremental")

    try:
        # Get or create a default CSAT survey for Chatwoot responses
        default_survey = sync_client.db.query(CSATSurvey).filter(
            CSATSurvey.name == "Chatwoot CSAT Survey"
        ).first()

        if not default_survey:
            default_survey = CSATSurvey(
                name="Chatwoot CSAT Survey",
                description="Auto-created survey for Chatwoot CSAT responses",
                survey_type=SurveyType.CSAT.value,
                is_active=True,
            )
            sync_client.db.add(default_survey)
            sync_client.db.flush()

        # Query resolved conversations that don't have CSAT responses yet
        query = sync_client.db.query(Conversation).filter(
            Conversation.status == ConversationStatus.RESOLVED,
            Conversation.chatwoot_id.isnot(None),
        )

        if not full_sync:
            # Only check conversations resolved in last 30 days
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            query = query.filter(Conversation.resolved_at >= cutoff)

        conversations = query.all()
        sync_client.increment_fetched(len(conversations))

        for conv in conversations:
            # Check if we already have a CSAT response for this conversation
            existing = sync_client.db.query(CSATResponse).filter(
                CSATResponse.chatwoot_conversation_id == conv.chatwoot_id
            ).first()

            if existing:
                continue  # Already have CSAT for this conversation

            try:
                # GET /accounts/{id}/conversations/{conv_id}/csat_survey
                response = await sync_client._request(
                    client,
                    "GET",
                    f"/accounts/{sync_client.account_id}/conversations/{conv.chatwoot_id}/csat_survey_response",
                )

                if not response:
                    continue

                # Response might be wrapped
                csat_data = response if isinstance(response, dict) else {}
                if "payload" in csat_data:
                    csat_data = csat_data["payload"]

                rating = csat_data.get("rating")
                if rating is None:
                    continue  # No CSAT response for this conversation

                # Find customer
                customer_id = None
                if conv.customer_id:
                    customer_id = conv.customer_id
                elif csat_data.get("contact_id"):
                    customer = sync_client.db.query(Customer).filter(
                        Customer.chatwoot_contact_id == csat_data.get("contact_id")
                    ).first()
                    if customer:
                        customer_id = customer.id

                # Find agent
                agent_id = None
                if csat_data.get("assigned_agent_id"):
                    employee = sync_client.db.query(Employee).filter(
                        Employee.chatwoot_agent_id == csat_data.get("assigned_agent_id")
                    ).first()
                    if employee:
                        # Note: CSATResponse links to Agent, not Employee
                        # We'd need to find or create an Agent for this employee
                        pass

                csat_response = CSATResponse(
                    survey_id=default_survey.id,
                    customer_id=customer_id,
                    rating=rating,
                    feedback_text=csat_data.get("feedback_message"),
                    responded_at=datetime.now(timezone.utc),
                    chatwoot_conversation_id=conv.chatwoot_id,
                )
                sync_client.db.add(csat_response)
                sync_client.increment_created()
                logger.debug(
                    "chatwoot_csat_synced",
                    conversation_id=conv.chatwoot_id,
                    rating=rating,
                )

            except Exception as e:
                # Log but continue - don't fail entire sync for one conversation
                logger.warning(
                    "chatwoot_csat_fetch_failed",
                    conversation_id=conv.chatwoot_id,
                    error=str(e),
                )
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_csat_synced",
            conversations_checked=len(conversations),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
