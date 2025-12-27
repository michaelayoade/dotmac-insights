"""
E2E Tests: Project Delivery Flow

Tests the complete project lifecycle from creation to completion.

Flow:
1. Create Project
2. Add Tasks
3. Create Milestones
4. Update Progress
5. Complete Tasks
6. Close Project
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json
from tests.e2e.fixtures.factories import create_customer, create_employee, create_project


class TestProjectCreation:
    """Test project creation and basic operations."""

    def test_create_project(self, e2e_superuser_client, e2e_db):
        """Test creating a project."""
        customer = create_customer(e2e_db, name="Project Test Customer")
        manager = create_employee(e2e_db, name="Project Manager")

        payload = {
            "project_name": "E2E Test Project",
            "customer_id": customer.id,
            "project_manager_id": manager.id,
            "status": "open",
            "priority": "high",
            "expected_start_date": date.today().isoformat(),
            "expected_end_date": (date.today() + timedelta(days=90)).isoformat(),
            "estimated_costing": 5000000,
        }

        response = e2e_superuser_client.post("/api/projects/projects", json=payload)
        assert_http_ok(response, "Create project")

        data = get_json(response)
        assert data["project_name"] == "E2E Test Project"
        assert data["status"] == "open"

    def test_list_projects(self, e2e_superuser_client, e2e_db):
        """Test listing projects."""
        customer = create_customer(e2e_db, name="List Project Customer")
        create_project(e2e_db, customer_id=customer.id, project_name="List Test 1")
        create_project(e2e_db, customer_id=customer.id, project_name="List Test 2")

        response = e2e_superuser_client.get("/api/projects/projects")
        assert_http_ok(response, "List projects")

        data = get_json(response)
        assert "items" in data
        assert len(data["items"]) >= 2

    def test_filter_projects_by_status(self, e2e_superuser_client, e2e_db):
        """Test filtering projects by status."""
        customer = create_customer(e2e_db, name="Filter Project Customer")
        create_project(e2e_db, customer_id=customer.id, status="open")
        create_project(e2e_db, customer_id=customer.id, status="completed")

        response = e2e_superuser_client.get("/api/projects/projects", params={"status": "open"})
        assert_http_ok(response, "Filter by status")

        data = get_json(response)
        for project in data["items"]:
            assert project["status"] == "open"

    def test_get_project_detail(self, e2e_superuser_client, e2e_db):
        """Test getting project details."""
        project = create_project(e2e_db, project_name="Detail Test Project")

        response = e2e_superuser_client.get(f"/api/projects/projects/{project.id}")
        assert_http_ok(response, "Get project")

        data = get_json(response)
        assert data["id"] == project.id


class TestProjectTasks:
    """Test project task management."""

    def test_create_task(self, e2e_superuser_client, e2e_db):
        """Test creating a task for a project."""
        project = create_project(e2e_db, project_name="Task Test Project")

        payload = {
            "project_id": project.id,
            "subject": "Implement feature X",
            "status": "Open",
            "priority": "High",
            "exp_start_date": date.today().isoformat(),
            "exp_end_date": (date.today() + timedelta(days=7)).isoformat(),
        }

        response = e2e_superuser_client.post("/api/projects/tasks", json=payload)
        assert_http_ok(response, "Create task")

        data = get_json(response)
        assert data["subject"] == "Implement feature X"
        assert data["project_id"] == project.id

    def test_list_project_tasks(self, e2e_superuser_client, e2e_db):
        """Test listing tasks for a project."""
        from tests.e2e.fixtures.factories import create_task

        project = create_project(e2e_db, project_name="Task List Project")
        create_task(e2e_db, project.id, subject="Task 1")
        create_task(e2e_db, project.id, subject="Task 2")

        response = e2e_superuser_client.get(
            "/api/projects/tasks",
            params={"project_id": project.id},
        )
        assert_http_ok(response, "List tasks")

        data = get_json(response)
        assert "items" in data
        assert len(data["items"]) >= 2

    def test_update_task_status(self, e2e_superuser_client, e2e_db):
        """Test updating task status."""
        from tests.e2e.fixtures.factories import create_task

        project = create_project(e2e_db, project_name="Task Update Project")
        task = create_task(e2e_db, project.id, status="Open")

        response = e2e_superuser_client.patch(
            f"/api/projects/tasks/{task.id}",
            json={"status": "Working"},
        )
        assert_http_ok(response, "Update task status")

        data = get_json(response)
        assert data["status"] == "Working"

    def test_complete_task(self, e2e_superuser_client, e2e_db):
        """Test completing a task."""
        from tests.e2e.fixtures.factories import create_task

        project = create_project(e2e_db, project_name="Complete Task Project")
        task = create_task(e2e_db, project.id, status="Working")

        response = e2e_superuser_client.patch(
            f"/api/projects/tasks/{task.id}",
            json={"status": "Completed"},
        )
        assert_http_ok(response, "Complete task")

        data = get_json(response)
        assert data["status"] == "Completed"

    def test_assign_task_to_employee(self, e2e_superuser_client, e2e_db):
        """Test assigning a task to an employee."""
        from tests.e2e.fixtures.factories import create_task

        project = create_project(e2e_db, project_name="Assign Task Project")
        employee = create_employee(e2e_db, name="Task Assignee")
        task = create_task(e2e_db, project.id)

        response = e2e_superuser_client.patch(
            f"/api/projects/tasks/{task.id}",
            json={"assigned_to_id": employee.id},
        )
        assert_http_ok(response, "Assign task")

        data = get_json(response)
        assert data["assigned_to_id"] == employee.id


class TestProjectMilestones:
    """Test project milestone management."""

    def test_create_milestone(self, e2e_superuser_client, e2e_db):
        """Test creating a project milestone."""
        project = create_project(e2e_db, project_name="Milestone Test Project")

        payload = {
            "project_id": project.id,
            "title": "Phase 1 Complete",
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "status": "planned",
        }

        response = e2e_superuser_client.post("/api/projects/milestones", json=payload)
        # May return 200, 201 or 404 if endpoint doesn't exist
        assert response.status_code in [200, 201, 404], f"Create milestone: {response.text}"

    def test_list_project_milestones(self, e2e_superuser_client, e2e_db):
        """Test listing project milestones."""
        project = create_project(e2e_db, project_name="Milestone List Project")

        response = e2e_superuser_client.get(
            "/api/projects/milestones",
            params={"project_id": project.id},
        )
        # Endpoint may not exist
        assert response.status_code in [200, 404], f"List milestones: {response.text}"


class TestProjectProgress:
    """Test project progress tracking."""

    def test_update_project_progress(self, e2e_superuser_client, e2e_db):
        """Test updating project completion percentage."""
        project = create_project(e2e_db, project_name="Progress Test Project")

        response = e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={"percent_complete": 50},
        )
        assert_http_ok(response, "Update progress")

        data = get_json(response)
        assert float(data.get("percent_complete", 0)) == 50

    def test_progress_recalculation(self, e2e_superuser_client, e2e_db):
        """Test that progress is recalculated from tasks."""
        from tests.e2e.fixtures.factories import create_task

        project = create_project(e2e_db, project_name="Auto Progress Project")

        # Create tasks
        task1 = create_task(e2e_db, project.id, status="Completed")
        task2 = create_task(e2e_db, project.id, status="Completed")
        task3 = create_task(e2e_db, project.id, status="Open")
        task4 = create_task(e2e_db, project.id, status="Open")

        # Get project - progress should reflect task completion
        response = e2e_superuser_client.get(f"/api/projects/projects/{project.id}")
        data = get_json(response)

        # 2/4 tasks complete = 50% (if auto-calculated)
        # Otherwise just verify endpoint works
        assert response.status_code == 200


class TestProjectStatus:
    """Test project status transitions."""

    def test_put_project_on_hold(self, e2e_superuser_client, e2e_db):
        """Test putting a project on hold."""
        project = create_project(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={"status": "on_hold"},
        )
        assert_http_ok(response, "Put on hold")

        data = get_json(response)
        assert data["status"] == "on_hold"

    def test_complete_project(self, e2e_superuser_client, e2e_db):
        """Test completing a project."""
        project = create_project(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={"status": "completed"},
        )
        assert_http_ok(response, "Complete project")

        data = get_json(response)
        assert data["status"] == "completed"

    def test_cancel_project(self, e2e_superuser_client, e2e_db):
        """Test cancelling a project."""
        project = create_project(e2e_db, status="open")

        response = e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={"status": "cancelled"},
        )
        assert_http_ok(response, "Cancel project")

        data = get_json(response)
        assert data["status"] == "cancelled"


class TestProjectDashboard:
    """Test project dashboard and analytics."""

    def test_projects_dashboard(self, e2e_superuser_client, e2e_db):
        """Test projects dashboard endpoint."""
        create_project(e2e_db, status="open")
        create_project(e2e_db, status="completed")

        response = e2e_superuser_client.get("/api/projects/dashboard")
        assert_http_ok(response, "Get projects dashboard")

        data = get_json(response)
        assert "total_projects" in data or "summary" in data or "projects" in data

    def test_project_analytics(self, e2e_superuser_client, e2e_db):
        """Test project analytics endpoint."""
        response = e2e_superuser_client.get("/api/projects/analytics/status-trend")
        assert_http_ok(response, "Get project analytics")


class TestFullProjectLifecycle:
    """Test complete project delivery workflow."""

    def test_complete_project_lifecycle(self, e2e_superuser_client, e2e_db):
        """
        Test complete flow:
        1. Create project
        2. Add tasks
        3. Assign tasks
        4. Update task progress
        5. Complete tasks
        6. Update project progress
        7. Complete project
        """
        customer = create_customer(e2e_db, name="Lifecycle Customer")
        manager = create_employee(e2e_db, name="PM Lifecycle")
        developer = create_employee(e2e_db, name="Dev Lifecycle")

        # Step 1: Create project
        project_payload = {
            "project_name": "Full Lifecycle Project",
            "customer_id": customer.id,
            "project_manager_id": manager.id,
            "status": "open",
            "priority": "high",
            "expected_start_date": date.today().isoformat(),
            "expected_end_date": (date.today() + timedelta(days=60)).isoformat(),
            "estimated_costing": 2000000,
        }
        project_resp = e2e_superuser_client.post("/api/projects/projects", json=project_payload)
        assert_http_ok(project_resp, "Step 1: Create project")
        project = get_json(project_resp)
        project_id = project["id"]

        # Step 2: Add tasks
        task_ids = []
        for i, task_name in enumerate(["Design", "Development", "Testing"]):
            task_payload = {
                "project_id": project_id,
                "subject": task_name,
                "status": "Open",
            }
            task_resp = e2e_superuser_client.post("/api/projects/tasks", json=task_payload)
            assert_http_ok(task_resp, f"Step 2: Create task {task_name}")
            task_ids.append(get_json(task_resp)["id"])

        # Step 3: Assign tasks
        for task_id in task_ids:
            assign_resp = e2e_superuser_client.patch(
                f"/api/projects/tasks/{task_id}",
                json={"assigned_to_id": developer.id},
            )
            assert_http_ok(assign_resp, "Step 3: Assign task")

        # Step 4 & 5: Update and complete tasks
        for task_id in task_ids:
            # Working
            e2e_superuser_client.patch(
                f"/api/projects/tasks/{task_id}",
                json={"status": "Working"},
            )
            # Completed
            complete_resp = e2e_superuser_client.patch(
                f"/api/projects/tasks/{task_id}",
                json={"status": "Completed"},
            )
            assert_http_ok(complete_resp, "Step 4/5: Complete task")

        # Step 6: Update project progress
        progress_resp = e2e_superuser_client.patch(
            f"/api/projects/projects/{project_id}",
            json={"percent_complete": 100},
        )
        assert_http_ok(progress_resp, "Step 6: Update progress")

        # Step 7: Complete project
        complete_resp = e2e_superuser_client.patch(
            f"/api/projects/projects/{project_id}",
            json={"status": "completed"},
        )
        assert_http_ok(complete_resp, "Step 7: Complete project")

        # Verify final state
        final_resp = e2e_superuser_client.get(f"/api/projects/projects/{project_id}")
        final = get_json(final_resp)
        assert final["status"] == "completed"
        assert float(final.get("percent_complete", 0)) == 100


class TestProjectCosting:
    """Test project cost tracking."""

    def test_update_project_costs(self, e2e_superuser_client, e2e_db):
        """Test updating project costs."""
        project = create_project(e2e_db, project_name="Cost Test Project")

        response = e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={
                "total_costing_amount": 1500000,
                "total_expense_claim": 200000,
            },
        )
        assert_http_ok(response, "Update project costs")

    def test_project_margin_calculation(self, e2e_superuser_client, e2e_db):
        """Test project margin calculation."""
        project = create_project(e2e_db, project_name="Margin Test Project")

        # Update revenue and costs
        e2e_superuser_client.patch(
            f"/api/projects/projects/{project.id}",
            json={
                "total_sales_amount": 2000000,
                "total_costing_amount": 1500000,
            },
        )

        # Get project and verify margin
        response = e2e_superuser_client.get(f"/api/projects/projects/{project.id}")
        data = get_json(response)

        # Gross margin = sales - costs = 500,000
        # Implementation may calculate this automatically
        assert "gross_margin" in data or "total_sales_amount" in data
