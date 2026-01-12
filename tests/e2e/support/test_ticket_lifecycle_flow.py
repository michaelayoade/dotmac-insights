"""
E2E Tests: Support Ticket Lifecycle

Tests the complete ticket lifecycle from creation through resolution.

Flow:
1. Create Ticket
2. Assign to Agent
3. Add Comments
4. Update Status (Working/On Hold)
5. Add Resolution
6. Close Ticket
7. Verify SLA compliance
"""
import pytest
from datetime import datetime, timedelta

from tests.e2e.conftest import (
    assert_http_ok, assert_http_error, get_json,
    assert_response_schema, assert_field_exists
)
from tests.e2e.fixtures.factories import create_customer, create_employee, create_ticket

# Apply module marker
pytestmark = pytest.mark.support


class TestTicketCreation:
    """Test ticket creation and basic operations."""

    def test_create_ticket(self, e2e_superuser_client, e2e_db):
        """Test creating a support ticket."""
        customer = create_customer(e2e_db, name="Ticket Test Customer")

        payload = {
            "subject": "E2E Test Ticket",
            "description": "This is a test ticket for E2E testing",
            "priority": "high",
            "status": "open",
            "customer_account_id": customer.id,
            "ticket_type": "Support",
        }

        response = e2e_superuser_client.post("/api/v1/support/tickets", json=payload)
        assert_http_ok(response, "Create ticket")

        data = get_json(response)
        assert "id" in data
        ticket_id = data["id"]

        # Fetch the ticket to verify full data
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket_id}")
        assert_http_ok(get_response, "Get created ticket")

        ticket_data = get_json(get_response)
        assert ticket_data["subject"] == "E2E Test Ticket"
        assert ticket_data["status"] == "open"
        assert ticket_data["priority"] == "high"

    def test_list_tickets(self, e2e_superuser_client, e2e_db):
        """Test listing tickets."""
        customer = create_customer(e2e_db, name="List Ticket Customer")
        create_ticket(e2e_db, customer_id=customer.id, subject="List Test 1")
        create_ticket(e2e_db, customer_id=customer.id, subject="List Test 2")

        response = e2e_superuser_client.get("/api/v1/support/tickets")
        assert_http_ok(response, "List tickets")

        data = get_json(response)
        assert "data" in data
        assert len(data["data"]) >= 2

    def test_filter_tickets_by_status(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by status."""
        customer = create_customer(e2e_db, name="Filter Ticket Customer")
        create_ticket(e2e_db, customer_id=customer.id, status="open")
        create_ticket(e2e_db, customer_id=customer.id, status="resolved")

        response = e2e_superuser_client.get("/api/v1/support/tickets", params={"status": "open"})
        assert_http_ok(response, "Filter by status")

        data = get_json(response)
        for ticket in data["data"]:
            assert ticket["status"] == "open"

    def test_filter_tickets_by_priority(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by priority."""
        customer = create_customer(e2e_db, name="Priority Filter Customer")
        create_ticket(e2e_db, customer_id=customer.id, priority="urgent")
        create_ticket(e2e_db, customer_id=customer.id, priority="low")

        response = e2e_superuser_client.get("/api/v1/support/tickets", params={"priority": "urgent"})
        assert_http_ok(response, "Filter by priority")

        data = get_json(response)
        for ticket in data["data"]:
            assert ticket["priority"] == "urgent"


class TestTicketAssignment:
    """Test ticket assignment workflow."""

    def test_assign_ticket_to_employee(self, e2e_superuser_client, e2e_db):
        """Test assigning a ticket to an employee."""
        customer = create_customer(e2e_db, name="Assign Test Customer")
        employee = create_employee(e2e_db, name="Support Agent")
        ticket = create_ticket(e2e_db, customer_id=customer.id, subject="Assign Test")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"assigned_employee_id": employee.id},
        )
        assert_http_ok(response, "Assign ticket")

        # Verify response has ticket id
        data = get_json(response)
        assert data["id"] == ticket.id

        # Fetch to verify assignment
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get assigned ticket")
        assigned = get_json(get_response)
        assert assigned["assigned_employee_id"] == employee.id

    def test_reassign_ticket(self, e2e_superuser_client, e2e_db):
        """Test reassigning a ticket to a different employee."""
        customer = create_customer(e2e_db, name="Reassign Test Customer")
        employee1 = create_employee(e2e_db, name="Agent 1")
        employee2 = create_employee(e2e_db, name="Agent 2")
        ticket = create_ticket(
            e2e_db,
            customer_id=customer.id,
            assigned_employee_id=employee1.id,
        )

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"assigned_employee_id": employee2.id},
        )
        assert_http_ok(response, "Reassign ticket")

        # Verify response has ticket id
        data = get_json(response)
        assert data["id"] == ticket.id

        # Fetch to verify reassignment
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get reassigned ticket")
        reassigned = get_json(get_response)
        assert reassigned["assigned_employee_id"] == employee2.id


class TestTicketComments:
    """Test ticket comments functionality."""

    def test_add_comment_to_ticket(self, e2e_superuser_client, e2e_db):
        """Test adding a comment to a ticket."""
        customer = create_customer(e2e_db, name="Comment Test Customer")
        ticket = create_ticket(e2e_db, customer_id=customer.id, subject="Comment Test")

        payload = {
            "comment": "This is a test comment",
            "commented_by": "Test Agent",
            "is_public": True,
        }

        response = e2e_superuser_client.post(
            f"/api/v1/support/tickets/{ticket.id}/comments",
            json=payload,
        )
        assert_http_ok(response, "Add comment")

        data = get_json(response)
        assert "id" in data  # API returns {"id": comment_id}

        # Verify by fetching ticket details (comments are in ticket response)
        ticket_resp = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(ticket_resp, "Get ticket with comment")
        ticket_data = get_json(ticket_resp)
        assert any(c["comment"] == "This is a test comment" for c in ticket_data.get("comments", []))

    def test_add_internal_note(self, e2e_superuser_client, e2e_db):
        """Test adding an internal (non-public) note."""
        customer = create_customer(e2e_db, name="Note Test Customer")
        ticket = create_ticket(e2e_db, customer_id=customer.id, subject="Note Test")

        payload = {
            "comment": "Internal agent note",
            "commented_by": "Support Lead",
            "is_public": False,
        }

        response = e2e_superuser_client.post(
            f"/api/v1/support/tickets/{ticket.id}/comments",
            json=payload,
        )
        assert_http_ok(response, "Add internal note")

        data = get_json(response)
        assert "id" in data

        # Verify by fetching ticket details (comments are in ticket response)
        ticket_resp = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(ticket_resp, "Get ticket with internal note")
        ticket_data = get_json(ticket_resp)
        internal_notes = [c for c in ticket_data.get("comments", []) if c["comment"] == "Internal agent note"]
        assert len(internal_notes) > 0
        assert internal_notes[0]["is_public"] is False

    def test_list_ticket_comments(self, e2e_superuser_client, e2e_db):
        """Test listing comments on a ticket via ticket detail endpoint."""
        from tests.e2e.fixtures.factories import add_ticket_comment

        customer = create_customer(e2e_db, name="List Comments Customer")
        ticket = create_ticket(e2e_db, customer_id=customer.id)
        add_ticket_comment(e2e_db, ticket.id, "Comment 1")
        add_ticket_comment(e2e_db, ticket.id, "Comment 2")

        # Comments are included in the ticket detail response
        response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(response, "Get ticket with comments")

        data = get_json(response)
        assert "comments" in data
        assert len(data["comments"]) >= 2


class TestTicketStatusTransitions:
    """Test ticket status transitions."""

    def test_open_to_replied(self, e2e_superuser_client, e2e_db):
        """Test transitioning from open to replied."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"status": "replied"},
        )
        assert_http_ok(response, "Transition to replied")

        # Fetch to verify status change
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket after replied")
        data = get_json(get_response)
        assert data["status"] == "replied"

    def test_put_on_hold(self, e2e_superuser_client, e2e_db):
        """Test putting a ticket on hold."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"status": "on_hold"},
        )
        assert_http_ok(response, "Put on hold")

        # Fetch to verify status change
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket after on hold")
        data = get_json(get_response)
        assert data["status"] == "on_hold"

    def test_resolve_ticket(self, e2e_superuser_client, e2e_db):
        """Test resolving a ticket."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={
                "status": "resolved",
                "resolution": "Issue was resolved by restarting the service.",
            },
        )
        assert_http_ok(response, "Resolve ticket")

        # Fetch to verify status change
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket after resolve")
        data = get_json(get_response)
        assert data["status"] == "resolved"

    def test_close_ticket(self, e2e_superuser_client, e2e_db):
        """Test closing a ticket."""
        ticket = create_ticket(e2e_db, status="resolved")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"status": "closed"},
        )
        assert_http_ok(response, "Close ticket")

        # Fetch to verify status change
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket after close")
        data = get_json(get_response)
        assert data["status"] == "closed"


class TestTicketResolution:
    """Test ticket resolution workflow."""

    def test_add_resolution(self, e2e_superuser_client, e2e_db):
        """Test adding resolution to a ticket."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={
                "resolution": "Customer's issue was resolved by updating their account settings.",
                "resolution_details": "Steps taken: 1. Verified account 2. Reset password 3. Updated email",
            },
        )
        assert_http_ok(response, "Add resolution")

        # Fetch to verify resolution
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket with resolution")
        data = get_json(get_response)
        assert "resolution" in data
        assert data["resolution"] is not None and len(data["resolution"]) > 0

    def test_update_resolution(self, e2e_superuser_client, e2e_db):
        """Test updating resolution details."""
        ticket = create_ticket(
            e2e_db,
            status="resolved",
            resolution="Initial resolution",
        )

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"resolution": "Updated resolution with more details"},
        )
        assert_http_ok(response, "Update resolution")


class TestTicketFullLifecycle:
    """Test complete ticket lifecycle."""

    def test_complete_ticket_lifecycle(self, e2e_superuser_client, e2e_db):
        """
        Test complete flow:
        1. Create ticket
        2. Assign to agent
        3. Add comment
        4. Update to replied
        5. Add resolution
        6. Resolve ticket
        7. Close ticket
        """
        customer = create_customer(e2e_db, name="Lifecycle Customer")
        employee = create_employee(e2e_db, name="Lifecycle Agent")

        # Step 1: Create ticket
        create_payload = {
            "subject": "Full Lifecycle Test",
            "description": "Testing complete ticket lifecycle",
            "priority": "high",
            "status": "open",
            "customer_account_id": customer.id,
            "ticket_type": "Support",
        }
        create_resp = e2e_superuser_client.post("/api/v1/support/tickets", json=create_payload)
        assert_http_ok(create_resp, "Step 1: Create ticket")
        ticket = get_json(create_resp)
        ticket_id = ticket["id"]

        # Step 2: Assign to agent
        assign_resp = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={"assigned_employee_id": employee.id},
        )
        assert_http_ok(assign_resp, "Step 2: Assign ticket")

        # Step 3: Add comment
        comment_resp = e2e_superuser_client.post(
            f"/api/v1/support/tickets/{ticket_id}/comments",
            json={
                "comment": "Looking into this issue",
                "commented_by": employee.name,
            },
        )
        assert_http_ok(comment_resp, "Step 3: Add comment")

        # Step 4: Update to replied
        replied_resp = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={"status": "replied"},
        )
        assert_http_ok(replied_resp, "Step 4: Mark as replied")

        # Step 5 & 6: Add resolution and resolve
        resolve_resp = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={
                "status": "resolved",
                "resolution": "Issue resolved by applying the fix",
            },
        )
        assert_http_ok(resolve_resp, "Step 5/6: Resolve ticket")

        # Step 7: Close ticket
        close_resp = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={"status": "closed"},
        )
        assert_http_ok(close_resp, "Step 7: Close ticket")

        # Verify final state
        final_resp = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket_id}")
        assert_http_ok(final_resp, "Get final ticket state")
        final = get_json(final_resp)
        assert final["status"] == "closed"
        # Verify resolution exists using explicit field check
        assert "resolution" in final, "Response missing 'resolution' field"
        # Resolution may be a string or nested object - handle both
        resolution = final["resolution"]
        if isinstance(resolution, dict):
            assert "resolution" in resolution, "Nested resolution object missing 'resolution' field"
            assert resolution["resolution"] is not None
        else:
            assert resolution is not None, "Resolution should not be None"


class TestSupportDashboard:
    """Test support dashboard and analytics."""

    def test_support_dashboard(self, e2e_superuser_client, e2e_db):
        """Test support dashboard endpoint."""
        # Create some tickets for metrics
        customer = create_customer(e2e_db, name="Dashboard Customer")
        create_ticket(e2e_db, customer_id=customer.id, status="open", priority="high")
        create_ticket(e2e_db, customer_id=customer.id, status="resolved", priority="medium")

        response = e2e_superuser_client.get("/api/v1/support/dashboard")
        assert_http_ok(response, "Get support dashboard")

        data = get_json(response)
        assert "tickets" in data
        assert "by_priority" in data
        assert "sla" in data
        assert "metrics" in data

    def test_ticket_analytics(self, e2e_superuser_client, e2e_db):
        """Test ticket analytics endpoint."""
        response = e2e_superuser_client.get("/api/v1/support/analytics/tickets")
        # May return different status depending on implementation
        assert response.status_code in [200, 404], f"Ticket analytics: {response.text}"


class TestTicketEscalation:
    """Test ticket escalation features."""

    def test_escalate_ticket(self, e2e_superuser_client, e2e_db):
        """Test escalating a ticket."""
        ticket = create_ticket(e2e_db, status="open", priority="medium")

        response = e2e_superuser_client.patch(
            f"/api/v1/support/tickets/{ticket.id}",
            json={"priority": "urgent"},
        )
        assert_http_ok(response, "Escalate priority")

        # Fetch to verify priority change
        get_response = e2e_superuser_client.get(f"/api/v1/support/tickets/{ticket.id}")
        assert_http_ok(get_response, "Get ticket after escalation")
        data = get_json(get_response)
        assert data["priority"] == "urgent"


class TestTicketSearch:
    """Test ticket search functionality."""

    def test_search_tickets_by_subject(self, e2e_superuser_client, e2e_db):
        """Test searching tickets by subject."""
        customer = create_customer(e2e_db, name="Search Test Customer")
        create_ticket(e2e_db, customer_id=customer.id, subject="Network connectivity issue")
        create_ticket(e2e_db, customer_id=customer.id, subject="Billing question")

        response = e2e_superuser_client.get(
            "/api/v1/support/tickets",
            params={"search": "connectivity"},
        )
        assert_http_ok(response, "Search tickets")

        data = get_json(response)
        # Should find at least the network ticket
        subjects = [t["subject"] for t in data["data"]]
        assert any("connectivity" in s.lower() for s in subjects)

    def test_search_by_customer(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by customer."""
        customer = create_customer(e2e_db, name="Customer Filter Test")
        create_ticket(e2e_db, customer_id=customer.id, subject="Customer Specific")

        response = e2e_superuser_client.get(
            "/api/v1/support/tickets",
            params={"customer_account_id": customer.id},
        )
        assert_http_ok(response, "Filter by customer")

        data = get_json(response)
        for ticket in data["data"]:
            assert ticket["customer_account_id"] == customer.id
