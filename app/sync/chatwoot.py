from __future__ import annotations

import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient
from app.models.sync_log import SyncSource
from app.models.customer import Customer
from app.models.conversation import Conversation, Message, ConversationStatus

logger = structlog.get_logger()


class ChatwootSync(BaseSyncClient):
    """Sync client for Chatwoot customer support platform."""

    source = SyncSource.CHATWOOT

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.chatwoot_api_url.rstrip("/")
        self.api_token = settings.chatwoot_api_token
        self.account_id = settings.chatwoot_account_id

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for Chatwoot API."""
        return {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make authenticated request to Chatwoot API."""
        response = await client.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=self._get_headers(),
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        data_key: str = "data",
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all records with pagination."""
        all_records = []
        page = 1

        while True:
            request_params = {"page": page, **(params or {})}
            response = await self._request(client, "GET", endpoint, params=request_params)

            data = response.get(data_key) if data_key else response
            if not data:
                break

            if isinstance(data, list):
                all_records.extend(data)
                self.increment_fetched(len(data))

                # Check if there are more pages
                meta = response.get("meta", {})
                if page >= meta.get("total_pages", page):
                    break
            else:
                all_records.append(data)
                break

            page += 1

        return all_records

    async def test_connection(self) -> bool:
        """Test if Chatwoot API connection is working."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await self._request(
                    client,
                    "GET",
                    f"/accounts/{self.account_id}/conversations",
                    params={"page": 1},
                )
            return True
        except Exception as e:
            logger.error("chatwoot_connection_test_failed", error=str(e))
            return False

    async def sync_all(self, full_sync: bool = False):
        """Sync all entities from Chatwoot."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_contacts(client, full_sync)
            await self.sync_conversations(client, full_sync)

    async def sync_contacts_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Contacts with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_contacts(client, full_sync)

    async def sync_conversations_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Conversations with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_conversations(client, full_sync)

    async def sync_contacts(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync contacts from Chatwoot and link to customers."""
        self.start_sync("contacts", "full" if full_sync else "incremental")

        try:
            contacts = await self._fetch_paginated(
                client,
                f"/accounts/{self.account_id}/contacts",
                data_key="payload",
            )

            for contact_data in contacts:
                chatwoot_id = contact_data.get("id")

                # Try to find matching customer
                email = contact_data.get("email")
                phone = contact_data.get("phone_number")
                _name = contact_data.get("name", "")  # Available for future use

                customer = None

                # Match by email first
                if email:
                    customer = self.db.query(Customer).filter(
                        Customer.email == email
                    ).first()

                # Then try by phone
                if not customer and phone:
                    # Normalize phone number (remove spaces, dashes)
                    normalized_phone = phone.replace(" ", "").replace("-", "")
                    customer = self.db.query(Customer).filter(
                        Customer.phone.ilike(f"%{normalized_phone[-10:]}%")
                    ).first()

                if customer:
                    customer.chatwoot_contact_id = chatwoot_id
                    customer.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                    logger.debug("chatwoot_contact_linked", customer_id=customer.id, chatwoot_id=chatwoot_id)

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_conversations(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync conversations/tickets from Chatwoot."""
        self.start_sync("conversations", "full" if full_sync else "incremental")

        try:
            # Fetch all conversations
            conversations = await self._fetch_paginated(
                client,
                f"/accounts/{self.account_id}/conversations",
                data_key="data",
                params={"status": "all"},
            )

            for conv_data in conversations:
                chatwoot_id = conv_data.get("id")
                existing = self.db.query(Conversation).filter(
                    Conversation.chatwoot_id == chatwoot_id
                ).first()

                # Find customer by contact_id
                contact_id = conv_data.get("meta", {}).get("sender", {}).get("id")
                customer = None
                if contact_id:
                    customer = self.db.query(Customer).filter(
                        Customer.chatwoot_contact_id == contact_id
                    ).first()

                # Map status
                status_str = str(conv_data.get("status", 0))
                status_map = {
                    "0": ConversationStatus.OPEN,
                    "1": ConversationStatus.RESOLVED,
                    "2": ConversationStatus.PENDING,
                    "3": ConversationStatus.SNOOZED,
                    "open": ConversationStatus.OPEN,
                    "resolved": ConversationStatus.RESOLVED,
                    "pending": ConversationStatus.PENDING,
                    "snoozed": ConversationStatus.SNOOZED,
                }
                status = status_map.get(status_str, ConversationStatus.OPEN)

                # Extract metadata
                meta = conv_data.get("meta", {})
                assignee = meta.get("assignee", {})
                inbox = conv_data.get("inbox", {})

                # Parse timestamps
                created_at = None
                if conv_data.get("created_at"):
                    try:
                        created_at = datetime.fromtimestamp(conv_data["created_at"])
                    except (ValueError, TypeError):
                        created_at = datetime.utcnow()

                # Calculate response and resolution times
                first_response_time = None
                resolution_time = None

                additional_attrs = conv_data.get("additional_attributes", {})
                if additional_attrs:
                    first_response_time = additional_attrs.get("first_response_time")
                    resolution_time = additional_attrs.get("resolution_time")

                # Get labels
                labels = conv_data.get("labels", [])
                labels_str = ",".join(labels) if labels else None

                if existing:
                    existing.customer_id = customer.id if customer else None
                    existing.chatwoot_contact_id = contact_id
                    existing.status = status
                    existing.inbox_name = inbox.get("name")
                    existing.channel = inbox.get("channel_type")
                    existing.assigned_agent_id = assignee.get("id")
                    existing.assigned_agent_name = assignee.get("name")
                    existing.message_count = conv_data.get("messages_count", 0)
                    existing.labels = labels_str
                    existing.last_activity_at = datetime.utcnow()
                    existing.last_synced_at = datetime.utcnow()

                    if first_response_time:
                        existing.first_response_time_seconds = int(first_response_time)

                    if resolution_time:
                        existing.resolution_time_seconds = int(resolution_time)

                    if status == ConversationStatus.RESOLVED and not existing.resolved_at:
                        existing.resolved_at = datetime.utcnow()

                    self.increment_updated()
                else:
                    conversation = Conversation(
                        chatwoot_id=chatwoot_id,
                        customer_id=customer.id if customer else None,
                        chatwoot_contact_id=contact_id,
                        status=status,
                        inbox_name=inbox.get("name"),
                        channel=inbox.get("channel_type"),
                        assigned_agent_id=assignee.get("id"),
                        assigned_agent_name=assignee.get("name"),
                        message_count=conv_data.get("messages_count", 0),
                        labels=labels_str,
                        created_at=created_at or datetime.utcnow(),
                    )

                    if first_response_time:
                        conversation.first_response_time_seconds = int(first_response_time)

                    if resolution_time:
                        conversation.resolution_time_seconds = int(resolution_time)

                    if status == ConversationStatus.RESOLVED:
                        conversation.resolved_at = datetime.utcnow()

                    self.db.add(conversation)
                    self.increment_created()

                # Sync messages for this conversation
                if chatwoot_id is not None:
                    await self._sync_conversation_messages(client, chatwoot_id)

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def _sync_conversation_messages(self, client: httpx.AsyncClient, conversation_chatwoot_id: int):
        """Sync messages for a specific conversation."""
        try:
            response = await self._request(
                client,
                "GET",
                f"/accounts/{self.account_id}/conversations/{conversation_chatwoot_id}/messages",
            )

            messages = response if isinstance(response, list) else response.get("payload", [])

            conversation = self.db.query(Conversation).filter(
                Conversation.chatwoot_id == conversation_chatwoot_id
            ).first()

            if not conversation:
                return

            for msg_data in messages:
                chatwoot_id = msg_data.get("id")
                existing = self.db.query(Message).filter(Message.chatwoot_id == chatwoot_id).first()

                if existing:
                    continue  # Messages don't change, skip if exists

                # Parse timestamp
                created_at = None
                if msg_data.get("created_at"):
                    try:
                        created_at = datetime.fromtimestamp(msg_data["created_at"])
                    except (ValueError, TypeError):
                        created_at = datetime.utcnow()

                sender = msg_data.get("sender", {})

                message = Message(
                    chatwoot_id=chatwoot_id,
                    conversation_id=conversation.id,
                    content=msg_data.get("content"),
                    message_type=str(msg_data.get("message_type", "")),
                    is_private=msg_data.get("private", False),
                    sender_type=sender.get("type"),
                    sender_id=sender.get("id"),
                    sender_name=sender.get("name"),
                    created_at=created_at or datetime.utcnow(),
                )
                self.db.add(message)

        except Exception as e:
            logger.warning(
                "failed_to_sync_messages",
                conversation_id=conversation_chatwoot_id,
                error=str(e),
            )
