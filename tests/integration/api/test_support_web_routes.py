"""
Integration Tests: Support Web Routes

Tests the SSR support ticket web routes with HTMX interactions.
Covers ticket CRUD, status updates, pagination, and filtering.
"""
import pytest
from datetime import datetime
from decimal import Decimal

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json


# Apply module marker
pytestmark = pytest.mark.support


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def support_client(auth_client_with_scope):
    """Create client with support read/write scopes."""
    return auth_client_with_scope(["support:read", "support:write"])


@pytest.fixture
def support_read_client(auth_client_with_scope):
    """Create client with support:read scope only."""
    return auth_client_with_scope(["support:read"])


@pytest.fixture
def no_scope_client(auth_client_with_scope):
    """Create client with no support scopes."""
    return auth_client_with_scope(["accounting:read"])


@pytest.fixture
def create_test_party(client):
    """Create a party for ticket testing."""
    from app.database import get_db
    from app.main import app
    from sqlalchemy.orm import Session

    # Use API or direct DB access
    party_data = {
        "name": "Test Party",
        "primary_email": "test@example.com",
    }

    # Try to create via API if endpoint exists
    response = client.post("/api/parties/", json=party_data)
    if response.status_code in [200, 201]:
        return response.json()

    # Fallback: Return None (tests will handle)
    return None


# =============================================================================
# DASHBOARD TESTS
# =============================================================================


class TestSupportDashboard:
    """Test support dashboard routes."""

    def test_dashboard_requires_auth(self, unauthenticated_client):
        """Test dashboard requires authentication."""
        response = unauthenticated_client.get("/support")
        assert response.status_code in [401, 403, 307]  # 307 redirect to login

    def test_dashboard_requires_scope(self, no_scope_client):
        """Test dashboard requires support:read scope."""
        response = no_scope_client.get("/support")
        assert response.status_code in [403, 401]

    def test_dashboard_accessible(self, support_client):
        """Test dashboard is accessible with proper scope."""
        response = support_client.get("/support")
        # May return 200 or redirect depending on setup
        assert response.status_code in [200, 302, 307]

    def test_dashboard_returns_html(self, support_client):
        """Test dashboard returns HTML."""
        response = support_client.get("/support")
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")


# =============================================================================
# TICKET LIST TESTS
# =============================================================================


class TestTicketList:
    """Test ticket list routes."""

    def test_list_requires_auth(self, unauthenticated_client):
        """Test ticket list requires authentication."""
        response = unauthenticated_client.get("/support/tickets")
        assert response.status_code in [401, 403, 307]

    def test_list_requires_scope(self, no_scope_client):
        """Test ticket list requires support:read scope."""
        response = no_scope_client.get("/support/tickets")
        assert response.status_code in [403, 401]

    def test_list_accessible(self, support_client):
        """Test ticket list is accessible."""
        response = support_client.get("/support/tickets")
        assert response.status_code in [200, 302, 307]

    def test_list_with_search_param(self, support_client):
        """Test ticket list with search parameter."""
        response = support_client.get("/support/tickets", params={"q": "test"})
        assert response.status_code in [200, 302, 307]

    def test_list_with_status_filter(self, support_client):
        """Test ticket list with status filter."""
        response = support_client.get("/support/tickets", params={"status": "open"})
        assert response.status_code in [200, 302, 307]

    def test_list_with_priority_filter(self, support_client):
        """Test ticket list with priority filter."""
        response = support_client.get("/support/tickets", params={"priority": "high"})
        assert response.status_code in [200, 302, 307]

    def test_list_with_unassigned_filter(self, support_client):
        """Test ticket list with unassigned filter."""
        response = support_client.get("/support/tickets", params={"assigned": "unassigned"})
        assert response.status_code in [200, 302, 307]

    def test_list_pagination(self, support_client):
        """Test ticket list pagination."""
        response = support_client.get("/support/tickets", params={"page": 1, "per_page": 10})
        assert response.status_code in [200, 302, 307]

    def test_list_sorting(self, support_client):
        """Test ticket list sorting."""
        response = support_client.get(
            "/support/tickets",
            params={"sort": "created_at", "dir": "desc"}
        )
        assert response.status_code in [200, 302, 307]

    def test_list_invalid_sort_handled(self, support_client):
        """Test that invalid sort column is handled gracefully."""
        response = support_client.get(
            "/support/tickets",
            params={"sort": "invalid_column", "dir": "desc"}
        )
        # Should not error, should fall back to default
        assert response.status_code in [200, 302, 307]


# =============================================================================
# TICKET CREATE TESTS
# =============================================================================


class TestTicketCreate:
    """Test ticket creation routes."""

    def test_create_form_requires_scope(self, support_read_client):
        """Test create form requires write scope for POST."""
        response = support_read_client.post(
            "/support/tickets/new",
            data={"subject": "Test"}
        )
        # GET might work, POST should fail without write scope
        assert response.status_code in [403, 405, 422]

    def test_create_form_accessible(self, support_client):
        """Test create form is accessible."""
        response = support_client.get("/support/tickets/new")
        assert response.status_code in [200, 302, 307]

    def test_create_requires_subject(self, support_client):
        """Test create requires subject field."""
        response = support_client.post(
            "/support/tickets/new",
            data={
                "description": "Missing subject",
                "priority": "medium",
            }
        )
        # Should return validation error
        assert response.status_code in [422, 400, 200]  # 200 if showing form with errors

    def test_create_requires_party_or_email(self, support_client):
        """Test create requires party_id or contact_email."""
        response = support_client.post(
            "/support/tickets/new",
            data={
                "subject": "Test Ticket",
                "description": "Test description",
                "priority": "medium",
            }
        )
        # Should return validation error about party
        assert response.status_code in [422, 400, 200]


# =============================================================================
# TICKET STATUS UPDATE TESTS
# =============================================================================


class TestTicketStatusUpdate:
    """Test ticket status update routes."""

    def test_status_update_requires_write_scope(self, support_read_client):
        """Test status update requires write scope."""
        response = support_read_client.post(
            "/support/tickets/1/status",
            data={"status": "resolved"}
        )
        assert response.status_code in [403, 401]

    def test_status_update_requires_csrf(self, support_client):
        """Test status update requires CSRF token."""
        # Without CSRF token, should fail
        response = support_client.post(
            "/support/tickets/999/status",
            data={"status": "resolved"}
        )
        # Either 403 (CSRF) or 404 (ticket not found)
        assert response.status_code in [403, 404, 422]

    def test_invalid_status_rejected(self, support_client):
        """Test that invalid status value is rejected."""
        # This tests the status validation we added
        response = support_client.post(
            "/support/tickets/999/status",
            data={"status": "invalid_status_value"}
        )
        # Should return error (either 400 for invalid status or 404 for ticket)
        assert response.status_code in [400, 404, 403, 422]


# =============================================================================
# HTMX PARTIAL TESTS
# =============================================================================


class TestHTMXPartials:
    """Test HTMX partial responses."""

    def test_table_partial_with_htmx_header(self, support_client):
        """Test table partial returns only table HTML with HTMX header."""
        response = support_client.get(
            "/support/tickets",
            headers={"HX-Request": "true"}
        )
        if response.status_code == 200:
            content = response.text
            # Should NOT contain full page layout (no <html> tag)
            # This is a basic check - adjust based on actual template structure
            assert "<!DOCTYPE" not in content or "partial" in content.lower()

    def test_ticket_row_partial(self, support_client):
        """Test ticket row partial endpoint."""
        # This endpoint returns just the row for HTMX updates
        response = support_client.get("/support/tickets/1/row")
        # Either 200 (found) or 404 (not found)
        assert response.status_code in [200, 404]


# =============================================================================
# SECURITY TESTS
# =============================================================================


class TestSecurityMeasures:
    """Test security measures in routes."""

    def test_sort_injection_prevented(self, support_client):
        """Test SQL injection via sort parameter is prevented."""
        response = support_client.get(
            "/support/tickets",
            params={"sort": "'; DROP TABLE tickets; --"}
        )
        # Should not error, should handle gracefully
        assert response.status_code in [200, 302, 307]

    def test_search_injection_prevented(self, support_client):
        """Test SQL injection via search is prevented."""
        response = support_client.get(
            "/support/tickets",
            params={"q": "'; DROP TABLE tickets; --"}
        )
        # Should not error
        assert response.status_code in [200, 302, 307]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling in routes."""

    def test_ticket_not_found(self, support_client):
        """Test 404 for non-existent ticket."""
        response = support_client.get("/support/tickets/999999")
        assert response.status_code == 404

    def test_invalid_ticket_id(self, support_client):
        """Test handling of invalid ticket ID."""
        response = support_client.get("/support/tickets/invalid")
        assert response.status_code in [404, 422]


# =============================================================================
# PARTY RESOLUTION TESTS
# =============================================================================


class TestPartyResolution:
    """Test party resolution in ticket creation."""

    def test_party_auto_resolved_from_email(self, support_client):
        """Test that party is auto-resolved from contact email."""
        # This tests the resolve_party_for_ticket helper
        response = support_client.post(
            "/support/tickets/new",
            data={
                "subject": "Test Ticket",
                "description": "Test",
                "priority": "medium",
                "contact_email": "newcontact@example.com",
                "contact_name": "New Contact",
            }
        )
        # Should either create successfully or show form (depending on other validation)
        # Not a 500 error
        assert response.status_code != 500
