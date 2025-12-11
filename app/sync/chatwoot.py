from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient, CircuitBreakerOpenError
from app.models.sync_log import SyncSource
from app.models.customer import Customer
from app.models.conversation import Conversation, Message, ConversationStatus
from app.models.employee import Employee

logger = structlog.get_logger()


def utcnow() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


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
        """Make authenticated request to Chatwoot API with circuit breaker protection."""
        # Check circuit breaker before making request
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker for {self.source.value} is open"
            )

        try:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=self._get_headers(),
                params=params,
                json=json,
            )
            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure(e)
            raise

    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        data_key: str = "payload",
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all records with pagination.

        Chatwoot API returns:
        - Contacts: {"meta": {...}, "payload": [...]}
        - Conversations: {"data": {"meta": {...}, "payload": [...]}}
        """
        all_records = []
        page = 1

        while True:
            request_params = {"page": page, **(params or {})}
            response = await self._request(client, "GET", endpoint, params=request_params)

            # Handle nested data structure (conversations endpoint)
            if "data" in response and isinstance(response["data"], dict):
                container = response["data"]
            else:
                container = response

            data = container.get(data_key) if data_key else container
            if not data:
                break

            if isinstance(data, list):
                all_records.extend(data)
                self.increment_fetched(len(data))

                # Check pagination from meta
                meta = container.get("meta", {})
                total_count = meta.get("all_count") or meta.get("count", 0)

                # Stop if we've fetched all or reached max pages
                if len(all_records) >= total_count:
                    break
                if max_pages and page >= max_pages:
                    logger.info("pagination_limit_reached", page=page, max_pages=max_pages, fetched=len(all_records))
                    break
                if len(data) == 0:
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
            await self.sync_agents(client, full_sync)  # Sync agents first to link employees
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

    async def sync_agents_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Agents with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_agents(client, full_sync)

    async def sync_agents(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync agents from Chatwoot and link to employees by email."""
        self.start_sync("agents", "full" if full_sync else "incremental")

        try:
            response = await self._request(
                client,
                "GET",
                f"/accounts/{self.account_id}/agents",
            )

            agents = response if isinstance(response, list) else response.get("payload", [])
            self.increment_fetched(len(agents))

            for agent_data in agents:
                chatwoot_agent_id = agent_data.get("id")
                email = agent_data.get("email")
                name = agent_data.get("name")

                if not email:
                    continue

                # Find matching employee by email
                employee = self.db.query(Employee).filter(
                    Employee.email.ilike(email)
                ).first()

                if employee:
                    employee.chatwoot_agent_id = chatwoot_agent_id
                    employee.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                    logger.debug(
                        "chatwoot_agent_linked",
                        employee_id=employee.id,
                        employee_name=employee.name,
                        chatwoot_agent_id=chatwoot_agent_id,
                        email=email,
                    )
                else:
                    logger.debug(
                        "chatwoot_agent_no_employee_match",
                        chatwoot_agent_id=chatwoot_agent_id,
                        agent_name=name,
                        email=email,
                    )

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

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
        """Sync conversations/tickets from Chatwoot.

        Uses last_activity_at from conversations for cursor tracking (not utcnow())
        to ensure we don't miss updates if sync takes time.
        """
        self.start_sync("conversations", "full" if full_sync else "incremental")

        try:
            # Get cursor for incremental sync
            cursor = self.get_cursor("conversations")
            last_updated_after = None

            if not full_sync and cursor and cursor.last_sync_timestamp:
                # Chatwoot API supports updated_after for incremental fetches (Unix timestamp)
                last_updated_after = int(cursor.last_sync_timestamp.timestamp())
                logger.info("chatwoot_incremental_sync", entity="conversations", since=cursor.last_sync_timestamp)

            # Reset cursor if full sync requested
            if full_sync:
                self.reset_cursor("conversations")

            # Build params with updated_after filter for incremental
            params: Dict[str, Any] = {"status": "all"}
            if last_updated_after:
                params["updated_after"] = last_updated_after

            # Fetch conversations (limit pages appropriately)
            conversations = await self._fetch_paginated(
                client,
                f"/accounts/{self.account_id}/conversations",
                data_key="payload",
                params=params,
                max_pages=100 if full_sync else 20,  # More pages for incremental since filtered
            )

            # Track the latest activity timestamp from API responses for cursor
            latest_activity_ts: Optional[int] = None

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

                # Find employee by chatwoot_agent_id
                employee = None
                assignee_id = assignee.get("id")
                if assignee_id:
                    employee = self.db.query(Employee).filter(
                        Employee.chatwoot_agent_id == assignee_id
                    ).first()

                # Parse timestamps
                created_at = None
                if conv_data.get("created_at"):
                    try:
                        created_at = datetime.fromtimestamp(conv_data["created_at"])
                    except (ValueError, TypeError):
                        created_at = datetime.utcnow()

                # Track the latest activity timestamp for cursor (use last_activity_at from API)
                conv_last_activity = conv_data.get("last_activity_at")
                if conv_last_activity:
                    if latest_activity_ts is None or conv_last_activity > latest_activity_ts:
                        latest_activity_ts = conv_last_activity

                # Calculate response and resolution times
                first_response_time = None
                resolution_time = None

                # First try additional_attributes (some versions use this)
                additional_attrs = conv_data.get("additional_attributes", {})
                if additional_attrs:
                    first_response_time = additional_attrs.get("first_response_time")
                    resolution_time = additional_attrs.get("resolution_time")

                # Calculate from first_reply_created_at if available (preferred)
                first_reply_at = conv_data.get("first_reply_created_at")
                if first_reply_at and created_at:
                    try:
                        first_reply_dt = datetime.fromtimestamp(first_reply_at)
                        first_response_time = int((first_reply_dt - created_at).total_seconds())
                    except (ValueError, TypeError):
                        pass

                # Parse first_response_at for the model field
                first_response_at = None
                if first_reply_at:
                    try:
                        first_response_at = datetime.fromtimestamp(first_reply_at)
                    except (ValueError, TypeError):
                        pass

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
                    existing.employee_id = employee.id if employee else None
                    existing.message_count = conv_data.get("messages_count", 0)
                    existing.labels = labels_str
                    existing.last_activity_at = datetime.utcnow()
                    existing.last_synced_at = datetime.utcnow()

                    if first_response_time:
                        existing.first_response_time_seconds = int(first_response_time)

                    if first_response_at:
                        existing.first_response_at = first_response_at

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
                        employee_id=employee.id if employee else None,
                        message_count=conv_data.get("messages_count", 0),
                        labels=labels_str,
                        created_at=created_at or datetime.utcnow(),
                    )

                    if first_response_time:
                        conversation.first_response_time_seconds = int(first_response_time)

                    if first_response_at:
                        conversation.first_response_at = first_response_at

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

            # Update cursor with latest activity timestamp from API (not utcnow())
            # This ensures we don't miss updates if sync takes time
            if latest_activity_ts:
                cursor_timestamp = datetime.fromtimestamp(latest_activity_ts, tz=timezone.utc)
            else:
                # Fallback to utcnow() if no conversations were synced
                cursor_timestamp = utcnow()

            self.update_cursor(
                entity_type="conversations",
                timestamp=cursor_timestamp,
                records_count=len(conversations),
            )

            self.complete_sync()
            logger.info(
                "chatwoot_conversations_synced",
                total=len(conversations),
                created=self.current_sync_log.records_created if self.current_sync_log else 0,
                updated=self.current_sync_log.records_updated if self.current_sync_log else 0,
            )

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def _sync_conversation_messages(self, client: httpx.AsyncClient, conversation_chatwoot_id: int):
        """Sync messages for a specific conversation with delta tracking.

        Uses `after` parameter with last_message_id to only fetch new messages.

        Chatwoot's MessageFinder supports:
        - `after`: Returns up to 100 messages after the specified ID (ascending order)
        - `before`: Returns up to 20 messages before the specified ID
        - Both: Returns up to 1000 messages between two IDs

        We use `after` for efficient delta syncs, fetching only new messages since
        the last sync. Verified against Chatwoot source: app/finders/message_finder.rb
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.chatwoot_id == conversation_chatwoot_id
            ).first()

            if not conversation:
                return

            # Get last synced message ID for this conversation to enable delta sync
            last_synced_msg = self.db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.chatwoot_id.desc()).first()

            last_message_id = last_synced_msg.chatwoot_id if last_synced_msg else None

            # Chatwoot API supports before/after params for message pagination
            params = {}
            if last_message_id:
                params["after"] = last_message_id  # Only fetch messages after this ID

            response = await self._request(
                client,
                "GET",
                f"/accounts/{self.account_id}/conversations/{conversation_chatwoot_id}/messages",
                params=params if params else None,
            )

            messages = response if isinstance(response, list) else response.get("payload", [])

            if not messages:
                return

            new_messages_count = 0
            for msg_data in messages:
                chatwoot_id = msg_data.get("id")

                # Skip if already exists (double-check for safety)
                existing = self.db.query(Message).filter(Message.chatwoot_id == chatwoot_id).first()
                if existing:
                    continue

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
                new_messages_count += 1

            if new_messages_count > 0:
                logger.debug(
                    "chatwoot_messages_synced",
                    conversation_id=conversation_chatwoot_id,
                    new_messages=new_messages_count,
                    delta_from=last_message_id,
                )

        except Exception as e:
            logger.warning(
                "failed_to_sync_messages",
                conversation_id=conversation_chatwoot_id,
                error=str(e),
            )
