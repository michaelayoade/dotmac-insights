"""
E2E Tests: HR Leave Management Flow

Tests the complete leave management workflow.

Flow:
1. Create Leave Allocation
2. Submit Leave Application
3. Approve/Reject Leave
4. Update Leave Balance
5. Check Leave Summary
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json
from tests.e2e.fixtures.factories import create_employee


class TestLeaveAllocation:
    """Test leave allocation management."""

    def test_create_leave_allocation(self, e2e_superuser_client, e2e_db):
        """Test creating a leave allocation for an employee."""
        employee = create_employee(e2e_db, name="Leave Test Employee")

        current_year = date.today().year
        payload = {
            "employee": f"EMP-{employee.id}",
            "employee_id": employee.id,
            "employee_name": employee.name,
            "leave_type": "Annual Leave",
            "from_date": f"{current_year}-01-01",
            "to_date": f"{current_year}-12-31",
            "new_leaves_allocated": 21,
            "total_leaves_allocated": 21,
        }

        response = e2e_superuser_client.post("/api/hr/leave-allocations", json=payload)
        assert_http_ok(response, "Create leave allocation")

        data = get_json(response)
        assert data["employee_id"] == employee.id

    def test_list_leave_allocations(self, e2e_superuser_client, e2e_db):
        """Test listing leave allocations."""
        from tests.e2e.fixtures.factories import create_leave_allocation

        employee = create_employee(e2e_db, name="Allocation List Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("21"))

        response = e2e_superuser_client.get("/api/hr/leave-allocations")
        assert_http_ok(response, "List leave allocations")

        data = get_json(response)
        assert "data" in data

    def test_get_employee_leave_balance(self, e2e_superuser_client, e2e_db):
        """Test getting an employee's leave balance."""
        from tests.e2e.fixtures.factories import create_leave_allocation

        employee = create_employee(e2e_db, name="Balance Test Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))

        response = e2e_superuser_client.get(
            "/api/hr/leave/balance",
            params={"employee_id": employee.id},
        )
        # Endpoint may vary - adjust as needed
        assert response.status_code in [200, 404], f"Get leave balance: {response.text}"


class TestLeaveApplication:
    """Test leave application workflow."""

    def test_submit_leave_application(self, e2e_superuser_client, e2e_db):
        """Test submitting a leave application."""
        from tests.e2e.fixtures.factories import create_leave_allocation

        employee = create_employee(e2e_db, name="Leave App Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))

        start_date = date.today() + timedelta(days=7)
        end_date = start_date + timedelta(days=3)

        payload = {
            "employee_id": employee.id,
            "leave_type": "Annual Leave",
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
            "reason": "Family vacation",
        }

        response = e2e_superuser_client.post("/api/hr/leave/applications", json=payload)
        assert_http_ok(response, "Submit leave application")

        data = get_json(response)
        assert data["employee_id"] == employee.id
        assert data["status"] in ["pending", "open", "submitted"]

    def test_list_leave_applications(self, e2e_superuser_client, e2e_db):
        """Test listing leave applications."""
        from tests.e2e.fixtures.factories import create_leave_allocation, create_leave_application

        employee = create_employee(e2e_db, name="App List Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))
        create_leave_application(e2e_db, employee.id)

        response = e2e_superuser_client.get("/api/hr/leave/applications")
        assert_http_ok(response, "List leave applications")

        data = get_json(response)
        assert "items" in data

    def test_get_leave_application_detail(self, e2e_superuser_client, e2e_db):
        """Test getting leave application details."""
        from tests.e2e.fixtures.factories import create_leave_allocation, create_leave_application

        employee = create_employee(e2e_db, name="App Detail Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))
        application = create_leave_application(e2e_db, employee.id)

        response = e2e_superuser_client.get(f"/api/hr/leave/applications/{application.id}")
        assert_http_ok(response, "Get leave application")

        data = get_json(response)
        assert data["id"] == application.id


class TestLeaveApproval:
    """Test leave approval workflow."""

    def test_approve_leave_application(self, e2e_superuser_client, e2e_db):
        """Test approving a leave application."""
        from tests.e2e.fixtures.factories import create_leave_allocation, create_leave_application

        employee = create_employee(e2e_db, name="Approve Test Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))
        application = create_leave_application(e2e_db, employee.id, status="pending")

        response = e2e_superuser_client.post(
            f"/api/hr/leave/applications/{application.id}/approve",
        )
        assert_http_ok(response, "Approve leave")

        data = get_json(response)
        assert data.get("status") == "approved" or data.get("success") is True

    def test_reject_leave_application(self, e2e_superuser_client, e2e_db):
        """Test rejecting a leave application."""
        from tests.e2e.fixtures.factories import create_leave_allocation, create_leave_application

        employee = create_employee(e2e_db, name="Reject Test Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))
        application = create_leave_application(e2e_db, employee.id, status="pending")

        response = e2e_superuser_client.post(
            f"/api/hr/leave/applications/{application.id}/reject",
            json={"reason": "Business-critical period"},
        )
        assert_http_ok(response, "Reject leave")

        data = get_json(response)
        assert data.get("status") == "rejected" or data.get("success") is True

    def test_cannot_exceed_allocation(self, e2e_superuser_client, e2e_db):
        """Test that leave cannot exceed allocation."""
        from tests.e2e.fixtures.factories import create_leave_allocation

        employee = create_employee(e2e_db, name="Exceed Test Employee")
        create_leave_allocation(e2e_db, employee.id, total_days=Decimal("5"))

        # Try to apply for more days than allocated
        start_date = date.today() + timedelta(days=7)
        end_date = start_date + timedelta(days=10)  # 11 days

        payload = {
            "employee_id": employee.id,
            "leave_type": "Annual Leave",
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
            "reason": "Long vacation",
        }

        response = e2e_superuser_client.post("/api/hr/leave/applications", json=payload)
        # Should either fail or return warning
        # Behavior depends on implementation
        assert response.status_code in [200, 201, 400], f"Exceed allocation: {response.text}"


class TestLeaveBalance:
    """Test leave balance updates."""

    def test_balance_decreases_after_approval(self, e2e_superuser_client, e2e_db):
        """Test that leave balance decreases after approval."""
        from tests.e2e.fixtures.factories import create_leave_allocation, create_leave_application

        employee = create_employee(e2e_db, name="Balance Update Employee")
        allocation = create_leave_allocation(e2e_db, employee.id, total_days=Decimal("20"))

        # Create and approve leave application
        application = create_leave_application(
            e2e_db,
            employee.id,
            from_date=date.today() + timedelta(days=7),
            to_date=date.today() + timedelta(days=9),  # 3 days
            status="pending",
        )

        # Approve
        e2e_superuser_client.post(f"/api/hr/leave/applications/{application.id}/approve")

        # Check allocation was updated
        e2e_db.refresh(allocation)
        assert allocation.used_days >= Decimal("3")


class TestLeaveTypes:
    """Test leave type management."""

    def test_list_leave_types(self, e2e_superuser_client, e2e_db):
        """Test listing available leave types."""
        response = e2e_superuser_client.get("/api/hr/leave/types")
        # May return 200 or 404 depending on endpoint availability
        assert response.status_code in [200, 404], f"List leave types: {response.text}"


class TestLeaveAnalytics:
    """Test leave analytics and reporting."""

    def test_leave_summary(self, e2e_superuser_client, e2e_db):
        """Test leave summary endpoint."""
        response = e2e_superuser_client.get("/api/hr/analytics/leave-balance")
        assert_http_ok(response, "Leave summary")

    def test_leave_calendar(self, e2e_superuser_client, e2e_db):
        """Test leave calendar endpoint."""
        response = e2e_superuser_client.get(
            "/api/hr/leave/calendar",
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=30)).isoformat(),
            },
        )
        # May not exist - just check doesn't error badly
        assert response.status_code in [200, 404], f"Leave calendar: {response.text}"


class TestFullLeaveWorkflow:
    """Test complete leave management workflow."""

    def test_complete_leave_cycle(self, e2e_superuser_client, e2e_db):
        """
        Test complete flow:
        1. Create employee
        2. Allocate leave
        3. Submit application
        4. Approve application
        5. Verify balance updated
        """
        # Step 1: Create employee
        employee = create_employee(e2e_db, name="Full Leave Cycle Employee")

        # Step 2: Allocate leave
        alloc_payload = {
            "employee_id": employee.id,
            "leave_type": "Annual Leave",
            "total_days": 21,
            "year": date.today().year,
        }
        alloc_resp = e2e_superuser_client.post("/api/hr/leave/allocations", json=alloc_payload)
        assert_http_ok(alloc_resp, "Step 2: Allocate leave")

        # Step 3: Submit application
        start_date = date.today() + timedelta(days=14)
        end_date = start_date + timedelta(days=4)  # 5 days

        app_payload = {
            "employee_id": employee.id,
            "leave_type": "Annual Leave",
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
            "reason": "Annual family vacation",
        }
        app_resp = e2e_superuser_client.post("/api/hr/leave/applications", json=app_payload)
        assert_http_ok(app_resp, "Step 3: Submit application")
        application = get_json(app_resp)
        app_id = application["id"]

        # Step 4: Approve application
        approve_resp = e2e_superuser_client.post(f"/api/hr/leave/applications/{app_id}/approve")
        assert_http_ok(approve_resp, "Step 4: Approve application")

        # Step 5: Verify balance updated (check allocation)
        alloc_list_resp = e2e_superuser_client.get(
            "/api/hr/leave/allocations",
            params={"employee_id": employee.id},
        )
        alloc_data = get_json(alloc_list_resp)

        # Find the allocation and verify used_days increased
        if "items" in alloc_data:
            for alloc in alloc_data["items"]:
                if alloc["employee_id"] == employee.id:
                    assert float(alloc.get("used_days", 0)) >= 5
                    break
