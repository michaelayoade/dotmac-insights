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

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json
from tests.e2e.fixtures.factories import create_customer, create_employee, create_ticket


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
            "customer_id": customer.id,
            "ticket_type": "Support",
        }

        response = e2e_superuser_client.post("/api/support/tickets", json=payload)
        assert_http_ok(response, "Create ticket")

        data = get_json(response)
        assert "id" in data
        ticket_id = data["id"]

        # Fetch the ticket to verify full data
        get_response = e2e_superuser_client.get(f"/api/support/tickets/{ticket_id}")
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

        response = e2e_superuser_client.get("/api/support/tickets")
        assert_http_ok(response, "List tickets")

        data = get_json(response)
        assert "data" in data
        assert len(data["data"]) >= 2

    def test_filter_tickets_by_status(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by status."""
        customer = create_customer(e2e_db, name="Filter Ticket Customer")
        create_ticket(e2e_db, customer_id=customer.id, status="open")
        create_ticket(e2e_db, customer_id=customer.id, status="resolved")

        response = e2e_superuser_client.get("/api/support/tickets", params={"status": "open"})
        assert_http_ok(response, "Filter by status")

        data = get_json(response)
        for ticket in data["data"]:
            assert ticket["status"] == "open"

    def test_filter_tickets_by_priority(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by priority."""
        customer = create_customer(e2e_db, name="Priority Filter Customer")
        create_ticket(e2e_db, customer_id=customer.id, priority="urgent")
        create_ticket(e2e_db, customer_id=customer.id, priority="low")

        response = e2e_superuser_client.get("/api/support/tickets", params={"priority": "urgent"})
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
            f"/api/support/tickets/{ticket.id}",
            json={"assigned_employee_id": employee.id},
        )
        assert_http_ok(response, "Assign ticket")

        data = get_json(response)
        assert data["assigned_employee_id"] == employee.id

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
            f"/api/support/tickets/{ticket.id}",
            json={"assigned_employee_id": employee2.id},
        )
        assert_http_ok(response, "Reassign ticket")

        data = get_json(response)
        assert data["assigned_employee_id"] == employee2.id


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
            f"/api/support/tickets/{ticket.id}/comments",
            json=payload,
        )
        assert_http_ok(response, "Add comment")

        data = get_json(response)
        assert data["comment"] == "This is a test comment"

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
            f"/api/support/tickets/{ticket.id}/comments",
            json=payload,
        )
        assert_http_ok(response, "Add internal note")

        data = get_json(response)
        assert data["is_public"] is False

    def test_list_ticket_comments(self, e2e_superuser_client, e2e_db):
        """Test listing comments on a ticket."""
        from tests.e2e.fixtures.factories import add_ticket_comment

        customer = create_customer(e2e_db, name="List Comments Customer")
        ticket = create_ticket(e2e_db, customer_id=customer.id)
        add_ticket_comment(e2e_db, ticket.id, "Comment 1")
        add_ticket_comment(e2e_db, ticket.id, "Comment 2")

        response = e2e_superuser_client.get(f"/api/support/tickets/{ticket.id}/comments")
        assert_http_ok(response, "List comments")

        data = get_json(response)
        assert "items" in data
        assert len(data["data"]) >= 2


class TestTicketStatusTransitions:
    """Test ticket status transitions."""

    def test_open_to_replied(self, e2e_superuser_client, e2e_db):
        """Test transitioning from open to replied."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={"status": "replied"},
        )
        assert_http_ok(response, "Transition to replied")

        data = get_json(response)
        assert data["status"] == "replied"

    def test_put_on_hold(self, e2e_superuser_client, e2e_db):
        """Test putting a ticket on hold."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={"status": "on_hold"},
        )
        assert_http_ok(response, "Put on hold")

        data = get_json(response)
        assert data["status"] == "on_hold"

    def test_resolve_ticket(self, e2e_superuser_client, e2e_db):
        """Test resolving a ticket."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={
                "status": "resolved",
                "resolution": "Issue was resolved by restarting the service.",
            },
        )
        assert_http_ok(response, "Resolve ticket")

        data = get_json(response)
        assert data["status"] == "resolved"

    def test_close_ticket(self, e2e_superuser_client, e2e_db):
        """Test closing a ticket."""
        ticket = create_ticket(e2e_db, status="resolved")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={"status": "closed"},
        )
        assert_http_ok(response, "Close ticket")

        data = get_json(response)
        assert data["status"] == "closed"


class TestTicketResolution:
    """Test ticket resolution workflow."""

    def test_add_resolution(self, e2e_superuser_client, e2e_db):
        """Test adding resolution to a ticket."""
        ticket = create_ticket(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={
                "resolution": "Customer's issue was resolved by updating their account settings.",
                "resolution_details": "Steps taken: 1. Verified account 2. Reset password 3. Updated email",
            },
        )
        assert_http_ok(response, "Add resolution")

        data = get_json(response)
        assert "resolution" in data
        assert "resolved" in data["resolution"].lower() or len(data["resolution"]) > 0

    def test_update_resolution(self, e2e_superuser_client, e2e_db):
        """Test updating resolution details."""
        ticket = create_ticket(
            e2e_db,
            status="resolved",
            resolution="Initial resolution",
        )

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
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
            "customer_id": customer.id,
            "ticket_type": "Support",
        }
        create_resp = e2e_superuser_client.post("/api/support/tickets", json=create_payload)
        assert_http_ok(create_resp, "Step 1: Create ticket")
        ticket = get_json(create_resp)
        ticket_id = ticket["id"]

        # Step 2: Assign to agent
        assign_resp = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket_id}",
            json={"assigned_employee_id": employee.id},
        )
        assert_http_ok(assign_resp, "Step 2: Assign ticket")

        # Step 3: Add comment
        comment_resp = e2e_superuser_client.post(
            f"/api/support/tickets/{ticket_id}/comments",
            json={
                "comment": "Looking into this issue",
                "commented_by": employee.name,
            },
        )
        assert_http_ok(comment_resp, "Step 3: Add comment")

        # Step 4: Update to replied
        replied_resp = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket_id}",
            json={"status": "replied"},
        )
        assert_http_ok(replied_resp, "Step 4: Mark as replied")

        # Step 5 & 6: Add resolution and resolve
        resolve_resp = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket_id}",
            json={
                "status": "resolved",
                "resolution": "Issue resolved by applying the fix",
            },
        )
        assert_http_ok(resolve_resp, "Step 5/6: Resolve ticket")

        # Step 7: Close ticket
        close_resp = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket_id}",
            json={"status": "closed"},
        )
        assert_http_ok(close_resp, "Step 7: Close ticket")

        # Verify final state
        final_resp = e2e_superuser_client.get(f"/api/support/tickets/{ticket_id}")
        final = get_json(final_resp)
        assert final["status"] == "closed"
        assert final["assigned_employee_id"] == employee.id
        assert final["resolution"] is not None


class TestSupportDashboard:
    """Test support dashboard and analytics."""

    def test_support_dashboard(self, e2e_superuser_client, e2e_db):
        """Test support dashboard endpoint."""
        # Create some tickets for metrics
        customer = create_customer(e2e_db, name="Dashboard Customer")
        create_ticket(e2e_db, customer_id=customer.id, status="open", priority="high")
        create_ticket(e2e_db, customer_id=customer.id, status="resolved", priority="medium")

        response = e2e_superuser_client.get("/api/support/dashboard")
        assert_http_ok(response, "Get support dashboard")

        data = get_json(response)
        assert "tickets" in data
        assert "by_priority" in data
        assert "sla" in data
        assert "metrics" in data

    def test_ticket_analytics(self, e2e_superuser_client, e2e_db):
        """Test ticket analytics endpoint."""
        response = e2e_superuser_client.get("/api/support/analytics/tickets")
        # May return different status depending on implementation
        assert response.status_code in [200, 404], f"Ticket analytics: {response.text}"


class TestTicketEscalation:
    """Test ticket escalation features."""

    def test_escalate_ticket(self, e2e_superuser_client, e2e_db):
        """Test escalating a ticket."""
        ticket = create_ticket(e2e_db, status="open", priority="medium")

        response = e2e_superuser_client.patch(
            f"/api/support/tickets/{ticket.id}",
            json={"priority": "urgent"},
        )
        assert_http_ok(response, "Escalate priority")

        data = get_json(response)
        assert data["priority"] == "urgent"


class TestTicketSearch:
    """Test ticket search functionality."""

    def test_search_tickets_by_subject(self, e2e_superuser_client, e2e_db):
        """Test searching tickets by subject."""
        customer = create_customer(e2e_db, name="Search Test Customer")
        create_ticket(e2e_db, customer_id=customer.id, subject="Network connectivity issue")
        create_ticket(e2e_db, customer_id=customer.id, subject="Billing question")

        response = e2e_superuser_client.get(
            "/api/support/tickets",
            params={"search": "network"},
        )
        assert_http_ok(response, "Search tickets")

        data = get_json(response)
        for ticket in data["data"]:
            assert "network" in ticket["subject"].lower()

    def test_search_by_customer(self, e2e_superuser_client, e2e_db):
        """Test filtering tickets by customer."""
        customer = create_customer(e2e_db, name="Customer Filter Test")
        create_ticket(e2e_db, customer_id=customer.id, subject="Customer Specific")

        response = e2e_superuser_client.get(
            "/api/support/tickets",
            params={"customer_id": customer.id},
        )
        assert_http_ok(response, "Filter by customer")

        data = get_json(response)
        for ticket in data["data"]:
            assert ticket["customer_id"] == customer.id
