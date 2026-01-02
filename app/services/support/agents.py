"""Agent service - business logic for agents and teams.

This service handles agent and team management:
- Agent CRUD operations
- Team CRUD operations
- Team membership management
- Workload tracking and availability

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.agent import Agent, Team, TeamMember
from app.models.omni import OmniConversation
from app.models.ticket import Ticket

from .types import (
    AgentCreate,
    AgentFilters,
    AgentUpdate,
    AgentWorkload,
    TeamCreate,
    TeamUpdate,
    TeamWorkload,
)
from .errors import (
    AgentNotFoundError,
    DuplicateAgentError,
    DuplicateTeamError,
    TeamMembershipError,
    TeamNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AgentService"]


class AgentService:
    """Service for agent and team management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Agent Queries
    # -------------------------------------------------------------------------

    def list_agents(
        self,
        filters: Optional[AgentFilters] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        """List agents with optional filtering.

        Args:
            filters: Optional AgentFilters for filtering results.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of Agent instances.
        """
        query = self.db.query(Agent)

        if filters:
            if filters.is_active is not None:
                query = query.filter(Agent.is_active == filters.is_active)

            if filters.domain:
                # domains is a JSON field like {"support": true, "sales": true}
                query = query.filter(
                    Agent.domains.op("->>")(filters.domain) == "true"
                )

            if filters.team_id:
                query = query.join(TeamMember).filter(
                    TeamMember.team_id == filters.team_id,
                    TeamMember.is_active == True,
                )

            if filters.skill:
                # skills is a JSON field like {"network": 3, "billing": 2}
                query = query.filter(
                    Agent.skills.op("->")(filters.skill).isnot(None)
                )

            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Agent.display_name.ilike(search_term),
                        Agent.email.ilike(search_term),
                    )
                )

        query = query.order_by(Agent.display_name.asc())
        return query.offset(offset).limit(limit).all()

    def get_agent(self, agent_id: int) -> Agent:
        """Get an agent by ID.

        Args:
            agent_id: The agent ID.

        Returns:
            Agent instance.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise AgentNotFoundError(agent_id)
        return agent

    def get_agent_by_email(self, email: str) -> Optional[Agent]:
        """Get an agent by email.

        Args:
            email: The agent's email.

        Returns:
            Agent instance or None if not found.
        """
        return self.db.query(Agent).filter(Agent.email == email).first()

    def get_agent_by_employee_id(self, employee_id: int) -> Optional[Agent]:
        """Get an agent by employee ID.

        Args:
            employee_id: The employee ID.

        Returns:
            Agent instance or None if not found.
        """
        return self.db.query(Agent).filter(Agent.employee_id == employee_id).first()

    def search_agents(self, query: str, limit: int = 20) -> List[Agent]:
        """Search agents by name or email.

        Args:
            query: Search query.
            limit: Maximum number of results.

        Returns:
            List of matching Agent instances.
        """
        search_term = f"%{query}%"
        return (
            self.db.query(Agent)
            .filter(
                Agent.is_active == True,
                or_(
                    Agent.display_name.ilike(search_term),
                    Agent.email.ilike(search_term),
                ),
            )
            .order_by(Agent.display_name.asc())
            .limit(limit)
            .all()
        )

    # -------------------------------------------------------------------------
    # Agent Mutations
    # -------------------------------------------------------------------------

    def create_agent(self, data: AgentCreate) -> Agent:
        """Create a new agent.

        Args:
            data: Agent creation data.

        Returns:
            Created Agent instance.

        Raises:
            DuplicateAgentError: If email already exists.
        """
        # Check for duplicate email
        if data.email:
            existing = self.get_agent_by_email(data.email)
            if existing:
                raise DuplicateAgentError(data.email)

        # Convert domains list to JSON dict
        domains_dict = {d: True for d in data.domains} if data.domains else None

        # Convert skills list to JSON dict with default weight 1
        skills_dict = {s: 1 for s in data.skills} if data.skills else None

        agent = Agent(
            email=data.email,
            display_name=data.display_name,
            employee_id=data.employee_id,
            domains=domains_dict,
            skills=skills_dict,
            capacity=data.capacity,
            routing_weight=data.routing_weight,
            channel_caps=data.channel_caps if data.channel_caps else None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(agent)
        self.db.flush()
        return agent

    def update_agent(self, agent_id: int, data: AgentUpdate) -> Agent:
        """Update an agent.

        Args:
            agent_id: The agent ID.
            data: Update data.

        Returns:
            Updated Agent instance.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        agent = self.get_agent(agent_id)

        if data.display_name is not None:
            agent.display_name = data.display_name

        if data.domains is not None:
            agent.domains = {d: True for d in data.domains} if data.domains else None

        if data.skills is not None:
            agent.skills = {s: 1 for s in data.skills} if data.skills else None

        if data.capacity is not None:
            agent.capacity = data.capacity

        if data.routing_weight is not None:
            agent.routing_weight = data.routing_weight

        if data.channel_caps is not None:
            agent.channel_caps = data.channel_caps if data.channel_caps else None

        if data.is_active is not None:
            agent.is_active = data.is_active

        agent.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return agent

    def activate_agent(self, agent_id: int) -> Agent:
        """Activate an agent.

        Args:
            agent_id: The agent ID.

        Returns:
            Updated Agent instance.
        """
        agent = self.get_agent(agent_id)
        agent.is_active = True
        agent.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return agent

    def deactivate_agent(self, agent_id: int) -> Agent:
        """Deactivate an agent.

        Args:
            agent_id: The agent ID.

        Returns:
            Updated Agent instance.
        """
        agent = self.get_agent(agent_id)
        agent.is_active = False
        agent.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return agent

    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent.

        Args:
            agent_id: The agent ID.

        Returns:
            True if deleted.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        agent = self.get_agent(agent_id)
        self.db.delete(agent)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Team Queries
    # -------------------------------------------------------------------------

    def list_teams(
        self,
        domain: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Team]:
        """List teams with optional filtering.

        Args:
            domain: Filter by domain (support, sales, etc.).
            active_only: Only return active teams.

        Returns:
            List of Team instances.
        """
        query = self.db.query(Team)

        if active_only:
            query = query.filter(Team.is_active == True)

        if domain:
            query = query.filter(Team.domain == domain)

        return query.order_by(Team.name.asc()).all()

    def get_team(self, team_id: int) -> Team:
        """Get a team by ID.

        Args:
            team_id: The team ID.

        Returns:
            Team instance.

        Raises:
            TeamNotFoundError: If team not found.
        """
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise TeamNotFoundError(team_id)
        return team

    def get_team_by_name(self, name: str) -> Optional[Team]:
        """Get a team by name.

        Args:
            name: The team name.

        Returns:
            Team instance or None if not found.
        """
        return self.db.query(Team).filter(Team.name == name).first()

    def get_team_members(
        self,
        team_id: int,
        active_only: bool = True,
    ) -> List[Agent]:
        """Get all agents in a team.

        Args:
            team_id: The team ID.
            active_only: Only return active members.

        Returns:
            List of Agent instances.
        """
        query = (
            self.db.query(Agent)
            .join(TeamMember)
            .filter(TeamMember.team_id == team_id)
        )

        if active_only:
            query = query.filter(
                TeamMember.is_active == True,
                Agent.is_active == True,
            )

        return query.order_by(Agent.display_name.asc()).all()

    # -------------------------------------------------------------------------
    # Team Mutations
    # -------------------------------------------------------------------------

    def create_team(self, data: TeamCreate) -> Team:
        """Create a new team.

        Args:
            data: Team creation data.

        Returns:
            Created Team instance.

        Raises:
            DuplicateTeamError: If name already exists.
        """
        # Check for duplicate name
        existing = self.get_team_by_name(data.name)
        if existing:
            raise DuplicateTeamError(data.name)

        team = Team(
            name=data.name,
            description=data.description,
            domain=data.domain,
            assignment_rule=data.assignment_rule,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(team)
        self.db.flush()
        return team

    def update_team(self, team_id: int, data: TeamUpdate) -> Team:
        """Update a team.

        Args:
            team_id: The team ID.
            data: Update data.

        Returns:
            Updated Team instance.

        Raises:
            TeamNotFoundError: If team not found.
            DuplicateTeamError: If new name conflicts.
        """
        team = self.get_team(team_id)

        if data.name is not None and data.name != team.name:
            existing = self.get_team_by_name(data.name)
            if existing:
                raise DuplicateTeamError(data.name)
            team.name = data.name

        if data.description is not None:
            team.description = data.description

        if data.domain is not None:
            team.domain = data.domain

        if data.assignment_rule is not None:
            team.assignment_rule = data.assignment_rule

        if data.is_active is not None:
            team.is_active = data.is_active

        team.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return team

    def delete_team(self, team_id: int) -> bool:
        """Delete a team.

        Args:
            team_id: The team ID.

        Returns:
            True if deleted.

        Raises:
            TeamNotFoundError: If team not found.
        """
        team = self.get_team(team_id)
        self.db.delete(team)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Membership
    # -------------------------------------------------------------------------

    def add_member(
        self,
        team_id: int,
        agent_id: int,
        role: str = "member",
    ) -> TeamMember:
        """Add an agent to a team.

        Args:
            team_id: The team ID.
            agent_id: The agent ID.
            role: Role in team (lead, member).

        Returns:
            Created TeamMember instance.

        Raises:
            TeamNotFoundError: If team not found.
            AgentNotFoundError: If agent not found.
            TeamMembershipError: If already a member.
        """
        # Verify team and agent exist
        self.get_team(team_id)
        self.get_agent(agent_id)

        # Check if already a member
        existing = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.agent_id == agent_id,
            )
            .first()
        )
        if existing:
            if existing.is_active:
                raise TeamMembershipError(f"Agent {agent_id} is already a member of team {team_id}")
            # Reactivate membership
            existing.is_active = True
            existing.role = role
            self.db.flush()
            return existing

        member = TeamMember(
            team_id=team_id,
            agent_id=agent_id,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(member)
        self.db.flush()
        return member

    def remove_member(self, team_id: int, agent_id: int) -> bool:
        """Remove an agent from a team.

        Args:
            team_id: The team ID.
            agent_id: The agent ID.

        Returns:
            True if removed.

        Raises:
            TeamMembershipError: If not a member.
        """
        member = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True,
            )
            .first()
        )
        if not member:
            raise TeamMembershipError(f"Agent {agent_id} is not a member of team {team_id}")

        member.is_active = False
        self.db.flush()
        return True

    def update_member_role(
        self,
        team_id: int,
        agent_id: int,
        role: str,
    ) -> TeamMember:
        """Update an agent's role in a team.

        Args:
            team_id: The team ID.
            agent_id: The agent ID.
            role: New role.

        Returns:
            Updated TeamMember instance.

        Raises:
            TeamMembershipError: If not a member.
        """
        member = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True,
            )
            .first()
        )
        if not member:
            raise TeamMembershipError(f"Agent {agent_id} is not a member of team {team_id}")

        member.role = role
        self.db.flush()
        return member

    def get_agent_teams(self, agent_id: int) -> List[Team]:
        """Get all teams an agent belongs to.

        Args:
            agent_id: The agent ID.

        Returns:
            List of Team instances.
        """
        return (
            self.db.query(Team)
            .join(TeamMember)
            .filter(
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True,
                Team.is_active == True,
            )
            .order_by(Team.name.asc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Workload
    # -------------------------------------------------------------------------

    def get_agent_workload(self, agent_id: int) -> AgentWorkload:
        """Get an agent's current workload.

        Args:
            agent_id: The agent ID.

        Returns:
            AgentWorkload instance.
        """
        agent = self.get_agent(agent_id)

        # Count open tickets
        open_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.assignee_id == agent_id,
                Ticket.status.in_(["open", "pending", "in_progress"]),
            )
            .scalar()
            or 0
        )

        # Count open conversations
        open_conversations = (
            self.db.query(func.count(OmniConversation.id))
            .filter(
                OmniConversation.assigned_agent_id == agent_id,
                OmniConversation.status.in_(["open", "pending"]),
            )
            .scalar()
            or 0
        )

        total_active = open_tickets + open_conversations
        capacity = agent.capacity or 10
        utilization = (total_active / capacity * 100) if capacity > 0 else 0.0

        return AgentWorkload(
            agent_id=agent_id,
            open_tickets=open_tickets,
            open_conversations=open_conversations,
            total_active=total_active,
            capacity=capacity,
            utilization_pct=round(utilization, 1),
        )

    def get_team_workload(self, team_id: int) -> TeamWorkload:
        """Get a team's current workload.

        Args:
            team_id: The team ID.

        Returns:
            TeamWorkload instance.
        """
        # Get team members
        members = self.get_team_members(team_id, active_only=True)
        total_agents = len(members)

        if total_agents == 0:
            return TeamWorkload(
                team_id=team_id,
                total_open=0,
                total_agents=0,
                available_agents=0,
                avg_utilization_pct=0.0,
            )

        # Calculate workload for each member
        total_open = 0
        total_utilization = 0.0
        available_count = 0

        for agent in members:
            workload = self.get_agent_workload(agent.id)
            total_open += workload.total_active
            total_utilization += workload.utilization_pct
            if workload.utilization_pct < 100:
                available_count += 1

        avg_utilization = total_utilization / total_agents if total_agents > 0 else 0.0

        return TeamWorkload(
            team_id=team_id,
            total_open=total_open,
            total_agents=total_agents,
            available_agents=available_count,
            avg_utilization_pct=round(avg_utilization, 1),
        )

    def is_agent_available(self, agent_id: int) -> bool:
        """Check if an agent is available (under capacity).

        Args:
            agent_id: The agent ID.

        Returns:
            True if agent is available.
        """
        workload = self.get_agent_workload(agent_id)
        return workload.utilization_pct < 100

    def get_available_agents(self, team_id: int) -> List[Agent]:
        """Get available agents in a team (under capacity).

        Args:
            team_id: The team ID.

        Returns:
            List of available Agent instances.
        """
        members = self.get_team_members(team_id, active_only=True)
        available = []

        for agent in members:
            if self.is_agent_available(agent.id):
                available.append(agent)

        return available

    # -------------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------------

    def get_agents_by_skill(self, skill: str) -> List[Agent]:
        """Get agents with a specific skill.

        Args:
            skill: The skill name.

        Returns:
            List of Agent instances with the skill.
        """
        return (
            self.db.query(Agent)
            .filter(
                Agent.is_active == True,
                Agent.skills.op("->")(skill).isnot(None),
            )
            .order_by(Agent.display_name.asc())
            .all()
        )

    def add_skill(self, agent_id: int, skill: str, level: int = 1) -> Agent:
        """Add a skill to an agent.

        Args:
            agent_id: The agent ID.
            skill: The skill name.
            level: Skill level (default 1).

        Returns:
            Updated Agent instance.
        """
        agent = self.get_agent(agent_id)
        skills = dict(agent.skills or {})
        skills[skill] = level
        agent.skills = skills
        agent.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return agent

    def remove_skill(self, agent_id: int, skill: str) -> Agent:
        """Remove a skill from an agent.

        Args:
            agent_id: The agent ID.
            skill: The skill name.

        Returns:
            Updated Agent instance.
        """
        agent = self.get_agent(agent_id)
        skills = dict(agent.skills or {})
        skills.pop(skill, None)
        agent.skills = skills if skills else None
        agent.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return agent
