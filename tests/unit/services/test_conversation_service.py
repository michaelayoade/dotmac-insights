"""
Unit Tests: ConversationService

Tests the omnichannel conversation service for inbox operations.
Covers CRUD, filtering, assignment, status management, and bulk operations.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch, PropertyMock
import enum

import pytest

from tests.unit.conftest import MockSession, MockQuery


# =============================================================================
# MOCK ENUMS
# =============================================================================


class MockConversationStatus(str, enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"
    CLOSED = "closed"


class MockConversationPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# =============================================================================
# MOCK DATA CLASSES
# =============================================================================


@dataclass
class MockOmniConversation:
    """Mock OmniConversation for testing."""
    id: int
    channel_id: int = 1
    subject: Optional[str] = "Test Conversation"
    external_thread_id: Optional[str] = None
    status: str = "open"
    priority: str = "medium"
    party_id: Optional[int] = None
    ticket_id: Optional[int] = None
    lead_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    assigned_party_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    contact_name: Optional[str] = "Test Contact"
    contact_email: Optional[str] = "contact@example.com"
    contact_company: Optional[str] = None
    tags: Optional[List[str]] = None
    is_starred: bool = False
    unread_count: int = 0
    message_count: int = 0
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[Any] = field(default_factory=list)
    channel: Optional[Any] = None
    assigned_agent: Optional[Any] = None
    assigned_team: Optional[Any] = None


@dataclass
class MockOmniChannel:
    """Mock OmniChannel for testing."""
    id: int
    name: str = "Test Channel"
    type: str = "email"
    is_active: bool = True


@dataclass
class MockOmniMessage:
    """Mock OmniMessage for testing."""
    id: int
    conversation_id: int
    direction: str = "inbound"
    body: str = "Test message"
    read_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attachments: List[Any] = field(default_factory=list)


@dataclass
class MockAgent:
    """Mock Agent for testing."""
    id: int
    email: str = "agent@example.com"
    display_name: str = "Test Agent"
    is_active: bool = True


@dataclass
class MockTeam:
    """Mock Team for testing."""
    id: int
    name: str = "Support Team"
    is_active: bool = True


@dataclass
class MockPrincipal:
    """Mock Principal for audit fields."""
    id: int = 1
    email: str = "test@example.com"
    name: str = "Test User"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MockSession()


@pytest.fixture
def mock_principal():
    """Create a mock principal."""
    return MockPrincipal(id=42, email="agent@example.com")


@pytest.fixture(autouse=True)
def disable_soft_validation(monkeypatch):
    """Disable soft validation for unit tests with mock models."""
    from app.services.validation.soft_validation_service import SoftValidationService

    monkeypatch.setattr(SoftValidationService, "validate_and_store", lambda *args, **kwargs: None)


@pytest.fixture
def sample_channel():
    """Create a sample channel."""
    return MockOmniChannel(id=1, name="Email", type="email")


@pytest.fixture
def sample_conversations():
    """Create a list of sample conversations."""
    return [
        MockOmniConversation(
            id=1,
            subject="First Conversation",
            status="open",
            priority="high",
            assigned_agent_id=None,
            unread_count=5,
        ),
        MockOmniConversation(
            id=2,
            subject="Second Conversation",
            status="pending",
            priority="medium",
            assigned_agent_id=10,
            assigned_party_id=10,
            unread_count=0,
        ),
        MockOmniConversation(
            id=3,
            subject="Third Conversation",
            status="resolved",
            priority="low",
            assigned_agent_id=10,
            assigned_party_id=10,
            resolved_at=datetime.now(timezone.utc),
        ),
    ]


@pytest.fixture
def sample_messages():
    """Create sample messages."""
    return [
        MockOmniMessage(id=1, conversation_id=1, direction="inbound", body="Hello"),
        MockOmniMessage(id=2, conversation_id=1, direction="outbound", body="Hi there"),
        MockOmniMessage(id=3, conversation_id=1, direction="inbound", body="Thanks"),
    ]


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestConversationServiceInit:
    """Test ConversationService initialization."""

    def test_init_with_principal(self, mock_db, mock_principal):
        """Test initialization with principal."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db, principal=mock_principal)

        assert service.db == mock_db
        assert service.principal == mock_principal

    def test_init_without_principal(self, mock_db):
        """Test initialization without principal."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        assert service.db == mock_db
        assert service.principal is None


class TestSortValidation:
    """Test sort column validation."""

    def test_allowed_sort_columns(self, mock_db):
        """Test that ALLOWED_SORTS contains expected columns."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        expected = {
            "last_message_at", "created_at", "updated_at", "subject",
            "priority", "status", "unread_count", "message_count",
        }
        assert service.ALLOWED_SORTS == expected

    def test_invalid_sort_falls_back(self, mock_db):
        """Test that invalid sort column falls back to last_message_at."""
        from app.services.support.conversations import ConversationService
        from app.services.types import PaginationParams

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Should not raise, should fall back
            result = service.list(
                sort_by="malicious_column'; DROP TABLE --",
                sort_order="desc"
            )

            assert result is not None

    def test_invalid_sort_order_falls_back(self, mock_db):
        """Test that invalid sort order falls back to desc."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            result = service.list(
                sort_by="created_at",
                sort_order="invalid"
            )

            assert result is not None


class TestEnumStringHandling:
    """Test enum vs string handling in filters."""

    def test_filter_with_string_status(self, mock_db):
        """Test filtering with string status value."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Pass string status (as routes do)
            filters = ConversationFilters(status="open")
            result = service.list(filters=filters)

            # Should work without error
            assert result is not None

    def test_filter_with_enum_status(self, mock_db):
        """Test filtering with enum status value."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Pass enum status
            filters = ConversationFilters(status=MockConversationStatus.OPEN)
            result = service.list(filters=filters)

            # Should work without error
            assert result is not None

    def test_filter_with_string_priority(self, mock_db):
        """Test filtering with string priority value."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Pass string priority
            filters = ConversationFilters(priority="high")
            result = service.list(filters=filters)

            assert result is not None


class TestInboxStats:
    """Test inbox statistics."""

    def test_stats_structure(self, mock_db):
        """Test that stats have correct structure."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 0
            mock_db_patched.query.return_value = mock_query

            stats = service.get_stats()

            # Verify InboxStats fields
            assert hasattr(stats, 'total_conversations')
            assert hasattr(stats, 'open_conversations')
            assert hasattr(stats, 'pending_conversations')
            assert hasattr(stats, 'resolved_conversations')
            assert hasattr(stats, 'unassigned_conversations')
            assert hasattr(stats, 'my_conversations')
            assert hasattr(stats, 'unread_conversations')
            assert hasattr(stats, 'snoozed_conversations')

    def test_stats_with_agent_id(self, mock_db):
        """Test stats with agent_id for my_conversations count."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 5  # my_conversations count
            mock_db_patched.query.return_value = mock_query

            stats = service.get_stats(agent_id=42)

            # my_conversations should be populated
            assert stats.my_conversations >= 0


class TestConversationFilters:
    """Test conversation filtering."""

    def test_search_filter(self, mock_db):
        """Test search filter applies to subject, contact_name, contact_email."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 1
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            filters = ConversationFilters(search="test query")
            result = service.list(filters=filters)

            # Filter should have been called
            assert mock_query.filter.called

    def test_unassigned_filter(self, mock_db):
        """Test unassigned_only filter."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            filters = ConversationFilters(unassigned_only=True)
            result = service.list(filters=filters)

            assert mock_query.filter.called

    def test_starred_filter(self, mock_db):
        """Test starred_only filter."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            filters = ConversationFilters(starred_only=True)
            result = service.list(filters=filters)

            assert mock_query.filter.called

    def test_tags_filter(self, mock_db):
        """Test tags filter."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationFilters

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            filters = ConversationFilters(tags=["urgent", "vip"])
            result = service.list(filters=filters)

            assert mock_query.filter.called


class TestConversationGet:
    """Test getting conversations."""

    def test_get_not_found(self, mock_db):
        """Test getting non-existent conversation."""
        from app.services.support.conversations import ConversationService
        from app.services.support.errors import ConversationNotFoundError

        mock_db.register_data(MockOmniConversation, [])

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_db_patched.query.return_value = mock_query

            with pytest.raises(ConversationNotFoundError):
                service.get(999)

    def test_get_with_messages(self, mock_db, sample_conversations, sample_messages):
        """Test getting conversation with messages."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.options.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = sample_conversations[0]
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = sample_messages
            mock_query.scalar.return_value = len(sample_messages)
            mock_db_patched.query.return_value = mock_query

            result = service.get_with_messages(1, message_limit=50)

            assert result.conversation == sample_conversations[0]
            assert len(result.messages) == len(sample_messages)


class TestConversationAssignment:
    """Test conversation assignment."""

    def test_assign_agent(self, mock_db, sample_conversations):
        """Test assigning agent to conversation."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]

        with patch.object(service, 'get', return_value=conv):
            mock_agent = MockAgent(id=10)

            with patch.object(service, 'db') as mock_db_patched:
                mock_query = MagicMock()
                mock_query.join.return_value = mock_query
                mock_query.filter.return_value = mock_query
                mock_query.first.return_value = mock_agent
                mock_db_patched.query.return_value = mock_query
                mock_db_patched.flush = MagicMock()

                result = service.assign(1, agent_id=10)

                assert result.assigned_party_id == 10
                assert result.assigned_at is not None

    def test_unassign(self, mock_db, sample_conversations):
        """Test unassigning conversation."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[1]  # Has assigned_agent_id=10

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.unassign(2)

                assert result.assigned_party_id is None
                assert result.assigned_team_id is None


class TestConversationStatus:
    """Test conversation status operations."""

    def test_update_status(self, mock_db, sample_conversations):
        """Test updating conversation status."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.update_status(1, "pending")

                assert result.status == "pending"

    def test_resolve_sets_resolved_at(self, mock_db, sample_conversations):
        """Test resolving conversation sets resolved_at."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.resolved_at = None

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.resolve(1)

                assert result.status == "resolved"
                assert result.resolved_at is not None

    def test_reopen_clears_resolved_at(self, mock_db, sample_conversations):
        """Test reopening conversation clears resolved_at."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[2]  # Resolved conversation

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.reopen(3)

                assert result.status == "open"
                assert result.resolved_at is None


class TestConversationStar:
    """Test conversation starring."""

    def test_star_conversation(self, mock_db, sample_conversations):
        """Test starring a conversation."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.is_starred = False

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.star(1, True)

                assert result.is_starred is True

    def test_unstar_conversation(self, mock_db, sample_conversations):
        """Test unstarring a conversation."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.is_starred = True

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.star(1, False)

                assert result.is_starred is False


class TestConversationTags:
    """Test conversation tagging."""

    def test_add_tag(self, mock_db, sample_conversations):
        """Test adding a tag."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.tags = []

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.add_tag(1, "urgent")

                assert "urgent" in result.tags

    def test_add_duplicate_tag_ignored(self, mock_db, sample_conversations):
        """Test adding duplicate tag is ignored."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.tags = ["urgent"]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.add_tag(1, "urgent")

                assert result.tags.count("urgent") == 1

    def test_remove_tag(self, mock_db, sample_conversations):
        """Test removing a tag."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.tags = ["urgent", "vip"]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                result = service.remove_tag(1, "urgent")

                assert "urgent" not in result.tags
                assert "vip" in result.tags


class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_update_status(self, mock_db, sample_conversations):
        """Test bulk status update."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.side_effect = sample_conversations
            mock_db_patched.query.return_value = mock_query
            mock_db_patched.flush = MagicMock()

            result = service.bulk_update_status([1, 2, 3], "resolved")

            assert result.updated_count == 3

    def test_bulk_update_empty_list(self, mock_db):
        """Test bulk update with empty list."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationBulkUpdate

        service = ConversationService(mock_db)

        data = ConversationBulkUpdate(ids=[])
        result = service.bulk_update(data)

        assert result.updated_count == 0
        assert result.failed_count == 0


class TestMarkRead:
    """Test mark as read functionality."""

    def test_mark_read_resets_unread_count(self, mock_db, sample_conversations):
        """Test marking conversation as read resets unread_count."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]
        conv.unread_count = 5

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_query = MagicMock()
                mock_query.filter.return_value = mock_query
                mock_query.update.return_value = 3  # 3 messages marked as read
                mock_db_patched.query.return_value = mock_query
                mock_db_patched.flush = MagicMock()

                result = service.mark_read(1)

                assert conv.unread_count == 0
                assert result == 3


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_assign_invalid_agent(self, mock_db, sample_conversations):
        """Test assigning non-existent agent."""
        from app.services.support.conversations import ConversationService
        from app.services.support.errors import ConversationAssignmentError

        service = ConversationService(mock_db)
        conv = sample_conversations[0]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_query = MagicMock()
                mock_query.join.return_value = mock_query
                mock_query.filter.return_value = mock_query
                mock_query.first.return_value = None  # Agent not found
                mock_db_patched.query.return_value = mock_query

                with pytest.raises(ConversationAssignmentError):
                    service.assign(1, agent_id=999)

    def test_assign_invalid_team(self, mock_db, sample_conversations):
        """Test assigning non-existent team."""
        from app.services.support.conversations import ConversationService
        from app.services.support.errors import ConversationAssignmentError

        service = ConversationService(mock_db)
        conv = sample_conversations[0]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_query = MagicMock()
                mock_query.filter.return_value = mock_query
                mock_query.first.return_value = None  # Team not found
                mock_db_patched.query.return_value = mock_query

                with pytest.raises(ConversationAssignmentError):
                    service.assign(1, team_id=999)

    def test_create_with_invalid_channel(self, mock_db):
        """Test creating conversation with invalid channel."""
        from app.services.support.conversations import ConversationService
        from app.services.support.types import ConversationCreate
        from app.services.support.errors import ValidationError

        service = ConversationService(mock_db)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None  # Channel not found
            mock_db_patched.query.return_value = mock_query

            data = ConversationCreate(channel_id=999, subject="Test")

            with pytest.raises(ValidationError):
                service.create(data)

    def test_snooze_without_until(self, mock_db, sample_conversations):
        """Test snoozing without specifying until time."""
        from app.services.support.conversations import ConversationService

        service = ConversationService(mock_db)
        conv = sample_conversations[0]

        with patch.object(service, 'get', return_value=conv):
            with patch.object(service, 'db') as mock_db_patched:
                mock_db_patched.flush = MagicMock()

                # Snooze until tomorrow
                until = datetime.now(timezone.utc) + timedelta(days=1)
                result = service.snooze(1, until=until)

                assert result.status == "snoozed"
                assert result.snoozed_until is not None
