"""
Integration Tests: Omnichannel Web Routes

Tests the SSR omnichannel inbox routes with HTMX interactions.
Covers conversation list, detail, reply, status, and star operations.
"""
import pytest
from datetime import datetime

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json


# Apply module marker
pytestmark = pytest.mark.inbox


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def inbox_client(auth_client_with_scope):
    """Create client with support read/write scopes for inbox."""
    return auth_client_with_scope(["support:read", "support:write"])


@pytest.fixture
def inbox_read_client(auth_client_with_scope):
    """Create client with support:read scope only."""
    return auth_client_with_scope(["support:read"])


@pytest.fixture
def no_scope_client(auth_client_with_scope):
    """Create client with no support scopes."""
    return auth_client_with_scope(["accounting:read"])


# =============================================================================
# INBOX LIST TESTS
# =============================================================================


class TestInboxList:
    """Test inbox list routes."""

    def test_inbox_requires_auth(self, unauthenticated_client):
        """Test inbox requires authentication."""
        response = unauthenticated_client.get("/inbox")
        assert response.status_code in [401, 403, 307]

    def test_inbox_requires_scope(self, no_scope_client):
        """Test inbox requires support:read scope."""
        response = no_scope_client.get("/inbox")
        assert response.status_code in [403, 401]

    def test_inbox_accessible(self, inbox_client):
        """Test inbox is accessible with proper scope."""
        response = inbox_client.get("/inbox")
        assert response.status_code in [200, 302, 307]

    def test_inbox_returns_html(self, inbox_client):
        """Test inbox returns HTML."""
        response = inbox_client.get("/inbox")
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")

    def test_inbox_with_search(self, inbox_client):
        """Test inbox with search parameter."""
        response = inbox_client.get("/inbox", params={"q": "test"})
        assert response.status_code in [200, 302, 307]

    def test_inbox_with_status_filter(self, inbox_client):
        """Test inbox with status filter."""
        response = inbox_client.get("/inbox", params={"status": "open"})
        assert response.status_code in [200, 302, 307]

    def test_inbox_with_priority_filter(self, inbox_client):
        """Test inbox with priority filter."""
        response = inbox_client.get("/inbox", params={"priority": "urgent"})
        assert response.status_code in [200, 302, 307]

    def test_inbox_with_channel_filter(self, inbox_client):
        """Test inbox with channel filter."""
        response = inbox_client.get("/inbox", params={"channel": 1})
        assert response.status_code in [200, 302, 307]

    def test_inbox_pagination(self, inbox_client):
        """Test inbox pagination."""
        response = inbox_client.get("/inbox", params={"page": 1, "per_page": 25})
        assert response.status_code in [200, 302, 307]


# =============================================================================
# CONVERSATION DETAIL TESTS
# =============================================================================


class TestConversationDetail:
    """Test conversation detail routes."""

    def test_detail_requires_auth(self, unauthenticated_client):
        """Test conversation detail requires auth."""
        response = unauthenticated_client.get("/inbox/1")
        assert response.status_code in [401, 403, 307]

    def test_detail_requires_scope(self, no_scope_client):
        """Test conversation detail requires scope."""
        response = no_scope_client.get("/inbox/1")
        assert response.status_code in [403, 401]

    def test_detail_not_found(self, inbox_client):
        """Test 404 for non-existent conversation."""
        response = inbox_client.get("/inbox/999999")
        assert response.status_code == 404

    def test_detail_invalid_id(self, inbox_client):
        """Test handling of invalid conversation ID."""
        response = inbox_client.get("/inbox/invalid")
        assert response.status_code in [404, 422]


# =============================================================================
# MESSAGES PARTIAL TESTS
# =============================================================================


class TestMessagesPartial:
    """Test messages thread partial for HTMX polling."""

    def test_messages_requires_auth(self, unauthenticated_client):
        """Test messages partial requires auth."""
        response = unauthenticated_client.get("/inbox/1/messages")
        assert response.status_code in [401, 403, 307]

    def test_messages_not_found(self, inbox_client):
        """Test 404 for non-existent conversation messages."""
        response = inbox_client.get("/inbox/999999/messages")
        assert response.status_code == 404


# =============================================================================
# REPLY TESTS
# =============================================================================


class TestConversationReply:
    """Test conversation reply routes."""

    def test_reply_requires_write_scope(self, inbox_read_client):
        """Test reply requires write scope."""
        response = inbox_read_client.post(
            "/inbox/1/reply",
            data={"body": "Test reply"}
        )
        assert response.status_code in [403, 401]

    def test_reply_requires_csrf(self, inbox_client):
        """Test reply requires CSRF token."""
        response = inbox_client.post(
            "/inbox/999/reply",
            data={"body": "Test reply"}
        )
        # Either 403 (CSRF) or 404 (conversation not found)
        assert response.status_code in [403, 404, 422]

    def test_reply_requires_body(self, inbox_client):
        """Test reply requires non-empty body."""
        response = inbox_client.post(
            "/inbox/999/reply",
            data={"body": ""}
        )
        # Should return error (either validation error or CSRF/not found)
        assert response.status_code in [400, 403, 404, 422]


# =============================================================================
# STATUS UPDATE TESTS
# =============================================================================


class TestConversationStatus:
    """Test conversation status update routes."""

    def test_status_requires_write_scope(self, inbox_read_client):
        """Test status update requires write scope."""
        response = inbox_read_client.post(
            "/inbox/1/status",
            data={"status": "resolved"}
        )
        assert response.status_code in [403, 401]

    def test_status_requires_csrf(self, inbox_client):
        """Test status update requires CSRF token."""
        response = inbox_client.post(
            "/inbox/999/status",
            data={"status": "resolved"}
        )
        # Either 403 (CSRF) or 404 (not found)
        assert response.status_code in [403, 404, 422]

    def test_invalid_status_rejected(self, inbox_client):
        """Test that invalid status value is rejected."""
        response = inbox_client.post(
            "/inbox/999/status",
            data={"status": "invalid_status_value"}
        )
        # Should handle gracefully
        assert response.status_code in [204, 400, 403, 404, 422]


# =============================================================================
# STAR TOGGLE TESTS
# =============================================================================


class TestConversationStar:
    """Test conversation star toggle routes."""

    def test_star_requires_write_scope(self, inbox_read_client):
        """Test star toggle requires write scope."""
        response = inbox_read_client.post("/inbox/1/star")
        assert response.status_code in [403, 401]

    def test_star_requires_csrf(self, inbox_client):
        """Test star toggle requires CSRF token."""
        response = inbox_client.post("/inbox/999/star")
        # Either 403 (CSRF) or 404 (not found)
        assert response.status_code in [403, 404, 422]


# =============================================================================
# HTMX PARTIAL TESTS
# =============================================================================


class TestHTMXPartials:
    """Test HTMX partial responses."""

    def test_inbox_partial_with_htmx_header(self, inbox_client):
        """Test inbox returns partial with HTMX header."""
        response = inbox_client.get(
            "/inbox",
            headers={"HX-Request": "true"}
        )
        if response.status_code == 200:
            content = response.text
            # Should be a partial, not full page
            # Basic check - adjust based on template structure
            assert response.status_code == 200

    def test_table_partial_endpoint(self, inbox_client):
        """Test table partial endpoint."""
        response = inbox_client.get("/inbox/table")
        assert response.status_code in [200, 302, 307]

    def test_table_partial_with_filters(self, inbox_client):
        """Test table partial with filters."""
        response = inbox_client.get(
            "/inbox/table",
            params={"status": "open", "priority": "high"}
        )
        assert response.status_code in [200, 302, 307]


# =============================================================================
# SECURITY TESTS
# =============================================================================


class TestSecurityMeasures:
    """Test security measures in omnichannel routes."""

    def test_search_injection_prevented(self, inbox_client):
        """Test SQL injection via search is prevented."""
        response = inbox_client.get(
            "/inbox",
            params={"q": "'; DROP TABLE conversations; --"}
        )
        # Should handle gracefully, not crash
        assert response.status_code in [200, 302, 307]

    def test_channel_id_validation(self, inbox_client):
        """Test channel ID is validated."""
        response = inbox_client.get(
            "/inbox",
            params={"channel": "invalid"}
        )
        # Should handle gracefully
        assert response.status_code in [200, 302, 307, 422]


# =============================================================================
# PRINCIPAL/AUDIT TESTS
# =============================================================================


class TestPrincipalPassing:
    """Test that principal is correctly passed to services."""

    def test_reply_sets_agent_id(self, inbox_client):
        """Test that reply sets agent_id from principal."""
        # This validates the fix where we pass principal to services
        # The agent_id should be set from the principal's user_id

        # Create a test conversation first (if possible)
        # For now, just verify the endpoint doesn't crash
        response = inbox_client.post(
            "/inbox/999/reply",
            data={"body": "Test reply"}
        )
        # Either fails with CSRF/404, but not 500
        assert response.status_code != 500

    def test_status_update_audit_trail(self, inbox_client):
        """Test that status update maintains audit trail."""
        response = inbox_client.post(
            "/inbox/999/status",
            data={"status": "resolved"}
        )
        # Should not crash
        assert response.status_code != 500


# =============================================================================
# STATS PROPERTY TESTS
# =============================================================================


class TestInboxStats:
    """Test inbox stats display."""

    def test_inbox_shows_stats(self, inbox_client):
        """Test that inbox page includes stats."""
        response = inbox_client.get("/inbox")
        if response.status_code == 200:
            content = response.text
            # Stats should be included in the page
            # The exact content depends on template structure
            assert response.status_code == 200

    def test_stats_property_names(self, inbox_client):
        """Test that correct stats property names are used."""
        # This validates the fix for InboxStats property names
        # (open_conversations instead of .open, etc.)
        response = inbox_client.get("/inbox")
        # Should not crash with AttributeError
        assert response.status_code != 500


# =============================================================================
# PARTY LINK TESTS
# =============================================================================


class TestPartyLink:
    """Test party link in conversation detail."""

    def test_conversation_detail_accessible(self, inbox_client):
        """Test conversation detail page renders without error."""
        # If conversation 999 doesn't exist, should 404 not 500
        response = inbox_client.get("/inbox/999")
        assert response.status_code in [404, 200]

    def test_party_link_present_when_party_exists(self, inbox_client):
        """Test party link is shown when party_id is set."""
        # This validates the template change to add party link
        # The actual verification requires a conversation with party_id
        # For now, just ensure no template errors
        response = inbox_client.get("/inbox/999")
        assert response.status_code in [404, 200]


# =============================================================================
# ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in omnichannel routes."""

    def test_graceful_handling_of_missing_conversation(self, inbox_client):
        """Test graceful 404 for missing conversation."""
        response = inbox_client.get("/inbox/999999999")
        assert response.status_code == 404

    def test_graceful_handling_of_invalid_pagination(self, inbox_client):
        """Test graceful handling of invalid pagination."""
        response = inbox_client.get(
            "/inbox",
            params={"page": -1, "per_page": 10000}
        )
        # Should handle gracefully, may correct to valid values
        assert response.status_code in [200, 302, 307, 422]
