"""
Inbox Conversation E2E Flow Tests

Tests the complete conversation lifecycle from arrival through resolution,
including agent assignment, messaging, and ticket/lead creation.
"""
import pytest
from datetime import datetime, timezone, timedelta

from tests.e2e.conftest import (
    assert_http_ok, assert_http_error, get_json,
    assert_response_schema
)
from tests.e2e.fixtures.factories import create_customer


pytestmark = pytest.mark.inbox


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def test_channel(e2e_db):
    """Create a test omni channel."""
    from app.models.omni import OmniChannel

    channel = OmniChannel(
        name="test-email-channel",
        type="email",
        is_active=True,
        config={"host": "smtp.test.com"},
    )
    e2e_db.add(channel)
    e2e_db.commit()
    e2e_db.refresh(channel)
    return channel


@pytest.fixture
def test_agent(e2e_db):
    """Create a test support agent."""
    from app.models.agent import Agent

    agent = Agent(
        email="agent@test.com",
        display_name="Support Agent",
        is_active=True,
        max_concurrent_chats=10,
        current_chat_count=0,
    )
    e2e_db.add(agent)
    e2e_db.commit()
    e2e_db.refresh(agent)
    return agent


@pytest.fixture
def test_team(e2e_db):
    """Create a test support team."""
    from app.models.agent import Team

    team = Team(
        name="Customer Support",
        description="Frontline customer support team",
        is_active=True,
    )
    e2e_db.add(team)
    e2e_db.commit()
    e2e_db.refresh(team)
    return team


@pytest.fixture
def create_test_conversation(e2e_db, test_channel):
    """Factory to create test conversations."""
    from app.models.omni import OmniConversation, OmniMessage

    def _create(
        subject: str = "Test Inquiry",
        contact_name: str = "Test Contact",
        contact_email: str = "contact@test.com",
        status: str = "open",
        initial_message: str = "Hello, I need help with my account.",
    ):
        conv = OmniConversation(
            channel_id=test_channel.id,
            subject=subject,
            status=status,
            priority="medium",
            contact_name=contact_name,
            contact_email=contact_email,
            message_count=1 if initial_message else 0,
            unread_count=1 if initial_message else 0,
            last_message_at=datetime.now(timezone.utc),
        )
        e2e_db.add(conv)
        e2e_db.flush()

        if initial_message:
            msg = OmniMessage(
                conversation_id=conv.id,
                channel_id=test_channel.id,
                direction="inbound",
                body=initial_message,
                created_at=datetime.now(timezone.utc),
            )
            e2e_db.add(msg)

        e2e_db.commit()
        e2e_db.refresh(conv)
        return conv

    return _create


# =============================================================================
# COMPLETE CONVERSATION FLOW
# =============================================================================


class TestConversationResolutionFlow:
    """
    Test the complete conversation lifecycle:
    New → Assigned → Responded → Resolved
    """

    def test_support_inquiry_complete_flow(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_agent,
    ):
        """
        E2E: Complete support conversation flow from inquiry to resolution.

        Flow:
        1. New conversation arrives
        2. Assign to agent
        3. Agent marks as read
        4. Agent sends reply
        5. Customer responds
        6. Agent sends final response
        7. Resolve conversation
        """
        client = e2e_superuser_client

        # 1. New conversation arrives (created via fixture simulating inbound)
        conv = create_test_conversation(
            subject="Billing Question",
            contact_name="Jane Customer",
            contact_email="jane@customer.com",
            initial_message="Hi, I have a question about my recent invoice #1234.",
        )
        conv_id = conv.id

        # Verify initial state
        resp = client.get(f"/api/v1/inbox/conversations/{conv_id}")
        assert_http_ok(resp, "Get conversation")
        conversation = get_json(resp)
        assert conversation["status"] == "open"
        assert conversation["unread_count"] >= 1
        assert conversation["assigned_agent_id"] is None

        # 2. Assign to agent
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/assign", json={
            "agent_id": test_agent.id,
        })
        assert_http_ok(resp, "Assign to agent")
        conversation = get_json(resp)
        assert conversation["assigned_agent_id"] == test_agent.id
        assert conversation["assigned_at"] is not None

        # 3. Agent marks conversation as read
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/mark-read")
        assert_http_ok(resp, "Mark as read")
        result = get_json(resp)
        assert result["success"] is True

        # 4. Agent sends reply
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/messages", json={
            "body": "Hello Jane! Thank you for reaching out. I'd be happy to help with your billing question. Could you please provide more details about invoice #1234?",
            "is_private": False,
        })
        assert_http_ok(resp, "Send reply")
        message = get_json(resp)
        assert message["direction"] == "outbound"

        # Verify first response time was tracked
        resp = client.get(f"/api/v1/inbox/conversations/{conv_id}")
        conversation = get_json(resp)
        assert conversation["first_response_at"] is not None

        # 5. Simulate customer response (add internal note about it)
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/messages", json={
            "body": "Customer replied: The invoice shows a charge I don't recognize.",
            "is_private": True,  # Private note
        })
        assert_http_ok(resp, "Add private note")
        note = get_json(resp)
        assert note["message_type"] == "private_note"

        # 6. Agent sends final response
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/messages", json={
            "body": "I've reviewed your account and found that charge was for the premium upgrade you requested on the 15th. I've attached the order confirmation for your records. Is there anything else I can help with?",
            "is_private": False,
        })
        assert_http_ok(resp, "Send final response")

        # 7. Resolve conversation
        resp = client.patch(f"/api/v1/inbox/conversations/{conv_id}", json={
            "status": "resolved",
        })
        assert_http_ok(resp, "Resolve conversation")
        conversation = get_json(resp)
        assert conversation["status"] == "resolved"
        assert conversation["resolved_at"] is not None


class TestConversationToTicketFlow:
    """Test creating support tickets from conversations."""

    def test_escalate_conversation_to_ticket(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_agent,
    ):
        """
        E2E: Escalate a conversation to a support ticket.

        Flow:
        1. Receive technical support inquiry
        2. Assign to agent
        3. Agent determines ticket needed
        4. Create ticket from conversation
        5. Continue conversation with ticket linked
        """
        client = e2e_superuser_client

        # 1. Technical support inquiry
        conv = create_test_conversation(
            subject="Network Connectivity Issues",
            contact_name="Tech Customer",
            contact_email="tech@company.com",
            initial_message="Our office network has been down for 2 hours. Multiple users affected. Need urgent help!",
        )
        conv_id = conv.id

        # 2. Assign to agent
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/assign", json={
            "agent_id": test_agent.id,
        })
        assert_http_ok(resp)

        # 3. Agent acknowledges and prepares to escalate
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/messages", json={
            "body": "I understand you're experiencing network issues affecting your office. Let me create a support ticket for this so our technical team can investigate.",
            "is_private": False,
        })
        assert_http_ok(resp)

        # 4. Create ticket from conversation
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/create-ticket", json={
            "subject": "Network Outage - Office Connectivity Down",
            "priority": "high",
            "category": "network",
            "description": "Customer reports complete network outage affecting multiple users for 2+ hours. Urgent resolution required.",
        })
        assert_http_ok(resp, "Create ticket")
        result = get_json(resp)

        assert result["success"] is True
        assert result["ticket_id"] is not None

        # 5. Verify conversation is linked to ticket
        resp = client.get(f"/api/v1/inbox/conversations/{conv_id}")
        conversation = get_json(resp)
        assert conversation["ticket_id"] == result["ticket_id"]


class TestConversationToLeadFlow:
    """Test creating sales leads from conversations."""

    def test_convert_inquiry_to_sales_lead(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
    ):
        """
        E2E: Convert a pricing inquiry into a sales lead.

        Flow:
        1. Receive pricing inquiry
        2. Identify sales opportunity
        3. Create lead from conversation
        4. Verify lead is linked
        """
        client = e2e_superuser_client

        # 1. Pricing inquiry
        conv = create_test_conversation(
            subject="Enterprise Pricing Inquiry",
            contact_name="Corporate Buyer",
            contact_email="buyer@enterprise.com",
            initial_message="We're evaluating providers for our company of 500+ employees. What enterprise packages do you offer?",
        )
        conv_id = conv.id

        # 2. Update conversation with sales context
        resp = client.patch(f"/api/v1/inbox/conversations/{conv_id}", json={
            "tags": ["sales", "enterprise", "pricing"],
            "priority": "high",
        })
        assert_http_ok(resp)

        # 3. Create lead from conversation
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/create-lead", json={
            "lead_name": "Corporate Buyer",
            "company_name": "Enterprise Corp",
            "source": "inbox",
            "notes": "Evaluating for 500+ employee deployment. High potential enterprise deal.",
        })
        assert_http_ok(resp, "Create lead")
        result = get_json(resp)

        assert result["success"] is True
        assert result["lead_id"] is not None

        # 4. Verify conversation is linked to lead
        resp = client.get(f"/api/v1/inbox/conversations/{conv_id}")
        conversation = get_json(resp)
        assert conversation["lead_id"] == result["lead_id"]


class TestConversationSnoozeFlow:
    """Test snoozing and unsnoozing conversations."""

    def test_snooze_awaiting_customer_response(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_agent,
    ):
        """
        E2E: Snooze conversation while awaiting customer response.

        Flow:
        1. Agent responds to inquiry
        2. Snooze for 24 hours
        3. Verify snoozed state
        """
        client = e2e_superuser_client

        conv = create_test_conversation(
            subject="Account Question",
            initial_message="Can you help with my account?",
        )
        conv_id = conv.id

        # Assign and respond
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/assign", json={
            "agent_id": test_agent.id,
        })
        assert_http_ok(resp)

        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/messages", json={
            "body": "I'd be happy to help. Could you please verify your account email?",
            "is_private": False,
        })
        assert_http_ok(resp)

        # Snooze for 24 hours
        snooze_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        resp = client.patch(f"/api/v1/inbox/conversations/{conv_id}", json={
            "status": "snoozed",
            "snoozed_until": snooze_until,
        })
        assert_http_ok(resp, "Snooze conversation")
        conversation = get_json(resp)

        assert conversation["status"] == "snoozed"
        assert conversation["snoozed_until"] is not None


class TestTeamAssignmentFlow:
    """Test team-based assignment workflows."""

    def test_assign_to_team_then_agent(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_team,
        test_agent,
    ):
        """
        E2E: Assign conversation to team, then specific agent picks it up.

        Flow:
        1. New conversation arrives
        2. Assign to team
        3. Agent from team picks up
        4. Process to resolution
        """
        client = e2e_superuser_client

        conv = create_test_conversation(
            subject="General Inquiry",
            initial_message="I have some questions about your services.",
        )
        conv_id = conv.id

        # 1. Assign to team
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/assign", json={
            "team_id": test_team.id,
        })
        assert_http_ok(resp, "Assign to team")
        conversation = get_json(resp)
        assert conversation["assigned_team_id"] == test_team.id
        assert conversation["assigned_agent_id"] is None

        # 2. Agent picks up from team queue
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/assign", json={
            "agent_id": test_agent.id,
        })
        assert_http_ok(resp, "Agent picks up")
        conversation = get_json(resp)
        assert conversation["assigned_agent_id"] == test_agent.id
        # Team assignment may remain or be cleared depending on business logic


class TestConversationFilteringFlow:
    """Test conversation list filtering in workflows."""

    def test_filter_unassigned_conversations(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_agent,
    ):
        """
        E2E: Filter to find unassigned conversations for pickup.
        """
        client = e2e_superuser_client

        # Create unassigned conversations
        for i in range(3):
            create_test_conversation(
                subject=f"Unassigned Inquiry {i}",
                initial_message=f"Need help with issue {i}",
            )

        # Create assigned conversation
        assigned_conv = create_test_conversation(
            subject="Already Assigned",
            initial_message="This one is taken",
        )
        resp = client.post(f"/api/v1/inbox/conversations/{assigned_conv.id}/assign", json={
            "agent_id": test_agent.id,
        })
        assert_http_ok(resp)

        # Filter for unassigned
        resp = client.get("/api/v1/inbox/conversations?unassigned=true")
        assert_http_ok(resp)
        data = get_json(resp)

        # All returned should be unassigned
        for conv in data["data"]:
            assert conv["assigned_agent_id"] is None
            assert conv["assigned_team_id"] is None

    def test_filter_starred_conversations(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
    ):
        """
        E2E: Star important conversations and filter to view them.
        """
        client = e2e_superuser_client

        # Create and star important conversations
        important_convs = []
        for i in range(2):
            conv = create_test_conversation(
                subject=f"VIP Customer {i}",
                initial_message=f"Important inquiry {i}",
            )
            resp = client.patch(f"/api/v1/inbox/conversations/{conv.id}", json={
                "is_starred": True,
            })
            assert_http_ok(resp)
            important_convs.append(conv.id)

        # Create regular conversation
        create_test_conversation(
            subject="Regular Inquiry",
            initial_message="Normal question",
        )

        # Filter for starred
        resp = client.get("/api/v1/inbox/conversations?is_starred=true")
        assert_http_ok(resp)
        data = get_json(resp)

        # All returned should be starred
        assert all(c["is_starred"] is True for c in data["data"])


class TestConversationArchiveFlow:
    """Test archiving conversations."""

    def test_archive_resolved_conversation(
        self,
        e2e_superuser_client,
        e2e_db,
        create_test_conversation,
        test_agent,
    ):
        """
        E2E: Archive a resolved conversation.
        """
        client = e2e_superuser_client

        conv = create_test_conversation(
            subject="Completed Inquiry",
            initial_message="Simple question",
        )
        conv_id = conv.id

        # Resolve the conversation
        resp = client.patch(f"/api/v1/inbox/conversations/{conv_id}", json={
            "status": "resolved",
        })
        assert_http_ok(resp)

        # Archive the conversation
        resp = client.post(f"/api/v1/inbox/conversations/{conv_id}/archive")
        assert_http_ok(resp, "Archive conversation")
        result = get_json(resp)
        assert result["success"] is True

        # Verify archived (closed) status
        resp = client.get(f"/api/v1/inbox/conversations/{conv_id}")
        conversation = get_json(resp)
        assert conversation["status"] == "closed"
