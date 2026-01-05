# Test Skill Reference

## Test Templates

### Unit Test Template (Service)

```python
"""
Unit tests for [ServiceName].

Tests [what the service does] with mocked dependencies.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest

from app.services.[service_module] import [ServiceClass]
from tests.unit.conftest import MockSession


# =============================================================================
# MOCK CLASSES
# =============================================================================


@dataclass
class Mock[Entity]:
    """Mock [entity] for testing."""
    id: int = 1
    name: str = "Test Entity"
    status: str = "active"
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MockSession()


@pytest.fixture
def service(mock_db):
    """Create service instance with mock db."""
    return [ServiceClass](mock_db)


# =============================================================================
# TESTS
# =============================================================================


class Test[ServiceClass]:
    """Tests for [ServiceClass]."""

    def test_[method]_success(self, service, mock_db):
        """Test [method] with valid input."""
        # Arrange
        mock_db.add_query_result([Mock[Entity](id=1, name="Test")])

        # Act
        result = service.[method](...)

        # Assert
        assert result is not None
        assert result["success"] is True

    def test_[method]_not_found(self, service, mock_db):
        """Test [method] when entity doesn't exist."""
        mock_db.add_query_result([])

        result = service.[method](999)

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.parametrize("input_val,expected", [
        (0, Decimal("0")),
        (100, Decimal("100")),
        (-50, Decimal("-50")),
    ])
    def test_[method]_edge_cases(self, service, input_val, expected):
        """Test [method] with various input values."""
        result = service.[method](input_val)
        assert result == expected
```

---

### Integration Test Template (API)

```python
"""
Integration tests for [Module] API.

Tests HTTP endpoints with real database operations.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

# Apply module marker
pytestmark = pytest.mark.integration


class TestCreate[Resource]:
    """Tests for creating [resource]."""

    def test_create_success(self, auth_client_with_scope):
        """Create [resource] with valid data."""
        client = auth_client_with_scope(["[module]:write"])

        payload = {
            "name": "Test Resource",
            "amount": "100.00",
        }

        response = client.post("/api/[module]/[resources]", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Resource"
        assert "id" in data

    def test_create_missing_required_field(self, auth_client_with_scope):
        """Reject creation with missing required field."""
        client = auth_client_with_scope(["[module]:write"])

        payload = {"amount": "100.00"}  # Missing 'name'

        response = client.post("/api/[module]/[resources]", json=payload)

        assert response.status_code == 422

    def test_create_requires_auth(self, unauthenticated_client):
        """Unauthenticated request rejected."""
        response = unauthenticated_client.post(
            "/api/[module]/[resources]",
            json={"name": "Test"}
        )

        assert response.status_code == 401

    def test_create_requires_write_scope(self, auth_client_with_scope):
        """Request without write scope rejected."""
        client = auth_client_with_scope(["[module]:read"])  # Read-only

        response = client.post(
            "/api/[module]/[resources]",
            json={"name": "Test"}
        )

        assert response.status_code == 403


class TestList[Resources]:
    """Tests for listing [resources]."""

    def test_list_success(self, auth_client_with_scope):
        """List [resources] returns paginated results."""
        client = auth_client_with_scope(["[module]:read"])

        response = client.get("/api/[module]/[resources]")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data

    def test_list_with_pagination(self, auth_client_with_scope):
        """Test pagination parameters."""
        client = auth_client_with_scope(["[module]:read"])

        response = client.get(
            "/api/[module]/[resources]",
            params={"limit": 10, "offset": 20}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20

    def test_list_with_filter(self, auth_client_with_scope):
        """Test filtering by status."""
        client = auth_client_with_scope(["[module]:read"])

        response = client.get(
            "/api/[module]/[resources]",
            params={"status": "active"}
        )

        assert response.status_code == 200


class TestGet[Resource]:
    """Tests for retrieving single [resource]."""

    def test_get_success(self, auth_client_with_scope):
        """Get [resource] by ID."""
        client = auth_client_with_scope(["[module]:read"])

        # First create one
        create_response = client.post(
            "/api/[module]/[resources]",
            json={"name": "Test"}
        )
        resource_id = create_response.json()["id"]

        # Then retrieve
        response = client.get(f"/api/[module]/[resources]/{resource_id}")

        assert response.status_code == 200
        assert response.json()["id"] == resource_id

    def test_get_not_found(self, auth_client_with_scope):
        """Return 404 for non-existent ID."""
        client = auth_client_with_scope(["[module]:read"])

        response = client.get("/api/[module]/[resources]/99999")

        assert response.status_code == 404


class TestUpdate[Resource]:
    """Tests for updating [resource]."""

    def test_update_success(self, auth_client_with_scope):
        """Update [resource] fields."""
        client = auth_client_with_scope(["[module]:write"])

        # Create
        create_resp = client.post(
            "/api/[module]/[resources]",
            json={"name": "Original"}
        )
        resource_id = create_resp.json()["id"]

        # Update
        response = client.patch(
            f"/api/[module]/[resources]/{resource_id}",
            json={"name": "Updated"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_partial_update(self, auth_client_with_scope):
        """Partial update only modifies specified fields."""
        client = auth_client_with_scope(["[module]:write"])

        # Create with multiple fields
        create_resp = client.post(
            "/api/[module]/[resources]",
            json={"name": "Test", "amount": "100.00"}
        )
        resource_id = create_resp.json()["id"]

        # Update only name
        response = client.patch(
            f"/api/[module]/[resources]/{resource_id}",
            json={"name": "New Name"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["amount"] == "100.00"  # Unchanged


class TestDelete[Resource]:
    """Tests for deleting [resource]."""

    def test_delete_success(self, auth_client_with_scope):
        """Delete [resource] returns 204."""
        client = auth_client_with_scope(["[module]:write"])

        # Create
        create_resp = client.post(
            "/api/[module]/[resources]",
            json={"name": "To Delete"}
        )
        resource_id = create_resp.json()["id"]

        # Delete
        response = client.delete(f"/api/[module]/[resources]/{resource_id}")

        assert response.status_code == 204

    def test_delete_not_found(self, auth_client_with_scope):
        """Delete non-existent returns 404."""
        client = auth_client_with_scope(["[module]:write"])

        response = client.delete("/api/[module]/[resources]/99999")

        assert response.status_code == 404
```

---

### E2E Test Template (Workflow)

```python
"""
E2E Tests: [Flow Name]

Tests the complete [business process] from [start] through [end].

Flow:
1. [Step 1]
2. [Step 2]
3. [Step 3]
...
"""
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json
from tests.e2e.fixtures.factories import (
    create_[entity1],
    create_[entity2],
)

# Apply module marker
pytestmark = pytest.mark.[module]


class Test[FlowName]Setup:
    """Test initial setup for [flow]."""

    def test_create_prerequisites(self, e2e_superuser_client, e2e_db):
        """Create required entities for the flow."""
        # Create prerequisite entities
        entity = create_[entity1](e2e_db, name="E2E Test Entity")

        assert entity.id is not None


class Test[FlowName]HappyPath:
    """Test the happy path for [flow]."""

    def test_step_1_[action](self, e2e_superuser_client, e2e_db):
        """[Description of step 1]."""
        # Setup
        entity = create_[entity1](e2e_db)

        # Action
        payload = {"entity_id": entity.id, "status": "submitted"}
        response = e2e_superuser_client.post("/api/[endpoint]", json=payload)

        # Assert
        assert_http_ok(response, "Step 1: [action]")
        data = get_json(response)
        assert data["status"] == "submitted"

    def test_step_2_[action](self, e2e_superuser_client, e2e_db):
        """[Description of step 2]."""
        # Setup - create entities in required state
        entity = create_[entity1](e2e_db, status="submitted")

        # Action
        response = e2e_superuser_client.post(
            f"/api/[endpoint]/{entity.id}/approve"
        )

        # Assert
        assert_http_ok(response, "Step 2: [action]")

        # Verify state change
        get_response = e2e_superuser_client.get(f"/api/[endpoint]/{entity.id}")
        assert get_json(get_response)["status"] == "approved"

    def test_step_3_[action](self, e2e_superuser_client, e2e_db):
        """[Description of step 3]."""
        # Complete flow and verify final state
        ...


class Test[FlowName]EdgeCases:
    """Test edge cases and error conditions for [flow]."""

    def test_cannot_skip_steps(self, e2e_superuser_client, e2e_db):
        """Cannot [final action] without [prerequisite]."""
        entity = create_[entity1](e2e_db, status="draft")  # Not submitted

        response = e2e_superuser_client.post(
            f"/api/[endpoint]/{entity.id}/complete"
        )

        assert_http_error(response, 400, "Cannot skip approval step")

    def test_duplicate_action_rejected(self, e2e_superuser_client, e2e_db):
        """Cannot [action] twice."""
        entity = create_[entity1](e2e_db, status="completed")

        response = e2e_superuser_client.post(
            f"/api/[endpoint]/{entity.id}/complete"
        )

        assert_http_error(response, 400, "Already completed")


class Test[FlowName]Rollback:
    """Test rollback and cancellation for [flow]."""

    def test_cancel_in_progress(self, e2e_superuser_client, e2e_db):
        """Can cancel [entity] before completion."""
        entity = create_[entity1](e2e_db, status="submitted")

        response = e2e_superuser_client.post(
            f"/api/[endpoint]/{entity.id}/cancel"
        )

        assert_http_ok(response, "Cancel in-progress")
        assert get_json(response)["status"] == "cancelled"

    def test_cannot_cancel_completed(self, e2e_superuser_client, e2e_db):
        """Cannot cancel after completion."""
        entity = create_[entity1](e2e_db, status="completed")

        response = e2e_superuser_client.post(
            f"/api/[endpoint]/{entity.id}/cancel"
        )

        assert_http_error(response, 400, "Cannot cancel completed")
```

---

### Factory Template

```python
def create_[entity](
    db: Session,
    name: str = None,
    status: str = "active",
    amount: Decimal = None,
    created_by_id: int = None,
    **kwargs
) -> "[Entity]":
    """
    Create a [entity] record for testing.

    Args:
        db: Database session
        name: Entity name (auto-generated if None)
        status: Initial status
        amount: Amount in decimal (auto-generated if None)
        created_by_id: Creator user ID
        **kwargs: Additional fields

    Returns:
        Created [Entity] instance
    """
    from app.models.[module] import [Entity]

    entity = [Entity](
        name=name or f"Test [Entity] {random_string(6)}",
        status=status,
        amount=amount or Decimal(str(random.randint(1000, 100000))),
        created_by_id=created_by_id,
        created_at=datetime.utcnow(),
        **kwargs
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def get_or_create_[shared_entity](
    db: Session,
    name: str = "Default [Entity]",
) -> "[SharedEntity]":
    """
    Get existing or create new [shared entity].

    Use for entities that should be reused across tests (e.g., currencies, types).
    """
    from app.models.[module] import [SharedEntity]

    entity = db.query([SharedEntity]).filter(
        [SharedEntity].name == name
    ).first()

    if entity:
        return entity

    entity = [SharedEntity](name=name)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
```

---

### Mock Session Template

```python
@dataclass
class MockSession:
    """
    Mock SQLAlchemy session for unit testing.

    Usage:
        mock_db = MockSession()
        mock_db.add_query_result([MockEntity(id=1)])
        service = MyService(mock_db)
        result = service.get_entity(1)
    """
    _query_results: List[Any] = field(default_factory=list)
    _added: List[Any] = field(default_factory=list)
    _committed: bool = False
    _rolled_back: bool = False

    def add_query_result(self, results: List[Any]):
        """Add results to be returned by next query."""
        self._query_results.extend(results)

    def query(self, model):
        """Mock query that returns configured results."""
        return MockQuery(self._query_results)

    def add(self, obj):
        """Track added objects."""
        self._added.append(obj)

    def commit(self):
        """Mark as committed."""
        self._committed = True

    def rollback(self):
        """Mark as rolled back."""
        self._rolled_back = True

    def refresh(self, obj):
        """No-op for mock."""
        pass


@dataclass
class MockQuery:
    """Mock query object."""
    _results: List[Any]

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._results[0] if self._results else None

    def all(self):
        return self._results

    def count(self):
        return len(self._results)

    def order_by(self, *args):
        return self

    def limit(self, n):
        return MockQuery(self._results[:n])

    def offset(self, n):
        return MockQuery(self._results[n:])
```

---

## Edge Case Test Patterns

### String Edge Cases

```python
@pytest.mark.parametrize("name", [
    "",                              # Empty
    " ",                             # Whitespace only
    "   trimmed   ",                 # Needs trimming
    "a",                             # Single char
    "a" * 255,                       # Max length
    "Test 🎉 Name",                  # Emoji
    "مرحبا",                         # Arabic (RTL)
    "<script>alert(1)</script>",     # XSS attempt
    "Robert'); DROP TABLE--",        # SQL injection attempt
])
def test_name_edge_cases(client, name):
    """Handle various name formats."""
    response = client.post("/api/resource", json={"name": name})
    # Assert based on expected behavior
```

### Numeric Edge Cases

```python
@pytest.mark.parametrize("amount,expected_status", [
    ("0", 200),                      # Zero
    ("0.01", 200),                   # Minimum
    ("999999999.99", 200),           # Large
    ("-100.00", 400),                # Negative (if not allowed)
    ("", 422),                       # Empty
    ("abc", 422),                    # Non-numeric
    ("1e10", 200),                   # Scientific notation
])
def test_amount_edge_cases(client, amount, expected_status):
    """Handle various amount values."""
    response = client.post("/api/resource", json={"amount": amount})
    assert response.status_code == expected_status
```

### Date Edge Cases

```python
@pytest.mark.parametrize("date_str,valid", [
    ("2024-01-01", True),            # Valid
    ("2024-02-29", True),            # Leap year
    ("2023-02-29", False),           # Not leap year
    ("2024-13-01", False),           # Invalid month
    ("2024-01-32", False),           # Invalid day
    ("2038-01-19", True),            # Y2K38 boundary
    ("1970-01-01", True),            # Unix epoch
    ("", False),                     # Empty
])
def test_date_edge_cases(client, date_str, valid):
    """Handle various date formats."""
    response = client.post("/api/resource", json={"date": date_str})
    if valid:
        assert response.status_code == 200
    else:
        assert response.status_code in [400, 422]
```

---

## RBAC Test Patterns

```python
class TestResourceRBAC:
    """RBAC tests for resource endpoints."""

    @pytest.mark.parametrize("scopes,expected_status", [
        (["resource:read"], 200),           # Has read scope
        (["resource:write"], 200),          # Write implies read
        (["other:read"], 403),              # Wrong scope
        ([], 403),                          # No scopes
    ])
    def test_list_requires_read_scope(
        self, auth_client_with_scope, scopes, expected_status
    ):
        """List requires read scope."""
        client = auth_client_with_scope(scopes)
        response = client.get("/api/resource")
        assert response.status_code == expected_status

    def test_superuser_bypasses_scope_check(self, auth_client_with_scope):
        """Superuser can access without specific scope."""
        client = auth_client_with_scope([], is_superuser=True)
        response = client.get("/api/resource")
        assert response.status_code == 200

    def test_service_token_access(self, service_token_client):
        """Service tokens work with appropriate scopes."""
        client = service_token_client(["resource:read"])
        response = client.get("/api/resource")
        assert response.status_code == 200
```

---

## Concurrency Test Patterns

```python
import concurrent.futures
import threading


class TestConcurrency:
    """Concurrency tests for race conditions."""

    def test_no_double_spend(self, auth_client_with_scope, e2e_db):
        """Concurrent updates don't cause double-spending."""
        # Create resource with limited quantity
        resource = create_resource(e2e_db, quantity=1)

        results = []
        errors = []

        def attempt_claim():
            try:
                client = auth_client_with_scope(["resource:write"])
                response = client.post(
                    f"/api/resource/{resource.id}/claim"
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(e)

        # Run concurrent claims
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_claim) for _ in range(5)]
            concurrent.futures.wait(futures)

        # Only one should succeed
        assert results.count(200) == 1
        assert results.count(400) == 4  # Others fail

    def test_optimistic_locking(self, auth_client_with_scope, e2e_db):
        """Concurrent updates with stale version fail."""
        resource = create_resource(e2e_db)

        # Get current version
        client = auth_client_with_scope(["resource:write"])
        response1 = client.get(f"/api/resource/{resource.id}")
        version1 = response1.json()["version"]

        # Update (increments version)
        client.patch(
            f"/api/resource/{resource.id}",
            json={"name": "Updated", "version": version1}
        )

        # Try update with stale version
        response = client.patch(
            f"/api/resource/{resource.id}",
            json={"name": "Stale Update", "version": version1}
        )

        assert response.status_code == 409  # Conflict
```

---

## Performance Test Patterns

```python
import time


class TestPerformance:
    """Performance tests."""

    @pytest.mark.slow
    def test_list_performance(self, auth_client_with_scope, e2e_db):
        """List endpoint responds within acceptable time."""
        # Create many records
        for i in range(100):
            create_resource(e2e_db, name=f"Resource {i}")

        client = auth_client_with_scope(["resource:read"])

        start = time.time()
        response = client.get("/api/resource", params={"limit": 50})
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0  # Under 1 second

    @pytest.mark.slow
    def test_no_n_plus_one(self, auth_client_with_scope, e2e_db, caplog):
        """Verify no N+1 query problems."""
        import logging

        # Enable SQL logging
        logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

        # Create records with relationships
        for i in range(10):
            parent = create_parent(e2e_db)
            for j in range(5):
                create_child(e2e_db, parent_id=parent.id)

        client = auth_client_with_scope(["resource:read"])

        with caplog.at_level(logging.DEBUG, logger="sqlalchemy.engine"):
            response = client.get("/api/parents?include=children")

        # Count SELECT statements
        select_count = sum(
            1 for record in caplog.records
            if "SELECT" in record.message
        )

        # Should be O(1), not O(N)
        assert select_count < 5  # Not 10+ queries
```
