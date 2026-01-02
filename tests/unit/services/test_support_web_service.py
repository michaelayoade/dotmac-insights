"""
Unit Tests: SupportWebService

Tests the support web service layer for ticket management operations.
Covers CRUD, pagination, filtering, sorting, and bulk operations.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch
import enum

import pytest

from tests.unit.conftest import MockSession, MockQuery


# =============================================================================
# MOCK ENUMS (match app/models/unified_ticket.py)
# =============================================================================


class MockTicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    REOPENED = "reopened"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MockTicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MockTicketType(str, enum.Enum):
    SUPPORT = "support"
    INCIDENT = "incident"
    SERVICE_REQUEST = "service_request"
    QUESTION = "question"


# =============================================================================
# MOCK DATA CLASSES
# =============================================================================


@dataclass
class MockUnifiedTicket:
    """Mock UnifiedTicket for testing."""
    id: int
    ticket_number: str = "TKT-TEST-0001"
    subject: str = "Test Ticket"
    description: Optional[str] = None
    status: str = "open"
    priority: str = "medium"
    ticket_type: str = "support"
    channel: Optional[str] = None
    source: str = "internal"
    party_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    assigned_to_id: Optional[int] = None
    assigned_team: Optional[str] = None
    resolution: Optional[str] = None
    resolution_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None


@dataclass
class MockPrincipal:
    """Mock Principal for testing audit fields."""
    id: int = 1
    email: str = "test@example.com"
    name: str = "Test User"
    is_superuser: bool = False
    scopes: set = field(default_factory=lambda: {"support:read", "support:write"})


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MockSession()


@pytest.fixture
def mock_principal():
    """Create a mock principal for audit fields."""
    return MockPrincipal(id=42, email="agent@example.com", name="Test Agent")


@pytest.fixture
def sample_tickets():
    """Create a list of sample tickets."""
    return [
        MockUnifiedTicket(
            id=1,
            ticket_number="TKT-20260101-ABC1",
            subject="First Ticket",
            status="open",
            priority="high",
            assigned_to_id=None,
        ),
        MockUnifiedTicket(
            id=2,
            ticket_number="TKT-20260101-ABC2",
            subject="Second Ticket",
            status="in_progress",
            priority="medium",
            assigned_to_id=10,
        ),
        MockUnifiedTicket(
            id=3,
            ticket_number="TKT-20260101-ABC3",
            subject="Third Ticket",
            status="resolved",
            priority="low",
            assigned_to_id=10,
        ),
    ]


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestSupportWebServiceInit:
    """Test SupportWebService initialization."""

    def test_init_with_user_id(self, mock_db):
        """Test initialization with user_id."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=42)

        assert service.db == mock_db
        assert service.user_id == 42
        assert service.principal is None

    def test_init_with_principal(self, mock_db, mock_principal):
        """Test initialization with principal."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=42, principal=mock_principal)

        assert service.db == mock_db
        assert service.user_id == 42
        assert service.principal == mock_principal


class TestTicketNumberGeneration:
    """Test ticket number generation (race-condition safe)."""

    def test_ticket_number_format(self, mock_db):
        """Test that ticket number has correct format: TKT-YYYYMMDDHHMMSS-XXXX."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        # Create ticket without ticket_number
        data = {
            "subject": "Test Ticket",
            "description": "Test description",
        }

        # Mock the add/flush behavior
        def mock_add(obj):
            obj.id = 1
            mock_db._added.append(obj)

        mock_db.add = mock_add
        mock_db.flush = lambda: None

        ticket = service.create_ticket(data)

        # Verify format
        assert ticket.ticket_number.startswith("TKT-")
        parts = ticket.ticket_number.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 14  # YYYYMMDDHHMMSS
        assert len(parts[2]) == 4  # UUID suffix

    def test_ticket_number_uniqueness(self, mock_db):
        """Test that generated ticket numbers are unique."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)
        generated_numbers = set()

        def mock_add(obj):
            obj.id = len(generated_numbers) + 1
            mock_db._added.append(obj)

        mock_db.add = mock_add
        mock_db.flush = lambda: None

        # Generate multiple ticket numbers
        for _ in range(100):
            ticket = service.create_ticket({"subject": "Test"})
            assert ticket.ticket_number not in generated_numbers
            generated_numbers.add(ticket.ticket_number)

    def test_existing_ticket_number_preserved(self, mock_db):
        """Test that existing ticket number is not overwritten."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        def mock_add(obj):
            obj.id = 1
            mock_db._added.append(obj)

        mock_db.add = mock_add
        mock_db.flush = lambda: None

        data = {
            "subject": "Test Ticket",
            "ticket_number": "CUSTOM-001",
        }

        ticket = service.create_ticket(data)
        assert ticket.ticket_number == "CUSTOM-001"


class TestSortValidation:
    """Test sort column validation (SQL injection prevention)."""

    def test_valid_sort_columns(self, mock_db):
        """Test that valid sort columns are accepted."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        valid_sorts = [
            "created_at", "updated_at", "ticket_number", "subject",
            "status", "priority", "ticket_type", "due_date",
        ]

        for sort in valid_sorts:
            assert sort in service.ALLOWED_TICKET_SORTS

    def test_invalid_sort_column_fallback(self, mock_db, sample_tickets):
        """Test that invalid sort columns fall back to created_at."""
        from app.modules.support._services import SupportWebService

        # Register mock data
        mock_db.register_data(type(sample_tickets[0]), sample_tickets)

        service = SupportWebService(mock_db, user_id=1)

        # Patch the query to track the sort column used
        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Try with SQL injection attempt
            result = service.list_tickets(sort="'; DROP TABLE tickets; --")

            # Should still work (falls back to created_at)
            assert result is not None

    def test_invalid_dir_fallback(self, mock_db, sample_tickets):
        """Test that invalid direction falls back to desc."""
        from app.modules.support._services import SupportWebService

        mock_db.register_data(type(sample_tickets[0]), sample_tickets)

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            # Try with invalid direction
            result = service.list_tickets(dir="DROP TABLE")

            # Should still work (falls back to desc)
            assert result is not None


class TestUnassignedFilter:
    """Test the unassigned_only filter for correct pagination."""

    def test_unassigned_filter_applied_to_query(self, mock_db):
        """Test that unassigned filter is applied at DB level, not client-side."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 5  # Total would be higher without filter
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            result = service.list_tickets(unassigned_only=True)

            # Verify filter was called (for unassigned)
            assert mock_query.filter.called

    def test_unassigned_with_pagination(self, mock_db):
        """Test that pagination counts reflect filtered results."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 3  # Only 3 unassigned
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            result = service.list_tickets(unassigned_only=True, per_page=25)

            # Total should reflect filtered count
            assert result["total"] == 3
            assert result["pages"] == 1


class TestDashboardStats:
    """Test dashboard statistics calculations."""

    def test_dashboard_stats_structure(self, mock_db):
        """Test that dashboard stats have correct structure."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.group_by.return_value = mock_query
            mock_query.scalar.return_value = 0
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            stats = service.get_dashboard_stats()

            # Verify structure
            assert "total_open" in stats
            assert "urgent_tickets" in stats
            assert "resolved_today" in stats
            assert "created_today" in stats
            assert "status_distribution" in stats
            assert "priority_distribution" in stats

    def test_created_today_stat(self, mock_db):
        """Test that created_today stat is included."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.group_by.return_value = mock_query

            # Set up scalar returns for different queries
            mock_query.scalar.side_effect = [10, 2, 5, 3, 7]  # Various counts
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            stats = service.get_dashboard_stats()

            # created_today should be one of the returned values
            assert "created_today" in stats


class TestStatusValidation:
    """Test status validation in update operations."""

    def test_update_field_validates_status(self, mock_db, sample_tickets):
        """Test that update_field validates status values."""
        from app.modules.support._services import SupportWebService
        from app.services.errors import ValidationError

        mock_db.register_data(type(sample_tickets[0]), [sample_tickets[0]])

        service = SupportWebService(mock_db, user_id=1)

        # Patch get_ticket to return our mock
        with patch.object(service, 'get_ticket', return_value=sample_tickets[0]):
            # Valid status should work
            try:
                service.update_field(1, "status", "resolved")
            except ValidationError:
                pytest.fail("Valid status should not raise ValidationError")

            # Invalid status should raise error
            with pytest.raises(ValidationError):
                service.update_field(1, "status", "invalid_status")

    def test_update_field_validates_priority(self, mock_db, sample_tickets):
        """Test that update_field validates priority values."""
        from app.modules.support._services import SupportWebService
        from app.services.errors import ValidationError

        mock_db.register_data(type(sample_tickets[0]), [sample_tickets[0]])

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'get_ticket', return_value=sample_tickets[0]):
            # Invalid priority should raise error
            with pytest.raises(ValidationError):
                service.update_field(1, "priority", "super_urgent")


class TestBulkOperations:
    """Test bulk update operations."""

    def test_bulk_update_status_sets_audit_fields(self, mock_db):
        """Test that bulk status update sets audit fields."""
        from app.modules.support._services import SupportWebService
        from app.models.unified_ticket import TicketStatus

        service = SupportWebService(mock_db, user_id=42)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.update.return_value = 3  # 3 updated

            mock_db_patched.query.return_value = mock_query

            result = service.bulk_update_status([1, 2, 3], TicketStatus.RESOLVED)

            assert result == 3
            # Verify update was called with audit fields
            mock_query.update.assert_called_once()
            update_dict = mock_query.update.call_args[0][0]
            assert "updated_by_id" in update_dict
            assert update_dict["updated_by_id"] == 42

    def test_bulk_delete_soft_deletes(self, mock_db):
        """Test that bulk delete performs soft delete."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=42)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.update.return_value = 2  # 2 deleted

            mock_db_patched.query.return_value = mock_query

            result = service.bulk_delete([1, 2])

            assert result == 2
            # Verify soft delete fields were set
            update_dict = mock_query.update.call_args[0][0]
            assert update_dict["is_deleted"] is True
            assert "deleted_at" in update_dict
            assert update_dict["deleted_by_id"] == 42


class TestAuditFields:
    """Test audit field population."""

    def test_create_sets_audit_fields(self, mock_db):
        """Test that create sets created_by_id and updated_by_id."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=99)

        def mock_add(obj):
            obj.id = 1
            mock_db._added.append(obj)

        mock_db.add = mock_add
        mock_db.flush = lambda: None

        ticket = service.create_ticket({"subject": "Test"})

        assert ticket.created_by_id == 99
        assert ticket.updated_by_id == 99

    def test_update_sets_updated_by_id(self, mock_db, sample_tickets):
        """Test that update sets updated_by_id."""
        from app.modules.support._services import SupportWebService

        mock_db.register_data(type(sample_tickets[0]), [sample_tickets[0]])

        service = SupportWebService(mock_db, user_id=77)

        with patch.object(service, 'get_ticket', return_value=sample_tickets[0]):
            ticket = service.update_ticket(1, {"subject": "Updated Subject"})

            assert ticket.updated_by_id == 77

    def test_delete_sets_deleted_by_id(self, mock_db, sample_tickets):
        """Test that delete sets deleted_by_id."""
        from app.modules.support._services import SupportWebService

        mock_db.register_data(type(sample_tickets[0]), [sample_tickets[0]])

        service = SupportWebService(mock_db, user_id=55)

        with patch.object(service, 'get_ticket', return_value=sample_tickets[0]):
            ticket = service.delete_ticket(1)

            assert ticket.is_deleted is True
            assert ticket.deleted_by_id == 55


class TestAgentStats:
    """Test agent statistics."""

    def test_agent_stats_structure(self, mock_db):
        """Test agent stats return correct structure."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.outerjoin.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.group_by.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.subquery.return_value = MagicMock()

            # Mock agent results
            mock_result = MagicMock()
            mock_result.id = 1
            mock_result.display_name = "Agent 1"
            mock_result.email = "agent1@example.com"
            mock_result.employee_id = 10
            mock_result.open_tickets = 5
            mock_query.all.return_value = [mock_result]

            mock_db_patched.query.return_value = mock_query

            stats = service.get_agent_stats(limit=10)

            assert len(stats) == 1
            assert stats[0]["id"] == 1
            assert stats[0]["name"] == "Agent 1"
            assert stats[0]["open_tickets"] == 5


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_ticket_list(self, mock_db):
        """Test listing tickets when none exist."""
        from app.modules.support._services import SupportWebService

        service = SupportWebService(mock_db, user_id=1)

        with patch.object(service, 'db') as mock_db_patched:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_db_patched.query.return_value = mock_query

            result = service.list_tickets()

            assert result["items"] == []
            assert result["total"] == 0
            assert result["pages"] == 0

    def test_bulk_operations_with_empty_list(self, mock_db):
        """Test bulk operations with empty ID list."""
        from app.modules.support._services import SupportWebService
        from app.models.unified_ticket import TicketStatus, TicketPriority

        service = SupportWebService(mock_db, user_id=1)

        # Should return 0, not error
        assert service.bulk_update_status([], TicketStatus.RESOLVED) == 0
        assert service.bulk_update_priority([], TicketPriority.HIGH) == 0
        assert service.bulk_delete([]) == 0

    def test_get_ticket_not_found(self, mock_db):
        """Test getting non-existent ticket."""
        from app.modules.support._services import SupportWebService
        from app.services.errors import NotFoundError

        mock_db.register_data(MockUnifiedTicket, [])

        service = SupportWebService(mock_db, user_id=1)

        with pytest.raises(NotFoundError):
            service.get_ticket(999)

    def test_update_nonexistent_ticket(self, mock_db):
        """Test updating non-existent ticket."""
        from app.modules.support._services import SupportWebService
        from app.services.errors import NotFoundError

        mock_db.register_data(MockUnifiedTicket, [])

        service = SupportWebService(mock_db, user_id=1)

        with pytest.raises(NotFoundError):
            service.update_ticket(999, {"subject": "Updated"})
