"""
Inbox API Integration Tests

Tests conversation CRUD, assignments, messages, ticket/lead creation,
filtering, and RBAC for the Inbox Conversations API.
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.models.omni import (
    OmniChannel, OmniConversation, OmniMessage, OmniParticipant
)
from app.models.agent import Agent, Team
from app.models.ticket import Ticket


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_channel(integration_db):
    """Create a test channel."""
    channel = OmniChannel(
        name="test-email-channel",
        type="email",
        is_active=True,
        config={"host": "smtp.test.com"},
    )
    integration_db.add(channel)
    integration_db.commit()
    integration_db.refresh(channel)
    return channel


@pytest.fixture
def sample_agent(integration_db):
    """Create a test agent."""
    agent = Agent(
        email="agent@test.com",
        display_name="Test Agent",
        is_active=True,
        max_concurrent_chats=10,
        current_chat_count=0,
    )
    integration_db.add(agent)
    integration_db.commit()
    integration_db.refresh(agent)
    return agent


@pytest.fixture
def sample_team(integration_db):
    """Create a test team."""
    team = Team(
        name="Support Team",
        description="Customer support team",
        is_active=True,
    )
    integration_db.add(team)
    integration_db.commit()
    integration_db.refresh(team)
    return team


@pytest.fixture
def create_test_conversation(integration_db, sample_channel):
    """Factory fixture to create test conversations."""
    created = []

    def _create(
        subject: str = "Test Conversation",
        status: str = "open",
        priority: str = "medium",
        contact_name: str = "Test Contact",
        contact_email: str = "contact@test.com",
        assigned_agent_id: int = None,
        assigned_team_id: int = None,
        is_starred: bool = False,
        tags: list = None,
        message_count: int = 0,
        unread_count: int = 0,
    ) -> OmniConversation:
        conv = OmniConversation(
            channel_id=sample_channel.id,
            subject=subject,
            status=status,
            priority=priority,
            contact_name=contact_name,
            contact_email=contact_email,
            assigned_agent_id=assigned_agent_id,
            assigned_team_id=assigned_team_id,
            is_starred=is_starred,
            tags=tags,
            message_count=message_count,
            unread_count=unread_count,
            last_message_at=datetime.now(timezone.utc),
        )
        integration_db.add(conv)
        integration_db.commit()
        integration_db.refresh(conv)
        created.append(conv)
        return conv

    yield _create


@pytest.fixture
def create_test_message(integration_db, sample_channel):
    """Factory fixture to create test messages."""
    def _create(
        conversation_id: int,
        body: str = "Test message content",
        direction: str = "inbound",
        message_type: str = None,
    ) -> OmniMessage:
        msg = OmniMessage(
            conversation_id=conversation_id,
            channel_id=sample_channel.id,
            body=body,
            direction=direction,
            message_type=message_type,
            created_at=datetime.now(timezone.utc),
        )
        integration_db.add(msg)
        integration_db.commit()
        integration_db.refresh(msg)
        return msg

    return _create


# =============================================================================
# CONVERSATION LIST TESTS
# =============================================================================


class TestConversationList:
    """Tests for GET /api/inbox/conversations"""

    def test_list_conversations_basic(self, auth_client, create_test_conversation):
        """List conversations returns paginated results."""
        for i in range(5):
            create_test_conversation(subject=f"Conversation {i}")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert len(data["data"]) >= 5

    def test_list_conversations_with_pagination(self, auth_client, create_test_conversation):
        """List conversations with limit and offset."""
        for i in range(15):
            create_test_conversation(subject=f"Conv {i}")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?limit=5&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 5
        assert data["limit"] == 5
        assert data["offset"] == 0

    def test_list_conversations_filter_by_status(self, auth_client, create_test_conversation):
        """Filter conversations by status."""
        create_test_conversation(subject="Open 1", status="open")
        create_test_conversation(subject="Resolved 1", status="resolved")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?status=resolved")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["status"] == "resolved" for c in data["data"])

    def test_list_conversations_filter_by_priority(self, auth_client, create_test_conversation):
        """Filter conversations by priority."""
        create_test_conversation(subject="Urgent 1", priority="urgent")
        create_test_conversation(subject="Low 1", priority="low")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?priority=urgent")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["priority"] == "urgent" for c in data["data"])

    def test_list_conversations_filter_unassigned(self, auth_client, create_test_conversation, sample_agent):
        """Filter for unassigned conversations."""
        create_test_conversation(subject="Unassigned", assigned_agent_id=None)
        create_test_conversation(subject="Assigned", assigned_agent_id=sample_agent.id)

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?unassigned=true")

        assert resp.status_code == 200
        data = resp.json()
        assert all(
            c["assigned_agent_id"] is None and c["assigned_team_id"] is None
            for c in data["data"]
        )

    def test_list_conversations_filter_by_agent(self, auth_client, create_test_conversation, sample_agent):
        """Filter conversations by assigned agent."""
        create_test_conversation(subject="Agent Conv", assigned_agent_id=sample_agent.id)
        create_test_conversation(subject="Other Conv", assigned_agent_id=None)

        client = auth_client(["support:read"])
        resp = client.get(f"/api/inbox/conversations?agent_id={sample_agent.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["assigned_agent_id"] == sample_agent.id for c in data["data"])

    def test_list_conversations_filter_by_team(self, auth_client, create_test_conversation, sample_team):
        """Filter conversations by assigned team."""
        create_test_conversation(subject="Team Conv", assigned_team_id=sample_team.id)
        create_test_conversation(subject="Other Conv", assigned_team_id=None)

        client = auth_client(["support:read"])
        resp = client.get(f"/api/inbox/conversations?team_id={sample_team.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["assigned_team_id"] == sample_team.id for c in data["data"])

    def test_list_conversations_filter_starred(self, auth_client, create_test_conversation):
        """Filter for starred conversations."""
        create_test_conversation(subject="Starred", is_starred=True)
        create_test_conversation(subject="Not Starred", is_starred=False)

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?is_starred=true")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["is_starred"] is True for c in data["data"])

    def test_list_conversations_filter_by_tag(self, auth_client, create_test_conversation):
        """Filter conversations by tag."""
        create_test_conversation(subject="Tagged", tags=["billing", "urgent"])
        create_test_conversation(subject="Not Tagged", tags=[])

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?tag=billing")

        assert resp.status_code == 200
        data = resp.json()
        assert all("billing" in (c.get("tags") or []) for c in data["data"])

    def test_list_conversations_search(self, auth_client, create_test_conversation):
        """Search conversations by subject or contact."""
        create_test_conversation(subject="Billing inquiry", contact_name="John Doe")
        create_test_conversation(subject="Technical issue", contact_name="Jane Smith")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?search=Billing")

        assert resp.status_code == 200
        data = resp.json()
        assert any("Billing" in c["subject"] for c in data["data"])

    def test_list_conversations_sort_by_last_message(self, auth_client, create_test_conversation):
        """Sort conversations by last_message_at."""
        create_test_conversation(subject="Older")
        create_test_conversation(subject="Newer")

        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations?sort_by=last_message_at&sort_order=desc")

        assert resp.status_code == 200
        data = resp.json()
        # Most recent should come first
        if len(data["data"]) >= 2:
            times = [c["last_message_at"] for c in data["data"] if c["last_message_at"]]
            assert times == sorted(times, reverse=True)


# =============================================================================
# CONVERSATION CRUD TESTS
# =============================================================================


class TestConversationGet:
    """Tests for GET /api/inbox/conversations/{id}"""

    def test_get_conversation_by_id(self, auth_client, create_test_conversation, create_test_message):
        """Get a conversation with messages."""
        conv = create_test_conversation(subject="Detailed Conversation")
        create_test_message(conversation_id=conv.id, body="First message")
        create_test_message(conversation_id=conv.id, body="Second message")

        client = auth_client(["support:read"])
        resp = client.get(f"/api/inbox/conversations/{conv.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv.id
        assert data["subject"] == "Detailed Conversation"
        assert "messages" in data
        assert len(data["messages"]) == 2

    def test_get_nonexistent_conversation_returns_404(self, auth_client):
        """Get non-existent conversation returns 404."""
        client = auth_client(["support:read"])
        resp = client.get("/api/inbox/conversations/99999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_conversation_without_scope_fails(self, auth_client, create_test_conversation):
        """Cannot get conversation without support:read scope."""
        conv = create_test_conversation()

        client = auth_client(["contacts:read"])  # Wrong scope
        resp = client.get(f"/api/inbox/conversations/{conv.id}")

        assert resp.status_code == 403


class TestConversationUpdate:
    """Tests for PATCH /api/inbox/conversations/{id}"""

    def test_update_conversation_status(self, auth_client, create_test_conversation):
        """Update conversation status."""
        conv = create_test_conversation(status="open")

        client = auth_client(["support:write"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "status": "resolved"
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None

    def test_update_conversation_priority(self, auth_client, create_test_conversation):
        """Update conversation priority."""
        conv = create_test_conversation(priority="medium")

        client = auth_client(["support:write"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "priority": "urgent"
        })

        assert resp.status_code == 200
        assert resp.json()["priority"] == "urgent"

    def test_update_conversation_starred(self, auth_client, create_test_conversation):
        """Star/unstar a conversation."""
        conv = create_test_conversation(is_starred=False)

        client = auth_client(["support:write"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "is_starred": True
        })

        assert resp.status_code == 200
        assert resp.json()["is_starred"] is True

    def test_update_conversation_tags(self, auth_client, create_test_conversation):
        """Update conversation tags."""
        conv = create_test_conversation(tags=[])

        client = auth_client(["support:write"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "tags": ["vip", "escalated", "billing"]
        })

        assert resp.status_code == 200
        data = resp.json()
        assert "vip" in data["tags"]
        assert "escalated" in data["tags"]

    def test_update_conversation_snooze(self, auth_client, create_test_conversation):
        """Snooze a conversation."""
        conv = create_test_conversation(status="open")
        snooze_until = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        client = auth_client(["support:write"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "status": "snoozed",
            "snoozed_until": snooze_until,
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "snoozed"
        assert resp.json()["snoozed_until"] is not None

    def test_update_nonexistent_conversation_returns_404(self, auth_client):
        """Update non-existent conversation returns 404."""
        client = auth_client(["support:write"])
        resp = client.patch("/api/inbox/conversations/99999", json={"status": "resolved"})

        assert resp.status_code == 404

    def test_update_conversation_without_write_scope_fails(self, auth_client, create_test_conversation):
        """Cannot update conversation without support:write scope."""
        conv = create_test_conversation()

        client = auth_client(["support:read"])
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={"status": "resolved"})

        assert resp.status_code == 403


class TestConversationDelete:
    """Tests for DELETE /api/inbox/conversations/{id}"""

    def test_delete_conversation_sets_status_closed(self, auth_client, create_test_conversation, integration_db):
        """Delete conversation sets status to closed (soft delete)."""
        conv = create_test_conversation(status="open")

        client = auth_client(["support:write"])
        resp = client.delete(f"/api/inbox/conversations/{conv.id}")

        assert resp.status_code == 204

        integration_db.refresh(conv)
        assert conv.status == "closed"

    def test_delete_nonexistent_conversation_returns_404(self, auth_client):
        """Delete non-existent conversation returns 404."""
        client = auth_client(["support:write"])
        resp = client.delete("/api/inbox/conversations/99999")

        assert resp.status_code == 404


# =============================================================================
# ASSIGNMENT TESTS
# =============================================================================


class TestConversationAssignment:
    """Tests for POST /api/inbox/conversations/{id}/assign"""

    def test_assign_to_agent(self, auth_client, create_test_conversation, sample_agent):
        """Assign conversation to an agent."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={
            "agent_id": sample_agent.id
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_agent_id"] == sample_agent.id
        assert data["assigned_at"] is not None

    def test_assign_to_team(self, auth_client, create_test_conversation, sample_team):
        """Assign conversation to a team."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={
            "team_id": sample_team.id
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_team_id"] == sample_team.id

    def test_unassign_agent(self, auth_client, create_test_conversation, sample_agent):
        """Unassign conversation from agent."""
        conv = create_test_conversation(assigned_agent_id=sample_agent.id)

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={
            "agent_id": 0  # 0 means unassign
        })

        assert resp.status_code == 200
        assert resp.json()["assigned_agent_id"] is None

    def test_assign_to_nonexistent_agent_fails(self, auth_client, create_test_conversation):
        """Cannot assign to non-existent agent."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={
            "agent_id": 99999
        })

        assert resp.status_code == 400
        assert "agent not found" in resp.json()["detail"].lower()

    def test_assign_to_nonexistent_team_fails(self, auth_client, create_test_conversation):
        """Cannot assign to non-existent team."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={
            "team_id": 99999
        })

        assert resp.status_code == 400
        assert "team not found" in resp.json()["detail"].lower()


# =============================================================================
# MESSAGE TESTS
# =============================================================================


class TestConversationMessages:
    """Tests for POST /api/inbox/conversations/{id}/messages"""

    def test_send_reply_message(self, auth_client, create_test_conversation, integration_db):
        """Send a reply message to conversation."""
        conv = create_test_conversation(message_count=0)

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/messages", json={
            "body": "Thank you for contacting us. We will look into this.",
            "is_private": False
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["body"] == "Thank you for contacting us. We will look into this."
        assert data["direction"] == "outbound"

        # Verify conversation stats updated
        integration_db.refresh(conv)
        assert conv.message_count == 1
        assert conv.first_response_at is not None

    def test_send_private_note(self, auth_client, create_test_conversation):
        """Send a private note (internal message)."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/messages", json={
            "body": "Internal note: Customer seems frustrated.",
            "is_private": True
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["message_type"] == "private_note"

    def test_send_message_to_nonexistent_conversation_fails(self, auth_client):
        """Cannot send message to non-existent conversation."""
        client = auth_client(["support:write"])
        resp = client.post("/api/inbox/conversations/99999/messages", json={
            "body": "Hello"
        })

        assert resp.status_code == 404


class TestMarkRead:
    """Tests for POST /api/inbox/conversations/{id}/mark-read"""

    def test_mark_conversation_read(self, auth_client, create_test_conversation, create_test_message, integration_db):
        """Mark all messages in conversation as read."""
        conv = create_test_conversation(unread_count=3)
        create_test_message(conversation_id=conv.id, body="Unread 1", direction="inbound")
        create_test_message(conversation_id=conv.id, body="Unread 2", direction="inbound")

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/mark-read")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        integration_db.refresh(conv)
        assert conv.unread_count == 0


# =============================================================================
# INTEGRATION TESTS (TICKET/LEAD CREATION)
# =============================================================================


class TestCreateTicket:
    """Tests for POST /api/inbox/conversations/{id}/create-ticket"""

    def test_create_ticket_from_conversation(self, auth_client, create_test_conversation, integration_db):
        """Create a support ticket from conversation."""
        conv = create_test_conversation(
            subject="Network outage",
            contact_name="John Doe",
            contact_email="john@test.com",
        )

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/create-ticket", json={
            "subject": "Network outage investigation",
            "priority": "high",
            "category": "network",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["ticket_id"] is not None

        # Verify conversation is linked to ticket
        integration_db.refresh(conv)
        assert conv.ticket_id == data["ticket_id"]

    def test_create_ticket_conversation_already_has_ticket_fails(self, auth_client, create_test_conversation, integration_db):
        """Cannot create ticket if conversation already has one."""
        # Create a ticket first
        ticket = Ticket(
            subject="Existing ticket",
            status="open",
        )
        integration_db.add(ticket)
        integration_db.commit()

        conv = create_test_conversation()
        conv.ticket_id = ticket.id
        integration_db.commit()

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/create-ticket", json={
            "subject": "New ticket"
        })

        assert resp.status_code == 400
        assert "already has a ticket" in resp.json()["detail"].lower()


class TestCreateLead:
    """Tests for POST /api/inbox/conversations/{id}/create-lead"""

    def test_create_lead_from_conversation(self, auth_client, create_test_conversation, integration_db):
        """Create a sales lead from conversation."""
        conv = create_test_conversation(
            subject="Pricing inquiry",
            contact_name="Jane Doe",
            contact_email="jane@company.com",
            contact_company="Acme Corp",
        )

        client = auth_client(["sales:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/create-lead", json={
            "lead_name": "Jane Doe",
            "company_name": "Acme Corp",
            "source": "inbox",
            "notes": "Interested in enterprise plan",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["lead_id"] is not None

        # Verify conversation is linked to lead
        integration_db.refresh(conv)
        assert conv.lead_id == data["lead_id"]

    def test_create_lead_without_sales_scope_fails(self, auth_client, create_test_conversation):
        """Cannot create lead without sales:write scope."""
        conv = create_test_conversation()

        client = auth_client(["support:write"])  # Wrong scope
        resp = client.post(f"/api/inbox/conversations/{conv.id}/create-lead", json={
            "lead_name": "Test Lead"
        })

        assert resp.status_code == 403


# =============================================================================
# ARCHIVE TESTS
# =============================================================================


class TestArchiveConversation:
    """Tests for POST /api/inbox/conversations/{id}/archive"""

    def test_archive_conversation(self, auth_client, create_test_conversation, integration_db):
        """Archive a conversation sets status to closed."""
        conv = create_test_conversation(status="open")

        client = auth_client(["support:write"])
        resp = client.post(f"/api/inbox/conversations/{conv.id}/archive")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        integration_db.refresh(conv)
        assert conv.status == "closed"


# =============================================================================
# RBAC TESTS
# =============================================================================


class TestInboxRBAC:
    """Tests for role-based access control."""

    def test_superuser_has_full_access(self, superuser_client, create_test_conversation):
        """Superuser can perform all operations."""
        conv = create_test_conversation()

        # Read
        resp = superuser_client.get(f"/api/inbox/conversations/{conv.id}")
        assert resp.status_code == 200

        # Update
        resp = superuser_client.patch(f"/api/inbox/conversations/{conv.id}", json={
            "status": "pending"
        })
        assert resp.status_code == 200

        # List
        resp = superuser_client.get("/api/inbox/conversations")
        assert resp.status_code == 200

    def test_read_only_scope(self, auth_client, create_test_conversation):
        """User with only read scope can read but not write."""
        conv = create_test_conversation()
        client = auth_client(["support:read"])

        # Can read
        resp = client.get(f"/api/inbox/conversations/{conv.id}")
        assert resp.status_code == 200

        # Cannot update
        resp = client.patch(f"/api/inbox/conversations/{conv.id}", json={"status": "resolved"})
        assert resp.status_code == 403

        # Cannot assign
        resp = client.post(f"/api/inbox/conversations/{conv.id}/assign", json={"agent_id": 1})
        assert resp.status_code == 403

        # Cannot send message
        resp = client.post(f"/api/inbox/conversations/{conv.id}/messages", json={"body": "test"})
        assert resp.status_code == 403

    def test_unauthenticated_request_fails(self, unauthenticated_client, create_test_conversation):
        """Unauthenticated requests are rejected."""
        conv = create_test_conversation()
        resp = unauthenticated_client.get(f"/api/inbox/conversations/{conv.id}")
        assert resp.status_code == 401
