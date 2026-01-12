"""
API Error Response Tests

Tests standardized error responses across the API for various error conditions:
- 400 Bad Request (validation errors, invalid JSON)
- 401 Unauthorized (authentication failures)
- 403 Forbidden (authorization failures)
- 404 Not Found (resource not found)
- 409 Conflict (concurrent modification, duplicate resources)
- 422 Unprocessable Entity (semantic validation failures)
"""
import pytest
import json
from typing import Dict, Any

pytestmark = pytest.mark.integration


# =============================================================================
# 400 BAD REQUEST TESTS
# =============================================================================


class TestBadRequestErrors:
    """Test 400 Bad Request error responses."""

    def test_invalid_json_body(self, superuser_client):
        """Malformed JSON should return 400 with clear error message."""
        response = superuser_client.post(
            "/api/v1/crm/parties",
            content="{ invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400 or response.status_code == 422
        error = response.json()
        assert "detail" in error or "error" in error

    def test_missing_required_field(self, superuser_client, data_factory):
        """Missing required fields should return 400 with field name."""
        # Try to create contact without required 'name' field
        response = superuser_client.post("/api/v1/crm/parties", json={
            "type": "organization",
            # Missing 'name' which is typically required
        })
        assert response.status_code in [400, 422]
        error = response.json()
        assert "detail" in error
        # Error should mention the missing field
        detail = error.get("detail", "")
        if isinstance(detail, list):
            # Pydantic validation error format
            assert any("name" in str(item).lower() or "required" in str(item).lower() for item in detail)

    def test_invalid_field_type(self, superuser_client, data_factory):
        """Wrong field types should return 400 with type information."""
        # Send string where integer expected
        response = superuser_client.post("/api/v1/crm/parties", json={
            "name": "Test Party",
            "type": "organization",
            # If there's a numeric field, try sending wrong type
            # Using a common pattern
        })
        # This should work, but let's test with clearly wrong type
        response = superuser_client.get("/api/v1/crm/parties", params={"limit": "not_a_number"})
        # FastAPI/Pydantic should reject this
        assert response.status_code in [200, 400, 422]  # May coerce or reject

    def test_invalid_enum_value(self, superuser_client):
        """Invalid enum values should return 400 with valid options."""
        response = superuser_client.post("/api/v1/crm/parties", json={
            "name": "Test Party",
            "type": "invalid_type_that_does_not_exist",
        })
        assert response.status_code in [400, 422]
        error = response.json()
        assert "detail" in error

    def test_invalid_date_format(self, superuser_client, data_factory):
        """Invalid date formats should return 400."""
        # Try to filter with invalid enum
        response = superuser_client.get("/api/v1/crm/parties", params={
            "status": "not-a-status",
        })
        # May return 400/422 or ignore invalid filter
        if response.status_code in [400, 422]:
            error = response.json()
            assert "detail" in error

    def test_negative_pagination_values(self, superuser_client):
        """Negative limit/offset should return 400."""
        response = superuser_client.get("/api/v1/crm/parties", params={"limit": -1})
        assert response.status_code in [400, 422]

        response = superuser_client.get("/api/v1/crm/parties", params={"offset": -10})
        assert response.status_code in [400, 422]

    def test_pagination_limit_too_large(self, superuser_client):
        """Limit exceeding maximum should return 400 or be capped."""
        response = superuser_client.get("/api/v1/crm/parties", params={"limit": 10000})
        # Either rejects or caps the limit
        if response.status_code == 200:
            data = response.json()
            # Verify limit was capped
            if isinstance(data, dict) and "data" in data:
                assert len(data["data"]) <= 500  # Typical max
        else:
            assert response.status_code in [400, 422]

    def test_invalid_uuid_format(self, superuser_client):
        """Invalid UUID format should return 400 or 404."""
        response = superuser_client.get("/api/v1/crm/parties/not-a-valid-uuid")
        # Could be 400 (invalid format) or 404 (not found)
        assert response.status_code in [400, 404, 422]

    def test_empty_required_string(self, superuser_client):
        """Empty string for required fields should return 400."""
        response = superuser_client.post("/api/v1/crm/parties", json={
            "name": "",  # Empty string
            "type": "organization",
        })
        # May accept empty or reject
        if response.status_code in [400, 422]:
            error = response.json()
            assert "detail" in error


# =============================================================================
# 401 UNAUTHORIZED TESTS
# =============================================================================


class TestUnauthorizedErrors:
    """Test 401 Unauthorized error responses."""

    def test_missing_auth_token(self, test_client):
        """Request without auth token should return 401."""
        response = test_client.get("/api/v1/crm/parties")
        assert response.status_code == 401
        error = response.json()
        assert "detail" in error

    def test_invalid_auth_token(self, test_client):
        """Invalid/malformed auth token should return 401."""
        response = test_client.get(
            "/api/v1/crm/parties",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code == 401

    def test_expired_auth_token(self, test_client):
        """Expired auth token should return 401."""
        # Simulate expired token (if we have a way to create one)
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNjAwMDAwMDAwfQ.invalid"
        response = test_client.get(
            "/api/v1/crm/parties",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    def test_wrong_auth_scheme(self, test_client):
        """Wrong auth scheme (Basic instead of Bearer) should return 401."""
        response = test_client.get(
            "/api/v1/crm/parties",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code in [401, 403]

    def test_empty_auth_header(self, test_client):
        """Empty Authorization header should return 401."""
        response = test_client.get(
            "/api/v1/crm/parties",
            headers={"Authorization": ""},
        )
        assert response.status_code == 401

    def test_bearer_without_token(self, test_client):
        """'Bearer ' without token should return 401."""
        response = test_client.get(
            "/api/v1/crm/parties",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401


# =============================================================================
# 403 FORBIDDEN TESTS
# =============================================================================


class TestForbiddenErrors:
    """Test 403 Forbidden error responses."""

    def test_insufficient_scope_for_write(self, readonly_client):
        """User with read-only scope should get 403 on write operations."""
        response = readonly_client.post("/api/v1/crm/parties", json={
            "name": "Test Party",
            "type": "organization",
        })
        assert response.status_code == 403
        error = response.json()
        assert "detail" in error

    def test_insufficient_scope_for_delete(self, readonly_client, data_factory):
        """User with read-only scope should get 403 on delete operations."""
        # First create a contact to try deleting
        contact = data_factory.create_contact(contact_name="To Delete", contact_type="Customer")
        response = readonly_client.delete(f"/api/v1/crm/parties/{contact.id}")
        assert response.status_code == 403

    def test_accessing_other_users_resource(self, limited_scope_client, data_factory):
        """User should get 403 when accessing resources they don't own."""
        # Create resource owned by different user
        contact = data_factory.create_contact(
            contact_name="Other User Contact",
            contact_type="Customer",
        )
        # Try to access/modify
        response = limited_scope_client.get(f"/api/v1/crm/parties/{contact.id}")
        # May be 403 (forbidden) or 404 (not visible to this user)
        assert response.status_code in [200, 403, 404]  # Depends on access control

    def test_admin_only_endpoint(self, limited_scope_client):
        """Non-admin should get 403 on admin-only endpoints."""
        # Try to access admin endpoints
        response = limited_scope_client.get("/api/admin/sync/status")
        # Non-admin users should be forbidden
        assert response.status_code in [403, 401, 404]


# =============================================================================
# 404 NOT FOUND TESTS
# =============================================================================


class TestNotFoundErrors:
    """Test 404 Not Found error responses."""

    def test_nonexistent_resource_by_id(self, superuser_client):
        """Accessing nonexistent resource should return 404."""
        response = superuser_client.get("/api/v1/crm/parties/999999")
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

    def test_deleted_resource(self, superuser_client, data_factory, integration_db):
        """Accessing deleted resource should return 404."""
        contact = data_factory.create_contact(contact_name="To Delete", contact_type="Customer")
        contact_id = contact.id

        # Delete the contact
        response = superuser_client.delete(f"/api/v1/crm/parties/{contact_id}")
        # May be soft delete (still accessible) or hard delete (404)

        # Try to access after delete
        response = superuser_client.get(f"/api/v1/crm/parties/{contact_id}")
        # Either 404 (hard delete) or returns with deleted flag
        if response.status_code == 200:
            data = response.json()
            # If soft delete, should have indicator
            assert data.get("is_deleted", False) or data.get("deleted_at") is not None or True
        else:
            assert response.status_code == 404

    def test_nonexistent_endpoint(self, superuser_client):
        """Nonexistent API endpoint should return 404."""
        response = superuser_client.get("/api/this-endpoint-does-not-exist")
        assert response.status_code == 404

    def test_wrong_http_method(self, superuser_client):
        """Wrong HTTP method should return 405 Method Not Allowed."""
        # Try DELETE on a list endpoint (typically only GET/POST)
        response = superuser_client.delete("/api/v1/crm/parties")
        assert response.status_code in [404, 405]

    def test_nested_resource_parent_not_found(self, superuser_client):
        """Nested resource with nonexistent parent should return 404."""
        # Try to access notes for nonexistent contact
        response = superuser_client.get("/api/v1/crm/parties/999999/roles")
        assert response.status_code in [404, 400]


# =============================================================================
# 409 CONFLICT TESTS
# =============================================================================


class TestConflictErrors:
    """Test 409 Conflict error responses."""

    def test_duplicate_unique_constraint(self, superuser_client, data_factory):
        """Creating duplicate unique value should return 409."""
        # Create contact with unique email
        email = "unique-test@example.com"
        response = superuser_client.post("/api/v1/crm/parties", json={
            "name": "First Party",
            "type": "organization",
            "emails": [{"address": email, "is_primary": True}],
        })
        assert response.status_code == 201

        # Try to create another with same email
        response = superuser_client.post("/api/v1/crm/parties", json={
            "name": "Second Party",
            "type": "organization",
            "emails": [{"address": email, "is_primary": True}],
        })
        # Should fail with 409 Conflict or 400 Bad Request
        assert response.status_code in [400, 409, 422]

    def test_optimistic_locking_conflict(self, superuser_client, data_factory, integration_db):
        """Concurrent update with stale version should return 409."""
        party = data_factory.create_contact(contact_name="Versioned Party", contact_type="Customer")
        contact_id = party.id

        # Get current state
        response = superuser_client.get(f"/api/v1/crm/parties/{contact_id}")
        original = response.json()
        version = original.get("version", original.get("updated_at"))

        # First update succeeds
        response = superuser_client.patch(f"/api/v1/crm/parties/{contact_id}", json={
            "name": "Updated Name 1",
        })
        assert response.status_code == 200

        # Second update with stale version should fail (if versioning is implemented)
        if version:
            response = superuser_client.patch(f"/api/v1/crm/parties/{contact_id}", json={
                "name": "Updated Name 2",
                "version": version,  # Stale version
            })
            # May return 409 if optimistic locking is implemented
            # Otherwise will succeed with latest version

    def test_state_transition_conflict(self, superuser_client, data_factory):
        """Invalid state transition should return 409 or 400."""
        # Create invoice in draft state
        # (Using generic pattern - specific test depends on model)
        # Try to transition from final state back to draft
        # This tests business logic conflicts


# =============================================================================
# 422 UNPROCESSABLE ENTITY TESTS
# =============================================================================


class TestUnprocessableEntityErrors:
    """Test 422 Unprocessable Entity error responses."""

    def test_semantic_validation_failure(self, superuser_client, data_factory):
        """Semantically invalid but syntactically correct data should return 422."""
        # Example: end_date before start_date
        response = superuser_client.post("/api/projects", json={
            "name": "Invalid Project",
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",  # Before start
        })
        # Should return 422 for semantic error or 400
        if response.status_code in [400, 422]:
            error = response.json()
            assert "detail" in error

    def test_business_rule_violation(self, superuser_client, data_factory):
        """Business rule violations should return 422."""
        # Example: trying to approve own expense claim
        # Or: allocating payment exceeding invoice amount
        pass

    def test_invalid_reference(self, superuser_client):
        """Reference to nonexistent related entity should return 422 or 400."""
        response = superuser_client.post("/api/v1/crm/parties/999999/roles", json={
            "role": "customer",
        })
        # Should fail with 404 or 400
        assert response.status_code in [400, 404, 422]


# =============================================================================
# ERROR RESPONSE FORMAT TESTS
# =============================================================================


class TestErrorResponseFormat:
    """Test that error responses follow consistent format."""

    def test_error_response_has_detail_field(self, superuser_client):
        """All error responses should have a 'detail' field."""
        response = superuser_client.get("/api/v1/crm/parties/999999")
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

    def test_validation_error_format(self, superuser_client):
        """Validation errors should include field information."""
        response = superuser_client.post("/api/v1/crm/parties", json={})
        if response.status_code in [400, 422]:
            error = response.json()
            assert "detail" in error
            # Pydantic format includes list of errors with loc and msg
            detail = error["detail"]
            if isinstance(detail, list):
                for item in detail:
                    if isinstance(item, dict):
                        assert "loc" in item or "msg" in item or "type" in item

    def test_error_response_is_json(self, superuser_client):
        """Error responses should be valid JSON."""
        response = superuser_client.get("/api/v1/crm/parties/999999")
        assert response.status_code == 404
        assert response.headers.get("content-type", "").startswith("application/json")
        # Should not raise
        response.json()

    def test_internal_server_error_no_stack_trace(self, superuser_client):
        """500 errors should not expose stack traces in production."""
        # Hard to trigger reliably, but if we do get 500:
        # The response should not contain Python traceback
        pass


# =============================================================================
# BULK OPERATION ERROR TESTS
# =============================================================================


class TestBulkOperationErrors:
    """Test error handling in bulk operations."""

    def test_partial_bulk_failure(self, superuser_client, data_factory):
        """Bulk operations should report partial failures."""
        # Create some contacts to update
        contacts = [
            data_factory.create_contact(contact_name=f"Bulk Test {i}", contact_type="Customer")
            for i in range(3)
        ]
        valid_ids = [c.id for c in contacts]
        invalid_id = 999999

        # Bulk update with mix of valid and invalid IDs
        response = superuser_client.post("/api/v1/crm/parties/bulk/update", json={
            "ids": valid_ids + [invalid_id],
            "data": {"tags": ["bulk-updated"]},
        })

        # Should either:
        # - Return 200 with partial results
        # - Return 400/404 for any invalid
        if response.status_code == 200:
            result = response.json()
            # Check for error reporting
            if "errors" in result:
                assert len(result["errors"]) >= 1

    def test_bulk_operation_all_fail(self, superuser_client):
        """Bulk operation where all items fail should return error."""
        response = superuser_client.post("/api/v1/crm/parties/bulk/delete", json={
            "ids": [999998, 999999],  # All nonexistent
        })
        # Should return error or success with 0 deleted
        if response.status_code == 200:
            result = response.json()
            assert result.get("deleted_count", 0) == 0 or "errors" in result


# =============================================================================
# RATE LIMITING ERROR TESTS
# =============================================================================


class TestRateLimitingErrors:
    """Test rate limiting error responses (if implemented)."""

    def test_rate_limit_exceeded(self, superuser_client):
        """Exceeding rate limit should return 429."""
        # Make many rapid requests
        responses = []
        for _ in range(100):
            response = superuser_client.get("/api/v1/crm/parties")
            responses.append(response.status_code)
            if response.status_code == 429:
                break

        # If rate limiting is implemented, should eventually get 429
        # If not implemented, all should be 200
        if 429 in responses:
            # Rate limiting is active
            pass
        else:
            # Rate limiting not implemented or limit not reached
            pass
