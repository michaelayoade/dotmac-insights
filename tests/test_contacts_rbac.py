"""
Contacts RBAC Tests

Tests for Role-Based Access Control on the Contacts API.
Verifies that:
- Users with correct scopes can access endpoints
- Users without correct scopes get 403
- Unauthenticated requests get 401
- Service tokens respect scopes
"""
import pytest
from fastapi import HTTPException


# =============================================================================
# POSITIVE TESTS - Users WITH correct scopes
# =============================================================================


def test_user_with_contacts_read_can_list(auth_client_with_scope):
    """GET /api/contacts → 200 when user has contacts:read scope."""
    client = auth_client_with_scope(["contacts:read"])
    response = client.get("/api/contacts")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    # Verify response structure
    data = response.json()
    assert "items" in data or "total" in data, "Response should have items or total"


def test_user_with_contacts_read_can_get_single(auth_client_with_scope):
    """GET /api/contacts/{id} → 404 (not 403) when user has contacts:read scope."""
    client = auth_client_with_scope(["contacts:read"])
    # Use a non-existent ID - we expect 404 (not found), not 403 (forbidden)
    response = client.get("/api/contacts/999999")
    assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"


def test_user_with_contacts_write_can_create(auth_client_with_scope):
    """POST /api/contacts → 201 when user has contacts:write scope."""
    client = auth_client_with_scope(["contacts:read", "contacts:write"])
    contact_data = {
        "name": "Test RBAC Contact",
        "email": "rbac-test@example.com",
        "contact_type": "lead",
        "category": "residential",
        "status": "active",
    }
    response = client.post("/api/contacts", json=contact_data)
    # 201 for success, 422 for validation error (both indicate auth passed)
    assert response.status_code in [201, 422], f"Expected 201 or 422, got {response.status_code}: {response.text}"


def test_user_with_contacts_write_can_update(auth_client_with_scope):
    """PATCH /api/contacts/{id} → 404 (not 403) when user has contacts:write scope."""
    client = auth_client_with_scope(["contacts:read", "contacts:write"])
    update_data = {"name": "Updated Name"}
    # Use a non-existent ID - we expect 404 (not found), not 403 (forbidden)
    response = client.patch("/api/contacts/999999", json=update_data)
    assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"


def test_user_with_contacts_write_can_delete(auth_client_with_scope):
    """DELETE /api/contacts/{id} → 404 (not 403) when user has contacts:write scope."""
    client = auth_client_with_scope(["contacts:read", "contacts:write"])
    # Use a non-existent ID - we expect 404 (not found), not 403 (forbidden)
    response = client.delete("/api/contacts/999999")
    assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"


# =============================================================================
# NEGATIVE TESTS - Users WITHOUT correct scopes
# =============================================================================


def test_user_without_contacts_read_gets_403(auth_client_with_scope):
    """GET /api/contacts → 403 when user lacks contacts:read scope."""
    client = auth_client_with_scope(["billing:read"])  # Different scope
    response = client.get("/api/contacts")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    # Verify error message mentions permission
    data = response.json()
    assert "permission" in data.get("detail", "").lower() or "denied" in data.get("detail", "").lower()


def test_user_without_contacts_write_gets_403_on_post(auth_client_with_scope):
    """POST /api/contacts → 403 when user lacks contacts:write scope."""
    client = auth_client_with_scope(["contacts:read"])  # Read-only
    contact_data = {
        "name": "Test Contact",
        "email": "test@example.com",
        "contact_type": "lead",
        "category": "residential",
        "status": "active",
    }
    response = client.post("/api/contacts", json=contact_data)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


def test_user_without_contacts_write_gets_403_on_patch(auth_client_with_scope):
    """PATCH /api/contacts/{id} → 403 when user lacks contacts:write scope."""
    client = auth_client_with_scope(["contacts:read"])  # Read-only
    response = client.patch("/api/contacts/1", json={"name": "Updated"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


def test_user_without_contacts_write_gets_403_on_delete(auth_client_with_scope):
    """DELETE /api/contacts/{id} → 403 when user lacks contacts:write scope."""
    client = auth_client_with_scope(["contacts:read"])  # Read-only
    response = client.delete("/api/contacts/1")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


# =============================================================================
# AUTHENTICATION TESTS - Invalid/missing tokens
# =============================================================================


def test_unauthenticated_request_gets_401(unauthenticated_client):
    """GET /api/contacts → 401 when no auth token provided."""
    response = unauthenticated_client.get("/api/contacts")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


def test_unauthenticated_post_gets_401(unauthenticated_client):
    """POST /api/contacts → 401 when no auth token provided."""
    contact_data = {"name": "Test", "email": "test@example.com"}
    response = unauthenticated_client.post("/api/contacts", json=contact_data)
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


# =============================================================================
# SERVICE TOKEN TESTS
# =============================================================================


def test_service_token_with_scope_can_read(service_token_client):
    """Service token with contacts:read scope can list contacts."""
    client = service_token_client(["contacts:read"])
    response = client.get("/api/contacts")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


def test_service_token_without_scope_gets_403(service_token_client):
    """Service token without contacts:read scope gets 403."""
    client = service_token_client(["sync:splynx:read"])  # Different scope
    response = client.get("/api/contacts")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


def test_service_token_without_write_scope_gets_403_on_post(service_token_client):
    """Service token without contacts:write scope gets 403 on POST."""
    client = service_token_client(["contacts:read"])  # Read-only
    contact_data = {
        "name": "Test Contact",
        "email": "test@example.com",
        "contact_type": "lead",
        "category": "residential",
        "status": "active",
    }
    response = client.post("/api/contacts", json=contact_data)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


# =============================================================================
# SUPERUSER TESTS
# =============================================================================


def test_superuser_bypasses_scope_checks(superuser_client):
    """Superuser can access contacts without explicit contacts:read scope."""
    response = superuser_client.get("/api/contacts")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


def test_superuser_can_write_without_explicit_scope(superuser_client):
    """Superuser can create contacts without explicit contacts:write scope."""
    contact_data = {
        "name": "Superuser Test Contact",
        "email": "superuser-test@example.com",
        "contact_type": "lead",
        "category": "residential",
        "status": "active",
    }
    response = superuser_client.post("/api/contacts", json=contact_data)
    # 201 for success, 422 for validation error (both indicate auth passed)
    assert response.status_code in [201, 422], f"Expected 201 or 422, got {response.status_code}: {response.text}"
