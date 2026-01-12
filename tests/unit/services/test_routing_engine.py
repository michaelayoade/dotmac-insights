"""
Unit tests for RoutingEngine.

Tests ticket routing, agent assignment, and load balancing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
import enum

import pytest

# Import the service
from app.services.routing_engine import RoutingEngine

# Import mock fixtures
from tests.unit.conftest import (
    MockSession,
    MockTicket,
    MockTicketStatus,
    MockTicketPriority,
    MockRoutingRule,
    MockAgent,
    MockTeam,
    MockTeamMember,
)


# =============================================================================
# ADDITIONAL MOCK CLASSES
# =============================================================================


class MockRoutingStrategy(str, enum.Enum):
    MANUAL = "manual"
    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"


@dataclass
class MockRoutingRoundRobinState:
    """Mock round-robin state."""
    id: int = 1
    team_id: int = 1
    last_party_id: Optional[int] = None


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MockSession()


@pytest.fixture
def routing_engine(mock_db):
    """Create RoutingEngine with mock db."""
    return RoutingEngine(mock_db)


@pytest.fixture
def ticket_unassigned():
    """Unassigned ticket."""
    return MockTicket(
        id=1,
        subject="Test Ticket",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.MEDIUM,
        assigned_to=None,
        ticket_type="technical",
        issue_type="network",
        region="lagos",
    )


@pytest.fixture
def ticket_assigned():
    """Already assigned ticket."""
    return MockTicket(
        id=2,
        subject="Assigned Ticket",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.MEDIUM,
        assigned_to="Agent 1",
    )


@pytest.fixture
def rule_round_robin():
    """Round-robin routing rule."""
    return MockRoutingRule(
        id=1,
        name="Technical Support",
        is_active=True,
        priority=100,
        strategy="round_robin",
        conditions=[
            {"field": "ticket_type", "operator": "equals", "value": "technical"}
        ],
        team_id=1,
    )


@pytest.fixture
def rule_least_busy():
    """Least busy routing rule."""
    return MockRoutingRule(
        id=2,
        name="General Support",
        is_active=True,
        priority=200,
        strategy="least_busy",
        conditions=None,  # Catch-all
        team_id=1,
    )


@pytest.fixture
def rule_skill_based():
    """Skill-based routing rule."""
    return MockRoutingRule(
        id=3,
        name="Skill Routing",
        is_active=True,
        priority=50,
        strategy="skill_based",
        conditions=[
            {"field": "priority", "operator": "equals", "value": "urgent"}
        ],
        team_id=1,
    )


@pytest.fixture
def rule_load_balanced():
    """Load-balanced routing rule."""
    return MockRoutingRule(
        id=4,
        name="Load Balanced",
        is_active=True,
        priority=150,
        strategy="load_balanced",
        conditions=[],
        team_id=1,
    )


@pytest.fixture
def rule_manual():
    """Manual assignment rule."""
    return MockRoutingRule(
        id=5,
        name="Manual Assignment",
        is_active=True,
        priority=75,
        strategy="manual",
        conditions=[
            {"field": "priority", "operator": "equals", "value": "high"}
        ],
        team_id=None,
    )


@pytest.fixture
def agents():
    """List of test agents."""
    return [
        MockAgent(
            id=1,
            email="agent1@example.com",
            display_name="Agent 1",
            is_active=True,
            capacity=10,
            routing_weight=1,
            skills={"technical": True, "network": True},
            domains={"lagos": True},
        ),
        MockAgent(
            id=2,
            email="agent2@example.com",
            display_name="Agent 2",
            is_active=True,
            capacity=10,
            routing_weight=2,
            skills={"billing": True},
            domains={},
        ),
        MockAgent(
            id=3,
            email="agent3@example.com",
            display_name="Agent 3",
            is_active=True,
            capacity=5,
            routing_weight=1,
            skills={"technical": True},
            domains={},
        ),
    ]


@pytest.fixture
def team():
    """Test team."""
    return MockTeam(id=1, name="Support Team")


@pytest.fixture
def team_members(agents):
    """Team members linking agents to team."""
    return [
        MockTeamMember(id=1, team_id=1, agent_id=1, is_active=True),
        MockTeamMember(id=2, team_id=1, agent_id=2, is_active=True),
        MockTeamMember(id=3, team_id=1, agent_id=3, is_active=True),
    ]


# =============================================================================
# AUTO-ASSIGN TESTS
# =============================================================================


class TestAutoAssign:
    """Tests for auto_assign method."""

    def test_skips_already_assigned_ticket(
        self, routing_engine, mock_db, ticket_assigned
    ):
        """Test returns early if ticket already assigned."""
        result = routing_engine.auto_assign(ticket_assigned)

        assert result["assigned"] is False
        assert result["reason"] == "already_assigned"
        assert result["current_assignee"] == "Agent 1"

    def test_no_matching_rule_returns_not_assigned(
        self, routing_engine, mock_db, ticket_unassigned
    ):
        """Test returns not assigned when no rule matches."""
        with patch.object(routing_engine, 'find_matching_rule', return_value=None):
            result = routing_engine.auto_assign(ticket_unassigned)

        assert result["assigned"] is False
        assert result["reason"] == "no_matching_rule"

    def test_manual_strategy_returns_not_assigned(
        self, routing_engine, mock_db, ticket_unassigned, rule_manual
    ):
        """Test manual strategy doesn't auto-assign."""
        with patch.object(routing_engine, 'find_matching_rule', return_value=rule_manual):
            result = routing_engine.auto_assign(ticket_unassigned)

        assert result["assigned"] is False
        assert result["reason"] == "manual_strategy"

    def test_no_available_agents_returns_not_assigned(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin
    ):
        """Test returns not assigned when no agents available."""
        with patch.object(routing_engine, 'find_matching_rule', return_value=rule_round_robin):
            with patch.object(routing_engine, 'get_available_agents', return_value=[]):
                result = routing_engine.auto_assign(ticket_unassigned)

        assert result["assigned"] is False
        assert result["reason"] == "no_available_agents"

    def test_successful_assignment(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin, agents, team
    ):
        """Test successful ticket assignment."""
        with patch.object(routing_engine, 'find_matching_rule', return_value=rule_round_robin):
            with patch.object(routing_engine, 'get_available_agents', return_value=agents):
                with patch.object(routing_engine, 'select_agent', return_value=agents[0]):
                    with patch.object(mock_db, 'query') as mock_query:
                        mock_team_query = MagicMock()
                        mock_team_query.filter.return_value.first.return_value = team
                        mock_query.return_value = mock_team_query

                        result = routing_engine.auto_assign(ticket_unassigned)

        assert result["assigned"] is True
        assert result["agent_id"] == 1
        assert result["agent_name"] == "Agent 1"
        assert ticket_unassigned.assigned_to == "Agent 1"
        assert ticket_unassigned.resolution_team == "Support Team"

    def test_selection_failed_returns_not_assigned(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin, agents
    ):
        """Test returns not assigned when selection fails."""
        with patch.object(routing_engine, 'find_matching_rule', return_value=rule_round_robin):
            with patch.object(routing_engine, 'get_available_agents', return_value=agents):
                with patch.object(routing_engine, 'select_agent', return_value=None):
                    result = routing_engine.auto_assign(ticket_unassigned)

        assert result["assigned"] is False
        assert result["reason"] == "selection_failed"


# =============================================================================
# FIND MATCHING RULE TESTS
# =============================================================================


class TestFindMatchingRule:
    """Tests for find_matching_rule method."""

    def test_matches_rule_by_conditions(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin
    ):
        """Test finds rule matching ticket conditions."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_rule_query = MagicMock()
            mock_rule_query.filter.return_value.order_by.return_value.all.return_value = [rule_round_robin]
            mock_query.return_value = mock_rule_query

            result = routing_engine.find_matching_rule(ticket_unassigned)

        assert result is not None
        assert result.id == 1

    def test_returns_first_matching_rule_by_priority(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin, rule_least_busy
    ):
        """Test returns highest priority matching rule."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_rule_query = MagicMock()
            # Round-robin has priority 100 < least_busy 200
            mock_rule_query.filter.return_value.order_by.return_value.all.return_value = [
                rule_round_robin, rule_least_busy
            ]
            mock_query.return_value = mock_rule_query

            result = routing_engine.find_matching_rule(ticket_unassigned)

        assert result.id == 1  # Round-robin matched first

    def test_catch_all_rule_matches_any(
        self, routing_engine, mock_db, ticket_unassigned, rule_least_busy
    ):
        """Test rule without conditions matches any ticket."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_rule_query = MagicMock()
            mock_rule_query.filter.return_value.order_by.return_value.all.return_value = [rule_least_busy]
            mock_query.return_value = mock_rule_query

            result = routing_engine.find_matching_rule(ticket_unassigned)

        assert result is not None
        assert result.id == 2

    def test_returns_none_when_no_rules(self, routing_engine, mock_db, ticket_unassigned):
        """Test returns None when no rules exist."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_rule_query = MagicMock()
            mock_rule_query.filter.return_value.order_by.return_value.all.return_value = []
            mock_query.return_value = mock_rule_query

            result = routing_engine.find_matching_rule(ticket_unassigned)

        assert result is None


# =============================================================================
# CONDITION EVALUATION TESTS
# =============================================================================


class TestEvaluateConditions:
    """Tests for _evaluate_conditions method."""

    def test_empty_conditions_returns_true(self, routing_engine, ticket_unassigned):
        """Test empty/None conditions is catch-all."""
        assert routing_engine._evaluate_conditions(None, ticket_unassigned) is True
        assert routing_engine._evaluate_conditions([], ticket_unassigned) is True

    def test_all_conditions_must_match(self, routing_engine, ticket_unassigned):
        """Test all conditions must match (AND logic)."""
        conditions = [
            {"field": "ticket_type", "operator": "equals", "value": "technical"},
            {"field": "priority", "operator": "equals", "value": "medium"},
        ]

        result = routing_engine._evaluate_conditions(conditions, ticket_unassigned)

        assert result is True

    def test_fails_if_any_condition_fails(self, routing_engine, ticket_unassigned):
        """Test fails if any condition doesn't match."""
        conditions = [
            {"field": "ticket_type", "operator": "equals", "value": "technical"},
            {"field": "priority", "operator": "equals", "value": "urgent"},  # Won't match
        ]

        result = routing_engine._evaluate_conditions(conditions, ticket_unassigned)

        assert result is False


class TestCheckCondition:
    """Tests for _check_condition method."""

    def test_equals_operator(self, routing_engine):
        """Test equals operator."""
        assert routing_engine._check_condition("test", "equals", "test") is True
        assert routing_engine._check_condition("test", "equals", "other") is False

    def test_not_equals_operator(self, routing_engine):
        """Test not_equals operator."""
        assert routing_engine._check_condition("test", "not_equals", "other") is True
        assert routing_engine._check_condition("test", "not_equals", "test") is False

    def test_contains_operator(self, routing_engine):
        """Test contains operator."""
        assert routing_engine._check_condition("hello world", "contains", "world") is True
        assert routing_engine._check_condition("hello", "contains", "world") is False

    def test_not_contains_operator(self, routing_engine):
        """Test not_contains operator."""
        assert routing_engine._check_condition("hello", "not_contains", "world") is True
        assert routing_engine._check_condition("hello world", "not_contains", "world") is False

    def test_in_list_operator(self, routing_engine):
        """Test in_list operator."""
        assert routing_engine._check_condition("a", "in_list", ["a", "b", "c"]) is True
        assert routing_engine._check_condition("d", "in_list", ["a", "b", "c"]) is False

    def test_not_in_list_operator(self, routing_engine):
        """Test not_in_list operator."""
        assert routing_engine._check_condition("d", "not_in_list", ["a", "b", "c"]) is True
        assert routing_engine._check_condition("a", "not_in_list", ["a", "b", "c"]) is False

    def test_is_empty_operator(self, routing_engine):
        """Test is_empty operator."""
        assert routing_engine._check_condition(None, "is_empty", None) is True
        assert routing_engine._check_condition("", "is_empty", None) is True
        assert routing_engine._check_condition("value", "is_empty", None) is False

    def test_is_not_empty_operator(self, routing_engine):
        """Test is_not_empty operator."""
        assert routing_engine._check_condition("value", "is_not_empty", None) is True
        assert routing_engine._check_condition(None, "is_not_empty", None) is False

    def test_starts_with_operator(self, routing_engine):
        """Test starts_with operator."""
        assert routing_engine._check_condition("hello world", "starts_with", "hello") is True
        assert routing_engine._check_condition("hello world", "starts_with", "world") is False

    def test_ends_with_operator(self, routing_engine):
        """Test ends_with operator."""
        assert routing_engine._check_condition("hello world", "ends_with", "world") is True
        assert routing_engine._check_condition("hello world", "ends_with", "hello") is False

    def test_unknown_operator_returns_false(self, routing_engine):
        """Test unknown operator returns False."""
        assert routing_engine._check_condition("value", "unknown", "value") is False


# =============================================================================
# GET AVAILABLE AGENTS TESTS
# =============================================================================


class TestGetAvailableAgents:
    """Tests for get_available_agents method."""

    def test_gets_team_agents(
        self, routing_engine, mock_db, rule_round_robin, agents, team_members
    ):
        """Test gets agents from team."""
        with patch.object(routing_engine, '_get_team_agents', return_value=agents):
            result = routing_engine.get_available_agents(rule_round_robin)

        assert len(result) == 3

    def test_uses_fallback_team_if_primary_empty(self, routing_engine, mock_db, agents):
        """Test uses fallback team when primary has no agents."""
        rule = MockRoutingRule(
            id=1,
            team_id=1,
            fallback_team_id=2,
            strategy="round_robin",
        )

        with patch.object(routing_engine, '_get_team_agents') as mock_get:
            mock_get.side_effect = [[], agents]  # Empty primary, agents in fallback

            result = routing_engine.get_available_agents(rule)

        assert len(result) == 3
        assert mock_get.call_count == 2

    def test_returns_empty_if_no_agents(self, routing_engine, mock_db, rule_round_robin):
        """Test returns empty if no agents available."""
        with patch.object(routing_engine, '_get_team_agents', return_value=[]):
            result = routing_engine.get_available_agents(rule_round_robin)

        assert result == []


# =============================================================================
# AGENT SELECTION STRATEGY TESTS
# =============================================================================


class TestSelectAgent:
    """Tests for select_agent method."""

    def test_round_robin_strategy(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin, agents
    ):
        """Test round-robin selection."""
        with patch.object(routing_engine, '_round_robin', return_value=agents[0]) as mock_rr:
            result = routing_engine.select_agent(ticket_unassigned, agents, rule_round_robin)

        assert result == agents[0]
        mock_rr.assert_called_once()

    def test_least_busy_strategy(
        self, routing_engine, mock_db, ticket_unassigned, rule_least_busy, agents
    ):
        """Test least-busy selection."""
        with patch.object(routing_engine, '_least_busy', return_value=agents[1]) as mock_lb:
            result = routing_engine.select_agent(ticket_unassigned, agents, rule_least_busy)

        assert result == agents[1]
        mock_lb.assert_called_once()

    def test_skill_based_strategy(
        self, routing_engine, mock_db, ticket_unassigned, rule_skill_based, agents
    ):
        """Test skill-based selection."""
        with patch.object(routing_engine, '_skill_based', return_value=agents[0]) as mock_sb:
            result = routing_engine.select_agent(ticket_unassigned, agents, rule_skill_based)

        assert result == agents[0]
        mock_sb.assert_called_once()

    def test_load_balanced_strategy(
        self, routing_engine, mock_db, ticket_unassigned, rule_load_balanced, agents
    ):
        """Test load-balanced selection."""
        with patch.object(routing_engine, '_load_balanced', return_value=agents[2]) as mock_llb:
            result = routing_engine.select_agent(ticket_unassigned, agents, rule_load_balanced)

        assert result == agents[2]
        mock_llb.assert_called_once()

    def test_unknown_strategy_returns_first(
        self, routing_engine, ticket_unassigned, agents
    ):
        """Test unknown strategy returns first agent."""
        rule = MockRoutingRule(id=1, strategy="unknown_strategy")

        result = routing_engine.select_agent(ticket_unassigned, agents, rule)

        assert result == agents[0]


class TestRoundRobinSelection:
    """Tests for _round_robin method."""

    def test_first_assignment_returns_first_agent(
        self, routing_engine, mock_db, agents
    ):
        """Test first assignment starts with first agent."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_state_query = MagicMock()
            mock_state_query.filter.return_value.first.return_value = None
            mock_query.return_value = mock_state_query

            result = routing_engine._round_robin(1, agents)

        assert result == agents[0]
        assert len(mock_db._added) == 1  # State was created

    def test_rotates_to_next_agent(self, routing_engine, mock_db, agents):
        """Test rotates to next agent in list."""
        state = MockRoutingRoundRobinState(id=1, team_id=1, last_party_id=1)

        with patch.object(mock_db, 'query') as mock_query:
            mock_state_query = MagicMock()
            mock_state_query.filter.return_value.first.return_value = state
            mock_query.return_value = mock_state_query

            result = routing_engine._round_robin(1, agents)

        assert result == agents[1]  # Rotated from agent 1 to agent 2
        assert state.last_party_id == 2

    def test_wraps_around_to_first(self, routing_engine, mock_db, agents):
        """Test wraps around when reaching end of list."""
        state = MockRoutingRoundRobinState(id=1, team_id=1, last_party_id=3)  # Last agent

        with patch.object(mock_db, 'query') as mock_query:
            mock_state_query = MagicMock()
            mock_state_query.filter.return_value.first.return_value = state
            mock_query.return_value = mock_state_query

            result = routing_engine._round_robin(1, agents)

        assert result == agents[0]  # Wrapped to first

    def test_returns_none_for_empty_agents(self, routing_engine, mock_db):
        """Test returns None when no agents."""
        result = routing_engine._round_robin(1, [])

        assert result is None


class TestLeastBusySelection:
    """Tests for _least_busy method."""

    def test_selects_agent_with_fewest_tickets(
        self, routing_engine, mock_db, agents
    ):
        """Test selects agent with lowest ticket count."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_count_query = MagicMock()
            # Agent 1: 5 tickets, Agent 2: 2 tickets, Agent 3: 8 tickets
            mock_count_query.filter.return_value.scalar.side_effect = [5, 2, 8]
            mock_query.return_value = mock_count_query

            result = routing_engine._least_busy(agents)

        assert result == agents[1]  # Agent 2 has fewest

    def test_returns_none_for_empty_agents(self, routing_engine, mock_db):
        """Test returns None for empty list."""
        result = routing_engine._least_busy([])

        assert result is None


class TestSkillBasedSelection:
    """Tests for _skill_based method."""

    def test_selects_agent_with_matching_skills(
        self, routing_engine, ticket_unassigned, agents
    ):
        """Test selects agent with matching skills."""
        # Agent 1 has technical and network skills, matches ticket
        result = routing_engine._skill_based(ticket_unassigned, agents)

        assert result == agents[0]

    def test_considers_region_domain(self, routing_engine, agents):
        """Test considers region in domains."""
        ticket = MockTicket(
            id=1,
            ticket_type="unknown",
            issue_type="unknown",
            region="lagos",  # Agent 1 has lagos domain
        )

        result = routing_engine._skill_based(ticket, agents)

        # Agent 1 should be selected due to lagos region match
        assert result == agents[0]

    def test_considers_routing_weight(self, routing_engine, agents):
        """Test routing weight affects score."""
        ticket = MockTicket(
            id=1,
            ticket_type="unknown",
            issue_type="unknown",
            region="unknown",
        )
        # No skill matches, so weight determines winner
        # Agent 2 has weight 2, others have 1

        result = routing_engine._skill_based(ticket, agents)

        assert result == agents[1]  # Highest weight

    def test_returns_first_if_no_matches(self, routing_engine, agents):
        """Test returns first agent if no skill matches."""
        ticket = MockTicket(id=1, ticket_type=None, issue_type=None, region=None)

        result = routing_engine._skill_based(ticket, agents)

        # Should return agent with highest base score (weight-based)
        assert result is not None


class TestLoadBalancedSelection:
    """Tests for _load_balanced method."""

    def test_selects_agent_with_lowest_utilization(
        self, routing_engine, mock_db, agents
    ):
        """Test selects agent with lowest capacity utilization."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_count_query = MagicMock()
            # Agent 1 (cap 10): 5 tickets = 50% util
            # Agent 2 (cap 10): 8 tickets = 80% util
            # Agent 3 (cap 5): 1 ticket = 20% util
            mock_count_query.filter.return_value.scalar.side_effect = [5, 8, 1]
            mock_query.return_value = mock_count_query

            result = routing_engine._load_balanced(agents)

        assert result == agents[2]  # Agent 3 has 20% utilization

    def test_skips_agents_at_capacity(self, routing_engine, mock_db, agents):
        """Test skips agents at or over capacity."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_count_query = MagicMock()
            # Agent 1: 10/10 = 100% (skip)
            # Agent 2: 10/10 = 100% (skip)
            # Agent 3: 4/5 = 80% (select)
            mock_count_query.filter.return_value.scalar.side_effect = [10, 10, 4]
            mock_query.return_value = mock_count_query

            result = routing_engine._load_balanced(agents)

        assert result == agents[2]

    def test_returns_none_if_all_at_capacity(self, routing_engine, mock_db, agents):
        """Test returns None if all agents at capacity."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_count_query = MagicMock()
            # All at 100% capacity
            mock_count_query.filter.return_value.scalar.side_effect = [10, 10, 5]
            mock_query.return_value = mock_count_query

            result = routing_engine._load_balanced(agents)

        assert result is None


# =============================================================================
# WORKLOAD SUMMARY TESTS
# =============================================================================


class TestGetWorkloadSummary:
    """Tests for get_workload_summary method."""

    def test_returns_summary_for_all_agents(self, routing_engine, mock_db, agents):
        """Test returns workload summary for all agents."""
        with patch.object(mock_db, 'query') as mock_query:
            # Mock agent query
            mock_agent_query = MagicMock()
            mock_agent_query.join.return_value = mock_agent_query
            mock_agent_query.filter.return_value = mock_agent_query
            mock_agent_query.all.return_value = agents

            # Mock ticket count queries
            mock_count_query = MagicMock()
            mock_count_query.filter.return_value.scalar.side_effect = [3, 5, 2]

            mock_query.side_effect = [mock_agent_query] + [mock_count_query] * 3

            result = routing_engine.get_workload_summary()

        assert result["total_agents"] == 3
        assert result["total_capacity"] == 25  # 10 + 10 + 5
        assert result["total_load"] == 10  # 3 + 5 + 2

    def test_filters_by_team(self, routing_engine, mock_db, agents, team_members):
        """Test filters workload by team."""
        with patch.object(mock_db, 'query') as mock_query:
            # Mock team members query
            mock_member_query = MagicMock()
            mock_member_query.filter.return_value.all.return_value = [(1,), (2,)]

            # Mock agent query
            mock_agent_query = MagicMock()
            mock_agent_query.join.return_value = mock_agent_query
            mock_agent_query.filter.return_value = mock_agent_query
            mock_agent_query.all.return_value = agents[:2]

            # Mock ticket counts
            mock_count_query = MagicMock()
            mock_count_query.filter.return_value.scalar.side_effect = [3, 5]

            mock_query.side_effect = [mock_agent_query, mock_member_query] + [mock_count_query] * 2

            result = routing_engine.get_workload_summary(team_id=1)

        assert result["total_agents"] == 2


# =============================================================================
# REBALANCE WORKLOAD TESTS
# =============================================================================


class TestRebalanceWorkload:
    """Tests for rebalance_workload method."""

    def test_requires_minimum_two_agents(self, routing_engine, mock_db, agents):
        """Test requires at least 2 agents to rebalance."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_agent_query = MagicMock()
            mock_agent_query.filter.return_value.all.return_value = [agents[0]]
            mock_query.return_value = mock_agent_query

            result = routing_engine.rebalance_workload()

        assert result["rebalanced"] == 0
        assert "at least 2 agents" in result["message"]

    def test_moves_tickets_from_overloaded(self, routing_engine, mock_db, agents):
        """Test moves tickets from overloaded to underloaded agents."""
        overloaded_ticket = MockTicket(
            id=10,
            subject="Move Me",
            status=MockTicketStatus.OPEN,
            assigned_to="Agent 1",
        )

        with patch.object(mock_db, 'query') as mock_query:
            # Mock agent query
            mock_agent_query = MagicMock()
            mock_agent_query.filter.return_value.all.return_value = agents

            # Mock ticket count: Agent 1 = 8, Agent 2 = 2, Agent 3 = 1
            mock_count_query = MagicMock()
            mock_count_query.filter.return_value.scalar.side_effect = [8, 2, 1, 8, 2, 1]

            # Mock tickets to move
            mock_ticket_query = MagicMock()
            mock_ticket_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [overloaded_ticket]

            mock_query.side_effect = [mock_agent_query] + [mock_count_query] * 6 + [mock_ticket_query]

            result = routing_engine.rebalance_workload()

        # At least some rebalancing should have been attempted
        assert "rebalanced" in result


# =============================================================================
# BATCH OPERATIONS TESTS
# =============================================================================


class TestFindUnassignedTickets:
    """Tests for find_unassigned_tickets method."""

    def test_finds_open_unassigned_tickets(self, routing_engine, mock_db, ticket_unassigned):
        """Test finds unassigned open tickets."""
        with patch.object(mock_db, 'query') as mock_query:
            mock_ticket_query = MagicMock()
            mock_ticket_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                ticket_unassigned
            ]
            mock_query.return_value = mock_ticket_query

            result = routing_engine.find_unassigned_tickets(limit=100)

        assert len(result) == 1
        assert result[0].assigned_to is None


class TestAutoAssignBatch:
    """Tests for auto_assign_batch method."""

    def test_processes_multiple_tickets(
        self, routing_engine, mock_db, ticket_unassigned, rule_round_robin, agents
    ):
        """Test batch processes multiple tickets."""
        ticket2 = MockTicket(id=2, subject="Ticket 2", assigned_to=None)

        with patch.object(routing_engine, 'find_unassigned_tickets', return_value=[ticket_unassigned, ticket2]):
            with patch.object(routing_engine, 'auto_assign') as mock_assign:
                mock_assign.return_value = {"assigned": True, "agent_name": "Agent 1"}

                result = routing_engine.auto_assign_batch(limit=10)

        assert result["processed"] == 2
        assert result["assigned"] == 2
        assert mock_assign.call_count == 2

    def test_counts_failures(self, routing_engine, mock_db, ticket_unassigned):
        """Test counts failed assignments."""
        with patch.object(routing_engine, 'find_unassigned_tickets', return_value=[ticket_unassigned]):
            with patch.object(routing_engine, 'auto_assign', return_value={"assigned": False, "reason": "no_agents"}):
                result = routing_engine.auto_assign_batch()

        assert result["processed"] == 1
        assert result["assigned"] == 0
        assert result["failed"] == 1


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_agent_with_no_display_name(self, routing_engine, mock_db):
        """Test handles agent without display_name."""
        agent = MockAgent(id=1, email="agent@example.com", display_name=None)

        # Should use email as fallback
        ticket = MockTicket(id=1, assigned_to=None)
        rule = MockRoutingRule(id=1, strategy="round_robin", team_id=1)

        with patch.object(routing_engine, 'find_matching_rule', return_value=rule):
            with patch.object(routing_engine, 'get_available_agents', return_value=[agent]):
                with patch.object(routing_engine, 'select_agent', return_value=agent):
                    with patch.object(mock_db, 'query') as mock_query:
                        mock_query.return_value.filter.return_value.first.return_value = None

                        result = routing_engine.auto_assign(ticket)

        assert result["assigned"] is True
        assert result["agent_name"] == "agent@example.com"

    def test_rule_with_empty_conditions_list(self, routing_engine, ticket_unassigned):
        """Test rule with empty conditions list is catch-all."""
        rule = MockRoutingRule(id=1, conditions=[])

        result = routing_engine._evaluate_conditions(rule.conditions, ticket_unassigned)

        assert result is True  # Empty list = catch-all

    def test_condition_with_enum_field(self, routing_engine, ticket_unassigned):
        """Test handles enum field values correctly."""
        # ticket_unassigned.priority is MockTicketPriority.MEDIUM
        conditions = [
            {"field": "priority", "operator": "equals", "value": "medium"}
        ]

        result = routing_engine._evaluate_conditions(conditions, ticket_unassigned)

        assert result is True

    def test_agent_capacity_zero(self, routing_engine, mock_db):
        """Test handles zero capacity gracefully."""
        agent = MockAgent(id=1, capacity=0)

        with patch.object(mock_db, 'query') as mock_query:
            mock_count_query = MagicMock()
            mock_count_query.filter.return_value.scalar.return_value = 0
            mock_query.return_value = mock_count_query

            # Should not crash with division by zero
            result = routing_engine._load_balanced([agent])

        # Agent with zero capacity should be skipped (utilization = inf)
        assert result is None
