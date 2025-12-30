"""
Unit tests for SLAEngine.

Tests SLA policy matching, target time calculations with business hours,
and breach detection.
"""
from __future__ import annotations

from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
import enum

import pytest

# Import the service
from app.services.sla_engine import SLAEngine

# Import mock fixtures
from tests.unit.conftest import (
    MockSession,
    MockTicket,
    MockTicketStatus,
    MockTicketPriority,
    MockSLAPolicy,
    MockSLATarget,
    MockBusinessCalendar,
)


# =============================================================================
# ADDITIONAL MOCK CLASSES
# =============================================================================


class MockSLATargetType(str, enum.Enum):
    FIRST_RESPONSE = "first_response"
    RESOLUTION = "resolution"


class MockBusinessHourType(str, enum.Enum):
    TWENTY_FOUR_SEVEN = "24x7"
    BUSINESS_HOURS = "business_hours"


@dataclass
class MockBusinessCalendarHoliday:
    """Mock holiday entry."""
    id: int = 1
    calendar_id: int = 1
    holiday_date: date = date(2024, 12, 25)
    is_recurring: bool = False
    description: str = "Christmas"


@dataclass
class MockSLABreachLog:
    """Mock SLA breach log."""
    id: int = 1
    ticket_id: int = 1
    policy_id: Optional[int] = 1
    target_type: str = "first_response"
    target_hours: Decimal = Decimal("4")
    actual_hours: Decimal = Decimal("5")
    breached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MockSession()


@pytest.fixture
def sla_engine(mock_db):
    """Create SLAEngine with mock db."""
    return SLAEngine(mock_db)


@pytest.fixture
def ticket_medium():
    """Medium priority ticket."""
    return MockTicket(
        id=1,
        subject="Test Ticket",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.MEDIUM,
        opening_date=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
        created_at=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def ticket_urgent():
    """Urgent priority ticket."""
    return MockTicket(
        id=2,
        subject="Urgent Issue",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.URGENT,
        ticket_type="technical",
        issue_type="outage",
        opening_date=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def ticket_with_sla():
    """Ticket with SLA deadlines set."""
    return MockTicket(
        id=3,
        subject="SLA Ticket",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.MEDIUM,
        opening_date=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
        response_by=datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
        resolution_by=datetime(2024, 1, 16, 9, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def policy_standard():
    """Standard SLA policy matching medium priority."""
    policy = MockSLAPolicy(
        id=1,
        name="Standard SLA",
        is_active=True,
        is_default=False,
        priority=100,
        conditions=[
            {"field": "priority", "operator": "equals", "value": "medium"}
        ],
    )
    policy.targets = [
        MockSLATarget(id=1, policy_id=1, target_type="first_response", priority="medium", target_hours=Decimal("4")),
        MockSLATarget(id=2, policy_id=1, target_type="resolution", priority="medium", target_hours=Decimal("24")),
    ]
    policy.calendar = None
    return policy


@pytest.fixture
def policy_urgent():
    """Urgent SLA policy with shorter targets."""
    policy = MockSLAPolicy(
        id=2,
        name="Urgent SLA",
        is_active=True,
        is_default=False,
        priority=50,  # Higher priority than standard
        conditions=[
            {"field": "priority", "operator": "equals", "value": "urgent"}
        ],
    )
    policy.targets = [
        MockSLATarget(id=3, policy_id=2, target_type="first_response", priority="urgent", target_hours=Decimal("1")),
        MockSLATarget(id=4, policy_id=2, target_type="resolution", priority="urgent", target_hours=Decimal("4")),
    ]
    policy.calendar = None
    return policy


@pytest.fixture
def policy_default():
    """Default fallback SLA policy."""
    policy = MockSLAPolicy(
        id=3,
        name="Default SLA",
        is_active=True,
        is_default=True,
        priority=999,
        conditions=[],
    )
    policy.targets = [
        MockSLATarget(id=5, policy_id=3, target_type="first_response", priority=None, target_hours=Decimal("8")),
        MockSLATarget(id=6, policy_id=3, target_type="resolution", priority=None, target_hours=Decimal("48")),
    ]
    policy.calendar = None
    return policy


@pytest.fixture
def business_hours_calendar():
    """Business hours calendar (9-5, Mon-Fri)."""
    return MockBusinessCalendar(
        id=1,
        name="Business Hours",
        calendar_type="business_hours",
        schedule={
            "mon": {"start": "09:00", "end": "17:00"},
            "tue": {"start": "09:00", "end": "17:00"},
            "wed": {"start": "09:00", "end": "17:00"},
            "thu": {"start": "09:00", "end": "17:00"},
            "fri": {"start": "09:00", "end": "17:00"},
        },
    )


@pytest.fixture
def twenty_four_seven_calendar():
    """24x7 calendar."""
    return MockBusinessCalendar(
        id=2,
        name="24x7",
        calendar_type="24x7",
        schedule=None,
    )


# =============================================================================
# POLICY MATCHING TESTS
# =============================================================================


class TestGetApplicablePolicy:
    """Tests for get_applicable_policy method."""

    def test_matches_policy_by_priority(
        self, sla_engine, mock_db, ticket_medium, policy_standard
    ):
        """Test policy matching by ticket priority."""
        with patch.object(mock_db, 'query') as mock_query:
            # Mock active policies query
            mock_policy_query = MagicMock()
            mock_policy_query.filter.return_value.order_by.return_value.all.return_value = [policy_standard]
            mock_query.return_value = mock_policy_query

            result = sla_engine.get_applicable_policy(ticket_medium)

        assert result is not None
        assert result.id == 1
        assert result.name == "Standard SLA"

    def test_returns_first_matching_policy_by_priority(
        self, sla_engine, mock_db, ticket_urgent, policy_standard, policy_urgent
    ):
        """Test that higher priority policy is returned first."""
        with patch.object(mock_db, 'query') as mock_query:
            # Policies sorted by priority (urgent = 50 < standard = 100)
            mock_policy_query = MagicMock()
            mock_policy_query.filter.return_value.order_by.return_value.all.return_value = [
                policy_urgent, policy_standard  # Urgent first
            ]
            mock_query.return_value = mock_policy_query

            result = sla_engine.get_applicable_policy(ticket_urgent)

        assert result.id == 2
        assert result.name == "Urgent SLA"

    def test_returns_default_policy_when_no_match(
        self, sla_engine, mock_db, ticket_medium, policy_default
    ):
        """Test fallback to default policy when no conditions match."""
        with patch.object(mock_db, 'query') as mock_query:
            def query_side_effect(model):
                mock_q = MagicMock()
                # First call: active policies - return empty
                if not hasattr(query_side_effect, 'called'):
                    query_side_effect.called = True
                    mock_q.filter.return_value.order_by.return_value.all.return_value = []
                # Second call: default policy
                else:
                    mock_q.filter.return_value.first.return_value = policy_default
                return mock_q

            mock_query.side_effect = query_side_effect

            result = sla_engine.get_applicable_policy(ticket_medium)

        assert result is not None
        assert result.is_default is True

    def test_returns_none_when_no_policy(self, sla_engine, mock_db, ticket_medium):
        """Test returns None when no policies exist."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_policy_query = MagicMock()
            mock_policy_query.filter.return_value.order_by.return_value.all.return_value = []
            mock_policy_query.filter.return_value.first.return_value = None
            mock_query.return_value = mock_policy_query

            result = sla_engine.get_applicable_policy(ticket_medium)

        assert result is None


class TestMatchesPolicyConditions:
    """Tests for _matches_policy_conditions method."""

    def test_empty_conditions_returns_false(self, sla_engine, ticket_medium):
        """Test empty conditions don't match (only for defaults)."""
        policy = MockSLAPolicy(id=1, conditions=[])

        result = sla_engine._matches_policy_conditions(policy, ticket_medium)

        assert result is False

    def test_single_condition_match(self, sla_engine, ticket_medium, policy_standard):
        """Test single condition matching."""
        result = sla_engine._matches_policy_conditions(policy_standard, ticket_medium)

        assert result is True

    def test_single_condition_no_match(self, sla_engine, ticket_urgent, policy_standard):
        """Test single condition not matching."""
        # policy_standard requires priority == "medium", ticket_urgent has "urgent"
        result = sla_engine._matches_policy_conditions(policy_standard, ticket_urgent)

        assert result is False

    def test_multiple_conditions_all_must_match(self, sla_engine, ticket_urgent):
        """Test all conditions must match (AND logic)."""
        policy = MockSLAPolicy(
            id=1,
            conditions=[
                {"field": "priority", "operator": "equals", "value": "urgent"},
                {"field": "ticket_type", "operator": "equals", "value": "technical"},
            ],
        )

        result = sla_engine._matches_policy_conditions(policy, ticket_urgent)

        assert result is True

    def test_multiple_conditions_one_fails(self, sla_engine, ticket_urgent):
        """Test fails if any condition doesn't match."""
        policy = MockSLAPolicy(
            id=1,
            conditions=[
                {"field": "priority", "operator": "equals", "value": "urgent"},
                {"field": "ticket_type", "operator": "equals", "value": "billing"},  # Won't match
            ],
        )

        result = sla_engine._matches_policy_conditions(policy, ticket_urgent)

        assert result is False


class TestEvaluateCondition:
    """Tests for _evaluate_condition method."""

    def test_equals_operator(self, sla_engine):
        """Test equals operator."""
        assert sla_engine._evaluate_condition("medium", "equals", "medium") is True
        assert sla_engine._evaluate_condition("high", "equals", "medium") is False

    def test_not_equals_operator(self, sla_engine):
        """Test not_equals operator."""
        assert sla_engine._evaluate_condition("high", "not_equals", "medium") is True
        assert sla_engine._evaluate_condition("medium", "not_equals", "medium") is False

    def test_contains_operator(self, sla_engine):
        """Test contains operator."""
        assert sla_engine._evaluate_condition("network outage", "contains", "outage") is True
        assert sla_engine._evaluate_condition("network issue", "contains", "outage") is False

    def test_not_contains_operator(self, sla_engine):
        """Test not_contains operator."""
        assert sla_engine._evaluate_condition("network issue", "not_contains", "outage") is True
        assert sla_engine._evaluate_condition("network outage", "not_contains", "outage") is False

    def test_in_list_operator(self, sla_engine):
        """Test in_list operator."""
        assert sla_engine._evaluate_condition("urgent", "in_list", ["urgent", "high"]) is True
        assert sla_engine._evaluate_condition("low", "in_list", ["urgent", "high"]) is False

    def test_not_in_list_operator(self, sla_engine):
        """Test not_in_list operator."""
        assert sla_engine._evaluate_condition("low", "not_in_list", ["urgent", "high"]) is True
        assert sla_engine._evaluate_condition("urgent", "not_in_list", ["urgent", "high"]) is False

    def test_is_empty_operator(self, sla_engine):
        """Test is_empty operator."""
        assert sla_engine._evaluate_condition(None, "is_empty", None) is True
        assert sla_engine._evaluate_condition("", "is_empty", None) is True
        assert sla_engine._evaluate_condition("value", "is_empty", None) is False

    def test_is_not_empty_operator(self, sla_engine):
        """Test is_not_empty operator."""
        assert sla_engine._evaluate_condition("value", "is_not_empty", None) is True
        assert sla_engine._evaluate_condition(None, "is_not_empty", None) is False
        assert sla_engine._evaluate_condition("", "is_not_empty", None) is False

    def test_greater_than_operator(self, sla_engine):
        """Test greater_than operator."""
        assert sla_engine._evaluate_condition(10, "greater_than", 5) is True
        assert sla_engine._evaluate_condition(5, "greater_than", 10) is False
        assert sla_engine._evaluate_condition("abc", "greater_than", 5) is False

    def test_less_than_operator(self, sla_engine):
        """Test less_than operator."""
        assert sla_engine._evaluate_condition(5, "less_than", 10) is True
        assert sla_engine._evaluate_condition(10, "less_than", 5) is False

    def test_unknown_operator_returns_false(self, sla_engine):
        """Test unknown operator returns False."""
        assert sla_engine._evaluate_condition("value", "unknown_op", "value") is False


# =============================================================================
# TARGET TIME CALCULATION TESTS
# =============================================================================


class TestCalculateTargetTime:
    """Tests for calculate_target_time method."""

    def test_24x7_simple_addition(self, sla_engine, twenty_four_seven_calendar):
        """Test 24x7 calendar uses simple hour addition."""
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        target_hours = Decimal("4")

        result = sla_engine.calculate_target_time(start, target_hours, twenty_four_seven_calendar)

        expected = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_no_calendar_uses_24x7(self, sla_engine):
        """Test None calendar uses 24x7 calculation."""
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        target_hours = Decimal("8")

        result = sla_engine.calculate_target_time(start, target_hours, None)

        expected = datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_business_hours_within_same_day(self, sla_engine, mock_db, business_hours_calendar):
        """Test business hours calculation within same day."""
        # Monday 10:00, 4 hours target should be 14:00 same day
        start = datetime(2024, 1, 15, 10, 0)  # Monday
        target_hours = Decimal("4")

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        expected = datetime(2024, 1, 15, 14, 0)
        assert result == expected

    def test_business_hours_spans_multiple_days(self, sla_engine, mock_db, business_hours_calendar):
        """Test business hours calculation spanning multiple days."""
        # Monday 15:00 (2h left), 10 hours target = Tue 17:00
        start = datetime(2024, 1, 15, 15, 0)  # Monday 3pm
        target_hours = Decimal("10")  # 2h Mon + 8h Tue

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        expected = datetime(2024, 1, 16, 17, 0)
        assert result == expected

    def test_business_hours_skips_weekend(self, sla_engine, mock_db, business_hours_calendar):
        """Test business hours skips weekend days."""
        # Friday 16:00 (1h left), 4 hours target
        start = datetime(2024, 1, 19, 16, 0)  # Friday 4pm
        target_hours = Decimal("4")  # 1h Fri + 3h Mon

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        # Should be Monday 12:00 (9:00 + 3h remaining)
        expected = datetime(2024, 1, 22, 12, 0)
        assert result == expected

    def test_start_before_business_hours(self, sla_engine, mock_db, business_hours_calendar):
        """Test start time before business hours moves to start."""
        start = datetime(2024, 1, 15, 7, 0)  # 7am before 9am start
        target_hours = Decimal("2")

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        expected = datetime(2024, 1, 15, 11, 0)  # 9am + 2h
        assert result == expected

    def test_start_after_business_hours(self, sla_engine, mock_db, business_hours_calendar):
        """Test start time after business hours moves to next day."""
        start = datetime(2024, 1, 15, 18, 0)  # 6pm after 5pm end
        target_hours = Decimal("2")

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        expected = datetime(2024, 1, 16, 11, 0)  # Next day 9am + 2h
        assert result == expected


class TestBusinessHoursWithHolidays:
    """Tests for business hours with holidays."""

    def test_skips_fixed_holiday(self, sla_engine, mock_db, business_hours_calendar):
        """Test calculation skips fixed holidays."""
        start = datetime(2024, 12, 24, 16, 0)  # Dec 24 4pm, 1h left
        target_hours = Decimal("4")

        # Dec 25 is a holiday
        holidays = [date(2024, 12, 25)]
        with patch.object(sla_engine, '_get_holidays', return_value=(holidays, [])):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        # Should skip Dec 25, continue on Dec 26
        expected = datetime(2024, 12, 26, 12, 0)  # 1h Dec24 + 3h Dec26
        assert result == expected

    def test_skips_recurring_holiday(self, sla_engine, mock_db, business_hours_calendar):
        """Test calculation skips recurring holidays."""
        start = datetime(2024, 12, 24, 16, 0)
        target_hours = Decimal("4")

        # Christmas is recurring
        recurring = [(12, 25)]  # (month, day)
        with patch.object(sla_engine, '_get_holidays', return_value=([], recurring)):
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        expected = datetime(2024, 12, 26, 12, 0)
        assert result == expected


# =============================================================================
# ELAPSED BUSINESS HOURS TESTS
# =============================================================================


class TestCalculateElapsedBusinessHours:
    """Tests for calculate_elapsed_business_hours method."""

    def test_24x7_simple_difference(self, sla_engine):
        """Test 24x7 uses simple time difference."""
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)

        result = sla_engine.calculate_elapsed_business_hours(start, end, None)

        assert result == 4.0

    def test_business_hours_same_day(self, sla_engine, mock_db, business_hours_calendar):
        """Test elapsed hours within same business day."""
        start = datetime(2024, 1, 15, 10, 0)
        end = datetime(2024, 1, 15, 14, 0)

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_elapsed_business_hours(start, end, business_hours_calendar)

        assert result == 4.0

    def test_business_hours_excludes_after_hours(self, sla_engine, mock_db, business_hours_calendar):
        """Test elapsed hours excludes after-hours time."""
        start = datetime(2024, 1, 15, 16, 0)  # Mon 4pm
        end = datetime(2024, 1, 16, 10, 0)  # Tue 10am

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            result = sla_engine.calculate_elapsed_business_hours(start, end, business_hours_calendar)

        # 1h Mon (4-5pm) + 1h Tue (9-10am) = 2h
        assert result == 2.0


# =============================================================================
# SLA STATUS TESTS
# =============================================================================


class TestCheckSLAStatus:
    """Tests for check_sla_status method."""

    def test_pending_first_response(self, sla_engine, mock_db, ticket_with_sla):
        """Test status for pending first response."""
        now = datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)

        with patch.object(sla_engine, 'get_applicable_policy', return_value=None):
            with patch('app.services.sla_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value = now

                result = sla_engine.check_sla_status(ticket_with_sla)

        assert result["first_response"]["status"] == "pending"
        assert result["first_response"]["hours_remaining"] == 2.0  # 11:00 to 13:00
        assert result["first_response"]["breached"] is False

    def test_breached_first_response(self, sla_engine, mock_db, ticket_with_sla):
        """Test status for breached first response."""
        now = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)  # Past 13:00 deadline

        with patch.object(sla_engine, 'get_applicable_policy', return_value=None):
            with patch('app.services.sla_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value = now

                result = sla_engine.check_sla_status(ticket_with_sla)

        assert result["first_response"]["breached"] is True
        assert result["first_response"]["hours_remaining"] < 0

    def test_completed_first_response(self, sla_engine, mock_db, ticket_with_sla):
        """Test status for completed first response."""
        ticket_with_sla.first_responded_on = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        with patch.object(sla_engine, 'get_applicable_policy', return_value=None):
            with patch.object(sla_engine, 'calculate_elapsed_business_hours', return_value=3.0):
                result = sla_engine.check_sla_status(ticket_with_sla)

        assert result["first_response"]["status"] == "completed"
        assert result["first_response"]["breached"] is False  # Responded before deadline
        assert result["first_response"]["elapsed_hours"] == 3.0

    def test_warning_threshold(self, sla_engine, mock_db, ticket_with_sla):
        """Test warning flag when approaching deadline."""
        now = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)  # 30 min before deadline

        with patch.object(sla_engine, 'get_applicable_policy', return_value=None):
            with patch('app.services.sla_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value = now

                result = sla_engine.check_sla_status(ticket_with_sla)

        assert result["first_response"]["warning"] is True  # Less than 1 hour remaining


# =============================================================================
# FIND WARNINGS AND BREACHES TESTS
# =============================================================================


class TestFindSLAWarnings:
    """Tests for find_sla_warnings method."""

    def test_finds_approaching_first_response(self, sla_engine, mock_db, ticket_with_sla):
        """Test finding tickets approaching first response deadline."""
        now = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)

        with patch('app.services.sla_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value = now

            with patch.object(mock_db, 'query') as mock_query:
                mock_ticket_query = MagicMock()
                mock_ticket_query.filter.return_value.all.return_value = [ticket_with_sla]
                mock_query.return_value = mock_ticket_query

                result = sla_engine.find_sla_warnings(threshold_minutes=60)

        assert len(result) == 1
        assert result[0].id == 3

    def test_deduplicates_warnings(self, sla_engine, mock_db, ticket_with_sla):
        """Test warnings are deduplicated."""
        now = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)

        with patch('app.services.sla_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value = now

            with patch.object(mock_db, 'query') as mock_query:
                mock_ticket_query = MagicMock()
                # Same ticket appears in both response and resolution warnings
                mock_ticket_query.filter.return_value.all.side_effect = [
                    [ticket_with_sla],  # Response warnings
                    [ticket_with_sla],  # Resolution warnings
                ]
                mock_query.return_value = mock_ticket_query

                result = sla_engine.find_sla_warnings(threshold_minutes=60)

        # Should only appear once
        assert len(result) == 1


class TestFindSLABreaches:
    """Tests for find_sla_breaches method."""

    def test_finds_first_response_breaches(self, sla_engine, mock_db, ticket_with_sla):
        """Test finding first response breaches."""
        now = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)  # Past deadline

        with patch('app.services.sla_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value = now

            with patch.object(mock_db, 'query') as mock_query:
                mock_ticket_query = MagicMock()
                mock_ticket_query.filter.return_value.all.side_effect = [
                    [ticket_with_sla],  # Response breaches
                    [],  # Resolution breaches
                ]
                mock_query.return_value = mock_ticket_query

                result = sla_engine.find_sla_breaches()

        assert len(result) == 1
        assert result[0] == (ticket_with_sla, "first_response")

    def test_finds_resolution_breaches(self, sla_engine, mock_db, ticket_with_sla):
        """Test finding resolution breaches."""
        now = datetime(2024, 1, 17, 10, 0, tzinfo=timezone.utc)  # Past resolution deadline
        ticket_with_sla.first_responded_on = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        with patch('app.services.sla_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value = now

            with patch.object(mock_db, 'query') as mock_query:
                mock_ticket_query = MagicMock()
                mock_ticket_query.filter.return_value.all.side_effect = [
                    [],  # Response breaches
                    [ticket_with_sla],  # Resolution breaches
                ]
                mock_query.return_value = mock_ticket_query

                result = sla_engine.find_sla_breaches()

        assert len(result) == 1
        assert result[0] == (ticket_with_sla, "resolution")


# =============================================================================
# LOG BREACH TESTS
# =============================================================================


class TestLogBreach:
    """Tests for log_breach method."""

    def test_creates_breach_log(self, sla_engine, mock_db, ticket_with_sla, policy_standard):
        """Test breach log creation."""
        with patch.object(sla_engine, 'get_applicable_policy', return_value=policy_standard):
            breach = sla_engine.log_breach(
                ticket=ticket_with_sla,
                target_type="first_response",
                target_hours=Decimal("4"),
                actual_hours=Decimal("5.5"),
            )

        assert len(mock_db._added) == 1
        assert mock_db._committed is True


# =============================================================================
# UPDATE TICKET SLA TESTS
# =============================================================================


class TestUpdateTicketSLA:
    """Tests for update_ticket_sla method."""

    def test_applies_sla_targets_to_ticket(
        self, sla_engine, mock_db, ticket_medium, policy_standard
    ):
        """Test SLA targets are applied to ticket."""
        with patch.object(sla_engine, 'get_applicable_policy', return_value=policy_standard):
            with patch.object(sla_engine, 'get_target_for_ticket') as mock_get_target:
                response_target = MockSLATarget(
                    id=1, policy_id=1, target_type="first_response", target_hours=Decimal("4")
                )
                resolution_target = MockSLATarget(
                    id=2, policy_id=1, target_type="resolution", target_hours=Decimal("24")
                )
                mock_get_target.side_effect = [response_target, resolution_target]

                result = sla_engine.update_ticket_sla(ticket_medium)

        assert result["policy_id"] == 1
        assert len(result["targets_set"]) == 2
        assert ticket_medium.response_by is not None
        assert ticket_medium.resolution_by is not None

    def test_no_policy_returns_not_applied(self, sla_engine, mock_db, ticket_medium):
        """Test no policy returns not applied message."""
        with patch.object(sla_engine, 'get_applicable_policy', return_value=None):
            result = sla_engine.update_ticket_sla(ticket_medium)

        assert result["policy_applied"] is False
        assert "No applicable SLA policy" in result["message"]


# =============================================================================
# GET TARGET FOR TICKET TESTS
# =============================================================================


class TestGetTargetForTicket:
    """Tests for get_target_for_ticket method."""

    def test_returns_priority_specific_target(
        self, sla_engine, ticket_medium, policy_standard
    ):
        """Test returns target matching ticket priority."""
        result = sla_engine.get_target_for_ticket(
            policy_standard, ticket_medium, MockSLATargetType.FIRST_RESPONSE
        )

        assert result is not None
        assert result.priority == "medium"
        assert result.target_hours == Decimal("4")

    def test_falls_back_to_no_priority_target(self, sla_engine, ticket_medium):
        """Test falls back to target without priority restriction."""
        policy = MockSLAPolicy(id=1, conditions=[])
        policy.targets = [
            MockSLATarget(id=1, policy_id=1, target_type="first_response", priority=None, target_hours=Decimal("8"))
        ]

        result = sla_engine.get_target_for_ticket(
            policy, ticket_medium, MockSLATargetType.FIRST_RESPONSE
        )

        assert result is not None
        assert result.priority is None
        assert result.target_hours == Decimal("8")

    def test_returns_none_when_no_matching_target(self, sla_engine, ticket_medium):
        """Test returns None when no target matches."""
        policy = MockSLAPolicy(id=1, conditions=[])
        policy.targets = [
            MockSLATarget(id=1, policy_id=1, target_type="resolution", priority="high", target_hours=Decimal("24"))
        ]

        result = sla_engine.get_target_for_ticket(
            policy, ticket_medium, MockSLATargetType.FIRST_RESPONSE
        )

        assert result is None


# =============================================================================
# PROCESS SLA CHECKS TESTS
# =============================================================================


class TestProcessSLAChecks:
    """Tests for process_sla_checks scheduled task."""

    def test_processes_warnings_and_breaches(
        self, sla_engine, mock_db, ticket_with_sla, policy_standard
    ):
        """Test scheduled task processes warnings and breaches."""
        with patch.object(sla_engine, 'find_sla_warnings', return_value=[ticket_with_sla]):
            with patch.object(sla_engine, 'find_sla_breaches', return_value=[]):
                result = sla_engine.process_sla_checks()

        assert result["warnings_found"] == 1
        assert result["breaches_found"] == 0

    def test_logs_new_breaches(
        self, sla_engine, mock_db, ticket_with_sla, policy_standard
    ):
        """Test logs breaches that haven't been logged yet."""
        response_target = MockSLATarget(
            id=1, policy_id=1, target_type="first_response", target_hours=Decimal("4")
        )

        with patch.object(sla_engine, 'find_sla_warnings', return_value=[]):
            with patch.object(sla_engine, 'find_sla_breaches', return_value=[(ticket_with_sla, "first_response")]):
                with patch.object(mock_db, 'query') as mock_query:
                    # No existing breach log
                    mock_breach_query = MagicMock()
                    mock_breach_query.filter.return_value.first.return_value = None
                    mock_query.return_value = mock_breach_query

                    with patch.object(sla_engine, 'get_applicable_policy', return_value=policy_standard):
                        with patch.object(sla_engine, 'get_target_for_ticket', return_value=response_target):
                            with patch.object(sla_engine, 'log_breach') as mock_log:
                                result = sla_engine.process_sla_checks()

        assert result["breaches_logged"] == 1
        mock_log.assert_called_once()

    def test_skips_already_logged_breaches(
        self, sla_engine, mock_db, ticket_with_sla
    ):
        """Test doesn't re-log existing breaches."""
        existing_breach = MockSLABreachLog(id=1, ticket_id=3, target_type="first_response")

        with patch.object(sla_engine, 'find_sla_warnings', return_value=[]):
            with patch.object(sla_engine, 'find_sla_breaches', return_value=[(ticket_with_sla, "first_response")]):
                with patch.object(mock_db, 'query') as mock_query:
                    mock_breach_query = MagicMock()
                    mock_breach_query.filter.return_value.first.return_value = existing_breach
                    mock_query.return_value = mock_breach_query

                    result = sla_engine.process_sla_checks()

        assert result["breaches_logged"] == 0


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_ticket_with_enum_priority(self, sla_engine, ticket_medium, policy_standard):
        """Test handling ticket with enum priority value."""
        # Ticket priority is MockTicketPriority.MEDIUM (enum)
        result = sla_engine._matches_policy_conditions(policy_standard, ticket_medium)

        assert result is True

    def test_condition_with_none_field_value(self, sla_engine, ticket_medium):
        """Test condition evaluation when ticket field is None."""
        policy = MockSLAPolicy(
            id=1,
            conditions=[
                {"field": "assigned_to", "operator": "is_empty", "value": None}
            ],
        )

        # ticket_medium.assigned_to is None
        result = sla_engine._matches_policy_conditions(policy, ticket_medium)

        assert result is True

    def test_zero_target_hours(self, sla_engine):
        """Test calculation with zero target hours."""
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        target_hours = Decimal("0")

        result = sla_engine.calculate_target_time(start, target_hours, None)

        assert result == start

    def test_very_large_target_hours(self, sla_engine, mock_db, business_hours_calendar):
        """Test calculation with very large target hours."""
        start = datetime(2024, 1, 15, 10, 0)
        target_hours = Decimal("1000")  # ~125 business days

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            # Should complete without infinite loop due to max_days limit
            result = sla_engine.calculate_target_time(start, target_hours, business_hours_calendar)

        assert result > start

    def test_calendar_with_empty_schedule(self, sla_engine, mock_db):
        """Test calendar with no business days defined."""
        calendar = MockBusinessCalendar(
            id=1,
            name="Empty Calendar",
            calendar_type="business_hours",
            schedule={},  # No days defined
        )

        start = datetime(2024, 1, 15, 10, 0)
        target_hours = Decimal("8")

        with patch.object(sla_engine, '_get_holidays', return_value=([], [])):
            # Should fall back to simple addition after max iterations
            result = sla_engine.calculate_target_time(start, target_hours, calendar)

        # Fallback behavior
        assert result is not None
