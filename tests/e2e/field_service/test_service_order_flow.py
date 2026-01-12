"""
Field Service Order E2E Flow Tests

Tests the complete service order lifecycle from creation through completion,
including dispatch, field operations, and customer sign-off.
"""
import pytest
from datetime import date, time, datetime, timezone, timedelta
from decimal import Decimal

from tests.e2e.conftest import (
    assert_http_ok, assert_http_error, get_json,
    assert_response_schema
)
from tests.e2e.fixtures.factories import create_customer, create_employee


pytestmark = pytest.mark.field_service


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def test_customer(e2e_db):
    """Create a test customer for field service."""
    return create_customer(
        e2e_db,
        name="Field Service Customer",
        email="fs.customer@test.com",
        phone="+234 800 123 4567",
    )


@pytest.fixture
def test_technician(e2e_db):
    """Create a test technician for field service."""
    return create_employee(
        e2e_db,
        name="Field Technician",
        email="technician@test.com",
        department="Field Operations",
        designation="Field Technician",
    )


@pytest.fixture
def test_dispatcher(e2e_db):
    """Create a test dispatcher user."""
    return create_employee(
        e2e_db,
        name="Dispatch Manager",
        email="dispatch@test.com",
        department="Field Operations",
        designation="Dispatch Manager",
    )


# =============================================================================
# COMPLETE SERVICE ORDER FLOW
# =============================================================================


class TestServiceOrderCompleteFlow:
    """
    Test the complete service order lifecycle:
    Draft → Scheduled → Dispatched → En Route → On Site → In Progress → Completed
    """

    def test_installation_order_complete_flow(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
        test_technician,
    ):
        """
        E2E: Complete installation service order flow from creation to completion.

        Flow:
        1. Create draft service order
        2. Schedule the order
        3. Dispatch to technician
        4. Technician marks en route
        5. Technician arrives on site
        6. Technician starts work
        7. Update checklist items
        8. Add time entry
        9. Add inventory items used
        10. Complete the order
        11. Capture customer signature
        """
        client = e2e_superuser_client

        # 1. Create draft service order
        create_payload = {
            "order_type": "installation",
            "priority": "high",
            "customer_account_id": test_customer.id,
            "service_address": "123 Installation Street, Lagos",
            "city": "Lagos",
            "state": "Lagos",
            "scheduled_date": date.today().isoformat(),
            "scheduled_start_time": "09:00:00",
            "scheduled_end_time": "12:00:00",
            "estimated_duration_hours": "3.0",
            "title": "Fiber Router Installation",
            "description": "Install fiber router and configure network",
            "customer_contact_name": "John Customer",
            "customer_contact_phone": "+234 812 345 6789",
            "is_billable": True,
        }

        resp = client.post("/api/v1/field-service/orders", json=create_payload)
        assert_http_ok(resp, "Create service order")
        order = get_json(resp)

        order_id = order["id"]
        assert order["status"] == "draft"
        assert order["order_type"] == "installation"
        assert order["priority"] == "high"

        # 2. Schedule the order
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/schedule", json={
            "notes": "Scheduled for morning installation"
        })
        assert_http_ok(resp, "Schedule order")
        order = get_json(resp)
        assert order["status"] == "scheduled"

        # 3. Dispatch to technician
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/dispatch", json={
            "technician_id": test_technician.id,
            "notes": "Assigned to primary technician",
            "notify_customer": False,
        })
        assert_http_ok(resp, "Dispatch order")
        order = get_json(resp)
        assert order["status"] == "dispatched"
        assert order["assigned_technician_id"] == test_technician.id

        # 4. Technician marks en route
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/en-route", json={
            "latitude": "6.5244",
            "longitude": "3.3792",
            "notes": "Leaving office now"
        })
        assert_http_ok(resp, "Mark en route")
        order = get_json(resp)
        assert order["status"] == "en_route"

        # 5. Technician arrives on site
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/arrive", json={
            "latitude": "6.4500",
            "longitude": "3.4000",
            "notes": "Arrived at customer location"
        })
        assert_http_ok(resp, "Mark arrived")
        order = get_json(resp)
        assert order["status"] == "on_site"

        # 6. Technician starts work
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/start", json={
            "notes": "Beginning installation work"
        })
        assert_http_ok(resp, "Start work")
        order = get_json(resp)
        assert order["status"] == "in_progress"

        # Verify time entry was created
        assert len(order.get("time_entries", [])) >= 1, "Should have created a time entry"

        # 7. Update checklist items (if any exist)
        if order.get("checklist_items"):
            for item in order["checklist_items"]:
                resp = client.patch(
                    f"/api/v1/field-service/orders/{order_id}/checklist/{item['id']}",
                    json={
                        "is_completed": True,
                        "notes": "Completed successfully",
                    }
                )
                assert_http_ok(resp, f"Update checklist item {item['id']}")

        # 8. Add inventory items used
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/items", json={
            "item_name": "Fiber Router Model X",
            "quantity": "1",
            "unit": "pcs",
            "unit_cost": "75000",
        })
        assert_http_ok(resp, "Add inventory item")

        # 9. Complete the order
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/complete", json={
            "notes": "Installation completed successfully. Customer trained on usage."
        })
        assert_http_ok(resp, "Complete order")
        order = get_json(resp)
        assert order["status"] == "completed"
        assert order["resolution_notes"] is not None

        # 10. Capture customer signature
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/signature", json={
            "signature_data": "base64encodedSignatureData==",
            "signer_name": "John Customer",
            "rating": 5,
            "feedback": "Excellent service! Very professional technician."
        })
        assert_http_ok(resp, "Capture signature")
        signature = get_json(resp)
        assert signature["signed"] is True
        assert signature["rating"] == 5

        # Verify final state
        resp = client.get(f"/api/v1/field-service/orders/{order_id}")
        final_order = get_json(resp)
        assert final_order["status"] == "completed"
        assert final_order["customer_rating"] == 5
        assert final_order["has_signature"] is True


class TestServiceOrderRescheduleFlow:
    """Test the rescheduling flow for service orders."""

    def test_reschedule_scheduled_order(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
    ):
        """
        E2E: Reschedule a scheduled service order.

        Flow:
        1. Create and schedule order
        2. Reschedule to a future date
        3. Verify order is rescheduled and still active
        """
        client = e2e_superuser_client

        # Create and schedule order
        create_payload = {
            "order_type": "maintenance",
            "customer_account_id": test_customer.id,
            "service_address": "456 Maintenance Ave",
            "scheduled_date": date.today().isoformat(),
            "title": "Routine Maintenance",
        }
        resp = client.post("/api/v1/field-service/orders", json=create_payload)
        order = get_json(resp)
        order_id = order["id"]

        # Schedule it
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/schedule", json={})
        assert_http_ok(resp, "Schedule order")

        # Reschedule to next week
        new_date = date.today() + timedelta(days=7)
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/reschedule", json={
            "scheduled_date": new_date.isoformat(),
            "scheduled_start_time": "14:00:00",
            "reason": "Customer requested different date",
            "notify_customer": False,
        })
        assert_http_ok(resp, "Reschedule order")
        order = get_json(resp)

        assert order["status"] == "scheduled"
        assert order["scheduled_date"] == new_date.isoformat()


class TestServiceOrderCancellationFlow:
    """Test cancellation flows for service orders."""

    def test_cancel_scheduled_order(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
    ):
        """
        E2E: Cancel a scheduled service order.
        """
        client = e2e_superuser_client

        # Create and schedule order
        create_payload = {
            "order_type": "repair",
            "customer_account_id": test_customer.id,
            "service_address": "789 Cancel Street",
            "scheduled_date": date.today().isoformat(),
            "title": "Repair Work",
        }
        resp = client.post("/api/v1/field-service/orders", json=create_payload)
        order = get_json(resp)
        order_id = order["id"]

        # Schedule it
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/schedule", json={})
        assert_http_ok(resp, "Schedule order")

        # Cancel the order
        resp = client.delete(f"/api/v1/field-service/orders/{order_id}")
        assert_http_ok(resp, "Cancel order")
        result = get_json(resp)
        assert "cancelled" in result["message"].lower()

        # Verify cancelled status
        resp = client.get(f"/api/v1/field-service/orders/{order_id}")
        order = get_json(resp)
        assert order["status"] == "cancelled"


class TestBulkOperationsFlow:
    """Test bulk operations on service orders."""

    def test_bulk_reschedule_orders(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
    ):
        """
        E2E: Bulk reschedule multiple orders to a new date.
        """
        client = e2e_superuser_client

        # Create multiple orders
        order_ids = []
        for i in range(3):
            resp = client.post("/api/v1/field-service/orders", json={
                "order_type": "maintenance",
                "customer_account_id": test_customer.id,
                "service_address": f"{i} Bulk Street",
                "scheduled_date": date.today().isoformat(),
                "title": f"Bulk Order {i}",
            })
            order = get_json(resp)

            # Schedule each order
            resp = client.post(f"/api/v1/field-service/orders/{order['id']}/schedule", json={})
            assert_http_ok(resp)
            order_ids.append(order["id"])

        # Bulk reschedule
        new_date = date.today() + timedelta(days=14)
        resp = client.post("/api/v1/field-service/orders/bulk/reschedule", json={
            "order_ids": order_ids,
            "scheduled_date": new_date.isoformat(),
            "reason": "Weather delay - all outdoor work postponed",
            "notify_customers": False,
        })
        assert_http_ok(resp, "Bulk reschedule")
        result = get_json(resp)

        assert result["rescheduled_count"] == 3
        assert len(result["errors"]) == 0

        # Verify all orders were rescheduled
        for order_id in order_ids:
            resp = client.get(f"/api/v1/field-service/orders/{order_id}")
            order = get_json(resp)
            assert order["scheduled_date"] == new_date.isoformat()


class TestEmergencyServiceFlow:
    """Test emergency/urgent service order handling."""

    def test_urgent_order_expedited_dispatch(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
        test_technician,
    ):
        """
        E2E: Create and expedite an urgent service order.

        Flow:
        1. Create urgent priority order
        2. Immediately dispatch
        3. Fast-track through to completion
        """
        client = e2e_superuser_client

        # Create urgent order
        resp = client.post("/api/v1/field-service/orders", json={
            "order_type": "repair",
            "priority": "urgent",
            "customer_account_id": test_customer.id,
            "service_address": "Emergency Location",
            "scheduled_date": date.today().isoformat(),
            "title": "URGENT: Network Down",
            "description": "Customer network completely down - business critical",
        })
        order = get_json(resp)
        order_id = order["id"]
        assert order["priority"] == "urgent"

        # Schedule immediately
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/schedule", json={
            "notes": "URGENT - expedited scheduling"
        })
        assert_http_ok(resp)

        # Dispatch immediately
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/dispatch", json={
            "technician_id": test_technician.id,
            "notes": "URGENT dispatch - highest priority",
            "notify_customer": False,
        })
        assert_http_ok(resp)

        # Simulate rapid response - directly to in progress
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/en-route", json={})
        assert_http_ok(resp)

        resp = client.post(f"/api/v1/field-service/orders/{order_id}/arrive", json={})
        assert_http_ok(resp)

        resp = client.post(f"/api/v1/field-service/orders/{order_id}/start", json={})
        assert_http_ok(resp)

        resp = client.post(f"/api/v1/field-service/orders/{order_id}/complete", json={
            "notes": "Emergency resolved - replaced faulty equipment"
        })
        assert_http_ok(resp)

        # Verify completed urgent order
        resp = client.get(f"/api/v1/field-service/orders/{order_id}")
        order = get_json(resp)
        assert order["status"] == "completed"
        assert order["priority"] == "urgent"


class TestMultiTechnicianFlow:
    """Test scenarios involving multiple technicians."""

    def test_reassign_order_to_different_technician(
        self,
        e2e_superuser_client,
        e2e_db,
        test_customer,
        test_technician,
    ):
        """
        E2E: Reassign a dispatched order to a different technician.
        """
        client = e2e_superuser_client

        # Create second technician
        tech2 = create_employee(
            e2e_db,
            name="Second Technician",
            email="tech2@test.com",
            department="Field Operations",
        )

        # Create and dispatch order to first technician
        resp = client.post("/api/v1/field-service/orders", json={
            "order_type": "installation",
            "customer_account_id": test_customer.id,
            "service_address": "Reassign Street",
            "scheduled_date": date.today().isoformat(),
            "title": "Order to Reassign",
        })
        order = get_json(resp)
        order_id = order["id"]

        # Schedule
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/schedule", json={})
        assert_http_ok(resp)

        # Dispatch to first technician
        resp = client.post(f"/api/v1/field-service/orders/{order_id}/dispatch", json={
            "technician_id": test_technician.id,
            "notify_customer": False,
        })
        assert_http_ok(resp)
        order = get_json(resp)
        assert order["assigned_technician_id"] == test_technician.id

        # Reassign to second technician via update
        resp = client.patch(f"/api/v1/field-service/orders/{order_id}", json={
            "assigned_technician_id": tech2.id,
        })
        assert_http_ok(resp, "Reassign technician")
        order = get_json(resp)
        assert order["assigned_technician_id"] == tech2.id
