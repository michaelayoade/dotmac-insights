"""
Field Service API Integration Tests

Tests service order CRUD, lifecycle transitions, checklists,
time entries, and RBAC for the Field Service API.
"""
import pytest
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal

from app.models.field_service import (
    ServiceOrder, ServiceOrderStatus, ServiceOrderType, ServiceOrderPriority,
    ServiceChecklist, ServiceTimeEntry, ServiceOrderItem, TimeEntryType
)
from app.models.customer import Customer
from app.models.employee import Employee


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_customer(integration_db):
    """Create a test customer."""
    customer = Customer(
        name="Test Customer",
        email="customer@test.com",
        phone="+234 800 123 4567",
        address="123 Test Street, Lagos",
    )
    integration_db.add(customer)
    integration_db.commit()
    integration_db.refresh(customer)
    return customer


@pytest.fixture
def sample_technician(integration_db):
    """Create a test technician."""
    technician = Employee(
        name="John Technician",
        email="tech@test.com",
        is_active=True,
    )
    integration_db.add(technician)
    integration_db.commit()
    integration_db.refresh(technician)
    return technician


@pytest.fixture
def sample_order_payload(sample_customer):
    """Base payload for creating a service order."""
    return {
        "order_type": "installation",
        "priority": "medium",
        "customer_id": sample_customer.id,
        "service_address": "456 Service Road, Lagos",
        "city": "Lagos",
        "state": "Lagos",
        "scheduled_date": date.today().isoformat(),
        "estimated_duration_hours": "2.0",
        "title": "Router Installation",
        "description": "Install new fiber router at customer location",
        "customer_contact_name": "John Doe",
        "customer_contact_phone": "+234 812 345 6789",
        "is_billable": True,
    }


@pytest.fixture
def create_test_order(integration_db, sample_customer):
    """Factory fixture to create test service orders."""
    created = []

    def _create(
        title: str = "Test Service Order",
        order_type: ServiceOrderType = ServiceOrderType.INSTALLATION,
        status: ServiceOrderStatus = ServiceOrderStatus.DRAFT,
        priority: ServiceOrderPriority = ServiceOrderPriority.MEDIUM,
        scheduled_date: date = None,
        assigned_technician_id: int = None,
        service_address: str = "123 Test Street",
        estimated_duration_hours: Decimal = Decimal("1.0"),
    ) -> ServiceOrder:
        order = ServiceOrder(
            order_number=f"SO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-TEST",
            order_type=order_type,
            status=status,
            priority=priority,
            customer_id=sample_customer.id,
            assigned_technician_id=assigned_technician_id,
            service_address=service_address,
            city="Lagos",
            state="Lagos",
            scheduled_date=scheduled_date or date.today(),
            estimated_duration_hours=estimated_duration_hours,
            title=title,
            customer_contact_name="Test Contact",
            is_billable=True,
        )
        integration_db.add(order)
        integration_db.commit()
        integration_db.refresh(order)
        created.append(order)
        return order

    yield _create


# =============================================================================
# SERVICE ORDER CRUD TESTS
# =============================================================================


class TestServiceOrderCreate:
    """Tests for POST /api/field-service/orders"""

    def test_create_order_success(self, auth_client, sample_order_payload):
        """Create a service order successfully."""
        client = auth_client(["field-service:write"])
        resp = client.post("/api/field-service/orders", json=sample_order_payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Router Installation"
        assert data["order_type"] == "installation"
        assert data["status"] == "draft"
        assert data["priority"] == "medium"
        assert data["order_number"] is not None

    def test_create_order_with_different_types(self, auth_client, sample_customer):
        """Create orders with different types."""
        client = auth_client(["field-service:write"])

        for order_type in ["installation", "maintenance", "repair", "survey", "disconnect"]:
            payload = {
                "order_type": order_type,
                "customer_id": sample_customer.id,
                "service_address": "Test Address",
                "scheduled_date": date.today().isoformat(),
                "title": f"Test {order_type.capitalize()}",
            }
            resp = client.post("/api/field-service/orders", json=payload)
            assert resp.status_code == 200
            assert resp.json()["order_type"] == order_type

    def test_create_order_with_different_priorities(self, auth_client, sample_customer):
        """Create orders with different priorities."""
        client = auth_client(["field-service:write"])

        for priority in ["low", "medium", "high", "urgent"]:
            payload = {
                "order_type": "maintenance",
                "priority": priority,
                "customer_id": sample_customer.id,
                "service_address": "Test Address",
                "scheduled_date": date.today().isoformat(),
                "title": f"Test {priority} priority",
            }
            resp = client.post("/api/field-service/orders", json=payload)
            assert resp.status_code == 200
            assert resp.json()["priority"] == priority

    def test_create_order_invalid_customer_fails(self, auth_client):
        """Cannot create order with non-existent customer."""
        client = auth_client(["field-service:write"])
        payload = {
            "order_type": "installation",
            "customer_id": 99999,
            "service_address": "Test Address",
            "scheduled_date": date.today().isoformat(),
            "title": "Test Order",
        }
        resp = client.post("/api/field-service/orders", json=payload)

        assert resp.status_code == 400
        assert "customer not found" in resp.json()["detail"].lower()

    def test_create_order_without_write_scope_fails(self, auth_client, sample_order_payload):
        """Cannot create order without field-service:write scope."""
        client = auth_client(["explorer:read"])
        resp = client.post("/api/field-service/orders", json=sample_order_payload)

        assert resp.status_code == 403


class TestServiceOrderRead:
    """Tests for GET /api/field-service/orders/{order_id}"""

    def test_get_order_by_id(self, auth_client, create_test_order):
        """Get a service order by ID."""
        order = create_test_order(title="Detailed Order")

        client = auth_client(["explorer:read"])
        resp = client.get(f"/api/field-service/orders/{order.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == order.id
        assert data["title"] == "Detailed Order"
        assert "checklist_items" in data
        assert "time_entries" in data
        assert "items_used" in data

    def test_get_nonexistent_order_returns_404(self, auth_client):
        """Get non-existent order returns 404."""
        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders/99999")

        assert resp.status_code == 404


class TestServiceOrderList:
    """Tests for GET /api/field-service/orders"""

    def test_list_orders_paginated(self, auth_client, create_test_order):
        """List orders with pagination."""
        for i in range(15):
            create_test_order(title=f"Order {i}")

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?limit=10&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 10
        assert data["total"] >= 15

    def test_list_orders_filter_by_status(self, auth_client, create_test_order):
        """Filter orders by status."""
        create_test_order(title="Draft Order", status=ServiceOrderStatus.DRAFT)
        create_test_order(title="Scheduled Order", status=ServiceOrderStatus.SCHEDULED)

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?status=draft")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["status"] == "draft" for o in data["data"])

    def test_list_orders_filter_by_type(self, auth_client, create_test_order):
        """Filter orders by type."""
        create_test_order(order_type=ServiceOrderType.INSTALLATION)
        create_test_order(order_type=ServiceOrderType.MAINTENANCE)

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?order_type=installation")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["order_type"] == "installation" for o in data["data"])

    def test_list_orders_filter_by_priority(self, auth_client, create_test_order):
        """Filter orders by priority."""
        create_test_order(priority=ServiceOrderPriority.URGENT)
        create_test_order(priority=ServiceOrderPriority.LOW)

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?priority=urgent")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["priority"] == "urgent" for o in data["data"])

    def test_list_orders_filter_by_technician(self, auth_client, create_test_order, sample_technician):
        """Filter orders by assigned technician."""
        create_test_order(assigned_technician_id=sample_technician.id)
        create_test_order(assigned_technician_id=None)

        client = auth_client(["explorer:read"])
        resp = client.get(f"/api/field-service/orders?technician_id={sample_technician.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["assigned_technician_id"] == sample_technician.id for o in data["data"])

    def test_list_orders_filter_by_date_range(self, auth_client, create_test_order):
        """Filter orders by scheduled date range."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        create_test_order(scheduled_date=today)
        create_test_order(scheduled_date=tomorrow)

        client = auth_client(["explorer:read"])
        resp = client.get(f"/api/field-service/orders?date_from={today.isoformat()}&date_to={today.isoformat()}")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["scheduled_date"] == today.isoformat() for o in data["data"])

    def test_list_orders_filter_unassigned(self, auth_client, create_test_order, sample_technician):
        """Filter for unassigned orders."""
        create_test_order(assigned_technician_id=None)
        create_test_order(assigned_technician_id=sample_technician.id)

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?unassigned_only=true")

        assert resp.status_code == 200
        data = resp.json()
        assert all(o["assigned_technician_id"] is None for o in data["data"])

    def test_list_orders_search(self, auth_client, create_test_order):
        """Search orders by title or order number."""
        create_test_order(title="Router Installation Project")
        create_test_order(title="Maintenance Visit")

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders?search=Router")

        assert resp.status_code == 200
        data = resp.json()
        assert any("Router" in o["title"] for o in data["data"])


class TestServiceOrderUpdate:
    """Tests for PATCH /api/field-service/orders/{order_id}"""

    def test_update_order_basic_fields(self, auth_client, create_test_order):
        """Update basic order fields."""
        order = create_test_order()

        client = auth_client(["field-service:write"])
        resp = client.patch(f"/api/field-service/orders/{order.id}", json={
            "title": "Updated Title",
            "description": "Updated description",
            "priority": "high",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["priority"] == "high"

    def test_update_order_status(self, auth_client, create_test_order):
        """Update order status."""
        order = create_test_order(status=ServiceOrderStatus.DRAFT)

        client = auth_client(["field-service:write"])
        resp = client.patch(f"/api/field-service/orders/{order.id}", json={
            "status": "scheduled",
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "scheduled"

    def test_update_nonexistent_order_returns_404(self, auth_client):
        """Update non-existent order returns 404."""
        client = auth_client(["field-service:write"])
        resp = client.patch("/api/field-service/orders/99999", json={"title": "Ghost"})

        assert resp.status_code == 404


class TestServiceOrderDelete:
    """Tests for DELETE /api/field-service/orders/{order_id}"""

    def test_delete_order_cancels(self, auth_client, create_test_order, integration_db):
        """Delete order sets status to cancelled."""
        order = create_test_order(status=ServiceOrderStatus.DRAFT)

        client = auth_client(["field-service:write"])
        resp = client.delete(f"/api/field-service/orders/{order.id}")

        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"].lower()

        integration_db.refresh(order)
        assert order.status == ServiceOrderStatus.CANCELLED

    def test_delete_completed_order_fails(self, auth_client, create_test_order):
        """Cannot delete completed orders."""
        order = create_test_order(status=ServiceOrderStatus.COMPLETED)

        client = auth_client(["field-service:write"])
        resp = client.delete(f"/api/field-service/orders/{order.id}")

        assert resp.status_code == 400
        assert "completed" in resp.json()["detail"].lower()


# =============================================================================
# LIFECYCLE TRANSITION TESTS
# =============================================================================


class TestServiceOrderLifecycle:
    """Tests for order lifecycle transitions."""

    def test_schedule_order(self, auth_client, create_test_order, integration_db):
        """Schedule a draft order."""
        order = create_test_order(status=ServiceOrderStatus.DRAFT)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/schedule", json={
            "notes": "Scheduled for installation",
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "scheduled"

    def test_schedule_non_draft_fails(self, auth_client, create_test_order):
        """Cannot schedule non-draft order."""
        order = create_test_order(status=ServiceOrderStatus.SCHEDULED)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/schedule", json={})

        assert resp.status_code == 400

    def test_dispatch_order(self, auth_client, create_test_order, sample_technician, integration_db):
        """Dispatch order to technician."""
        order = create_test_order(status=ServiceOrderStatus.SCHEDULED)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/dispatch", json={
            "technician_id": sample_technician.id,
            "notify_customer": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dispatched"
        assert data["assigned_technician_id"] == sample_technician.id

    def test_dispatch_invalid_technician_fails(self, auth_client, create_test_order):
        """Cannot dispatch to non-existent technician."""
        order = create_test_order(status=ServiceOrderStatus.SCHEDULED)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/dispatch", json={
            "technician_id": 99999,
        })

        assert resp.status_code == 400
        assert "technician not found" in resp.json()["detail"].lower()

    def test_mark_en_route(self, auth_client, create_test_order, sample_technician, integration_db):
        """Mark technician as en route."""
        order = create_test_order(
            status=ServiceOrderStatus.DISPATCHED,
            assigned_technician_id=sample_technician.id,
        )

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/en-route", json={
            "latitude": "6.5244",
            "longitude": "3.3792",
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "en_route"

    def test_mark_arrived(self, auth_client, create_test_order, sample_technician, integration_db):
        """Mark technician as arrived on site."""
        order = create_test_order(status=ServiceOrderStatus.DISPATCHED)
        order.status = ServiceOrderStatus.EN_ROUTE
        integration_db.commit()

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/arrive", json={})

        assert resp.status_code == 200
        assert resp.json()["status"] == "on_site"

    def test_start_work(self, auth_client, create_test_order, sample_technician, integration_db):
        """Start work on order."""
        order = create_test_order(
            status=ServiceOrderStatus.DISPATCHED,
            assigned_technician_id=sample_technician.id,
        )
        order.status = ServiceOrderStatus.ON_SITE
        integration_db.commit()

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/start", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        # Should have created a time entry
        assert len(data["time_entries"]) >= 1

    def test_complete_order(self, auth_client, create_test_order, sample_technician, integration_db):
        """Complete a service order."""
        order = create_test_order(
            status=ServiceOrderStatus.DISPATCHED,
            assigned_technician_id=sample_technician.id,
        )
        order.status = ServiceOrderStatus.IN_PROGRESS
        integration_db.commit()

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/complete", json={
            "notes": "All work completed successfully",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["resolution_notes"] == "All work completed successfully"

    def test_reschedule_order(self, auth_client, create_test_order, integration_db):
        """Reschedule a service order."""
        order = create_test_order(status=ServiceOrderStatus.SCHEDULED)
        new_date = date.today() + timedelta(days=7)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/reschedule", json={
            "scheduled_date": new_date.isoformat(),
            "reason": "Customer requested different date",
            "notify_customer": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["scheduled_date"] == new_date.isoformat()

    def test_reschedule_completed_order_fails(self, auth_client, create_test_order):
        """Cannot reschedule completed orders."""
        order = create_test_order(status=ServiceOrderStatus.COMPLETED)

        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/reschedule", json={
            "scheduled_date": date.today().isoformat(),
            "reason": "Test",
        })

        assert resp.status_code == 400


# =============================================================================
# CHECKLIST TESTS
# =============================================================================


class TestServiceOrderChecklist:
    """Tests for checklist operations."""

    def test_update_checklist_item(self, auth_client, create_test_order, integration_db):
        """Update a checklist item."""
        order = create_test_order()

        # Add a checklist item
        item = ServiceChecklist(
            service_order_id=order.id,
            idx=1,
            item_text="Test equipment",
            is_required=True,
        )
        integration_db.add(item)
        integration_db.commit()
        integration_db.refresh(item)

        client = auth_client(["field-service:mobile"])
        resp = client.patch(
            f"/api/field-service/orders/{order.id}/checklist/{item.id}",
            json={
                "is_completed": True,
                "notes": "All tests passed",
                "measurement_value": "25 Mbps",
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_completed"] is True
        assert data["notes"] == "All tests passed"
        assert data["measurement_value"] == "25 Mbps"
        assert data["completed_at"] is not None

    def test_update_nonexistent_checklist_item_fails(self, auth_client, create_test_order):
        """Cannot update non-existent checklist item."""
        order = create_test_order()

        client = auth_client(["field-service:mobile"])
        resp = client.patch(
            f"/api/field-service/orders/{order.id}/checklist/99999",
            json={"is_completed": True}
        )

        assert resp.status_code == 404


# =============================================================================
# TIME ENTRY TESTS
# =============================================================================


class TestTimeEntries:
    """Tests for time entry operations."""

    def test_add_time_entry(self, auth_client, create_test_order, sample_technician, integration_db):
        """Add a time entry to an order."""
        order = create_test_order(assigned_technician_id=sample_technician.id)

        client = auth_client(["field-service:mobile"])
        now = datetime.now(timezone.utc)
        resp = client.post(f"/api/field-service/orders/{order.id}/time-entries", json={
            "entry_type": "work",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "notes": "Installation work",
            "is_billable": True,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["entry_type"] == "work"
        assert data["duration_hours"] is not None
        assert abs(data["duration_hours"] - 2.0) < 0.1

    def test_add_time_entry_no_technician_fails(self, auth_client, create_test_order):
        """Cannot add time entry if no technician assigned."""
        order = create_test_order(assigned_technician_id=None)

        client = auth_client(["field-service:mobile"])
        now = datetime.now(timezone.utc)
        resp = client.post(f"/api/field-service/orders/{order.id}/time-entries", json={
            "entry_type": "work",
            "start_time": now.isoformat(),
        })

        assert resp.status_code == 400
        assert "technician" in resp.json()["detail"].lower()


# =============================================================================
# INVENTORY ITEMS TESTS
# =============================================================================


class TestItemsUsed:
    """Tests for inventory item operations."""

    def test_add_item_used(self, auth_client, create_test_order, integration_db):
        """Add an inventory item to an order."""
        order = create_test_order()

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/items", json={
            "item_name": "Fiber Router",
            "quantity": "1",
            "unit": "pcs",
            "unit_cost": "45000",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_name"] == "Fiber Router"
        assert data["quantity"] == 1.0
        assert data["total_cost"] == 45000.0

        # Verify order parts cost updated
        integration_db.refresh(order)
        assert order.parts_cost == Decimal("45000")


# =============================================================================
# SIGNATURE CAPTURE TESTS
# =============================================================================


class TestSignatureCapture:
    """Tests for signature capture operations."""

    def test_capture_signature(self, auth_client, create_test_order, integration_db):
        """Capture customer signature."""
        order = create_test_order()

        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/signature", json={
            "signature_data": "base64encodeddata==",
            "signer_name": "John Customer",
            "rating": 5,
            "feedback": "Excellent service!",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["signed"] is True
        assert data["signer_name"] == "John Customer"
        assert data["rating"] == 5

        integration_db.refresh(order)
        assert order.customer_signature is not None
        assert order.customer_rating == 5


# =============================================================================
# BULK OPERATIONS TESTS
# =============================================================================


class TestBulkOperations:
    """Tests for bulk operations."""

    def test_bulk_reschedule(self, auth_client, create_test_order):
        """Bulk reschedule multiple orders."""
        order1 = create_test_order(title="Order 1", status=ServiceOrderStatus.SCHEDULED)
        order2 = create_test_order(title="Order 2", status=ServiceOrderStatus.SCHEDULED)
        new_date = date.today() + timedelta(days=14)

        client = auth_client(["field-service:dispatch"])
        resp = client.post("/api/field-service/orders/bulk/reschedule", json={
            "order_ids": [order1.id, order2.id],
            "scheduled_date": new_date.isoformat(),
            "reason": "Weather delay",
            "notify_customers": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["rescheduled_count"] == 2
        assert len(data["errors"]) == 0

    def test_bulk_cancel(self, auth_client, create_test_order):
        """Bulk cancel multiple orders."""
        order1 = create_test_order(title="Order 1", status=ServiceOrderStatus.SCHEDULED)
        order2 = create_test_order(title="Order 2", status=ServiceOrderStatus.DRAFT)

        client = auth_client(["field-service:dispatch"])
        resp = client.post("/api/field-service/orders/bulk/cancel", json={
            "order_ids": [order1.id, order2.id],
            "reason": "Project cancelled",
            "notify_customers": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled_count"] == 2


# =============================================================================
# DASHBOARD TESTS
# =============================================================================


class TestFieldServiceDashboard:
    """Tests for dashboard endpoint."""

    def test_get_dashboard(self, auth_client, create_test_order):
        """Get field service dashboard metrics."""
        # Create some orders with different statuses
        create_test_order(status=ServiceOrderStatus.DRAFT)
        create_test_order(status=ServiceOrderStatus.SCHEDULED)
        create_test_order(status=ServiceOrderStatus.IN_PROGRESS)
        create_test_order(status=ServiceOrderStatus.COMPLETED)

        client = auth_client(["analytics:read"])
        resp = client.get("/api/field-service/dashboard")

        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "by_status" in data
        assert "by_type" in data
        assert "today" in data
        assert data["summary"]["total_orders"] >= 4


# =============================================================================
# RBAC TESTS
# =============================================================================


class TestFieldServiceRBAC:
    """Tests for role-based access control."""

    def test_read_scope_allows_list(self, auth_client, create_test_order):
        """Read scope allows listing orders."""
        create_test_order()

        client = auth_client(["explorer:read"])
        resp = client.get("/api/field-service/orders")

        assert resp.status_code == 200

    def test_read_scope_denies_write(self, auth_client, sample_customer):
        """Read scope denies create operations."""
        client = auth_client(["explorer:read"])
        resp = client.post("/api/field-service/orders", json={
            "order_type": "installation",
            "customer_id": sample_customer.id,
            "service_address": "Test",
            "scheduled_date": date.today().isoformat(),
            "title": "Test",
        })

        assert resp.status_code == 403

    def test_dispatch_scope_for_lifecycle(self, auth_client, create_test_order, sample_technician):
        """Dispatch scope required for lifecycle operations."""
        order = create_test_order(status=ServiceOrderStatus.SCHEDULED)

        # With dispatch scope - should work
        client = auth_client(["field-service:dispatch"])
        resp = client.post(f"/api/field-service/orders/{order.id}/dispatch", json={
            "technician_id": sample_technician.id,
        })
        assert resp.status_code == 200

    def test_mobile_scope_for_field_operations(self, auth_client, create_test_order, sample_technician, integration_db):
        """Mobile scope required for field operations."""
        order = create_test_order(
            status=ServiceOrderStatus.DISPATCHED,
            assigned_technician_id=sample_technician.id,
        )

        # With mobile scope - should work
        client = auth_client(["field-service:mobile"])
        resp = client.post(f"/api/field-service/orders/{order.id}/en-route", json={})
        assert resp.status_code == 200

    def test_superuser_has_full_access(self, superuser_client, create_test_order):
        """Superuser can perform all operations."""
        order = create_test_order()

        # Read
        resp = superuser_client.get(f"/api/field-service/orders/{order.id}")
        assert resp.status_code == 200

        # Update
        resp = superuser_client.patch(f"/api/field-service/orders/{order.id}", json={
            "title": "Updated"
        })
        assert resp.status_code == 200
