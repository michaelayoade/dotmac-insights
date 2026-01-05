"""Support Agent service - business logic for support agents and teams.

After Agent → Party unification, support agents are now represented as:
- Party with PartyRole(role="support_agent")
- Agent capabilities stored in PartyRole.metadata_

This service handles:
- Support agent CRUD operations (via Party + PartyRole)
- Team CRUD operations
- Team membership management
- Workload tracking and availability

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.party import Party, PartyRole
from app.models.agent import Team, TeamMember
from app.models.omni import OmniConversation
from app.models.unified_ticket import UnifiedTicket, TicketStatus

from .types import (
    AgentCreate,
    AgentFilters,
    AgentUpdate,
    AgentWorkload,
    AgentDetailStats,
    AgentDetailResult,
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
    """Service for support agent and team management.

    After Agent → Party unification, agents are now:
    - Party records with PartyRole(role="support_agent")
    - Agent capabilities stored in PartyRole.metadata_

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
    # Agent Queries (Party-based)
    # -------------------------------------------------------------------------

    def _base_agent_query(self):
        """Base query for support agents (Party with support_agent role)."""
        return (
            self.db.query(Party)
            .join(PartyRole)
            .filter(
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            )
        )

    def list_agents(
        self,
        filters: Optional[AgentFilters] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Party]:
        """List support agents with optional filtering.

        Args:
            filters: Optional AgentFilters for filtering results.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of Party instances (support agents).
        """
        query = self._base_agent_query().options(joinedload(Party.roles))

        if filters:
            if filters.is_active is not None:
                if filters.is_active:
                    query = query.filter(Party.status == "active")
                else:
                    query = query.filter(Party.status != "active")

            if filters.domain:
                # Filter by domain in PartyRole metadata
                query = query.filter(
                    PartyRole.metadata_.op("->")("domains").op("->>")(filters.domain) == "true"
                )

            if filters.team_id:
                query = query.join(TeamMember, TeamMember.party_id == Party.id).filter(
                    TeamMember.team_id == filters.team_id,
                    TeamMember.is_active == True,
                )

            if filters.skill:
                # Filter by skill in PartyRole metadata
                query = query.filter(
                    PartyRole.metadata_.op("->")("skills").op("->")(filters.skill).isnot(None)
                )

            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Party.name.ilike(search_term),
                        Party.primary_email.ilike(search_term),
                        Party.first_name.ilike(search_term),
                        Party.last_name.ilike(search_term),
                    )
                )

        query = query.order_by(Party.name.asc())
        return query.offset(offset).limit(limit).all()

    def get_agent(self, party_id: int) -> Party:
        """Get a support agent by Party ID.

        Args:
            party_id: The party ID.

        Returns:
            Party instance (support agent).

        Raises:
            AgentNotFoundError: If agent not found.
        """
        party = (
            self._base_agent_query()
            .options(joinedload(Party.roles))
            .filter(Party.id == party_id)
            .first()
        )
        if not party:
            raise AgentNotFoundError(party_id)
        return party

    def get_agent_by_email(self, email: str) -> Optional[Party]:
        """Get a support agent by email.

        Args:
            email: The agent's email.

        Returns:
            Party instance or None if not found.
        """
        return (
            self._base_agent_query()
            .options(joinedload(Party.roles))
            .filter(Party.primary_email == email)
            .first()
        )

    def get_party_agent_role(self, party_id: int) -> Optional[PartyRole]:
        """Get the support_agent PartyRole for a party.

        Args:
            party_id: The party ID.

        Returns:
            PartyRole or None if not a support agent.
        """
        return (
            self.db.query(PartyRole)
            .filter(
                PartyRole.party_id == party_id,
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            )
            .first()
        )

    def search_agents(self, query: str, limit: int = 20) -> List[Party]:
        """Search support agents by name or email.

        Args:
            query: Search query.
            limit: Maximum number of results.

        Returns:
            List of matching Party instances.
        """
        search_term = f"%{query}%"
        return (
            self._base_agent_query()
            .filter(
                Party.status == "active",
                or_(
                    Party.name.ilike(search_term),
                    Party.primary_email.ilike(search_term),
                    Party.first_name.ilike(search_term),
                    Party.last_name.ilike(search_term),
                ),
            )
            .order_by(Party.name.asc())
            .limit(limit)
            .all()
        )

    # -------------------------------------------------------------------------
    # Agent Mutations
    # -------------------------------------------------------------------------

    def create_agent(self, data: AgentCreate) -> Party:
        """Create a new support agent.

        Creates a Party record with PartyRole(role="support_agent").

        Args:
            data: Agent creation data.

        Returns:
            Created Party instance.

        Raises:
            DuplicateAgentError: If email already exists as an agent.
        """
        # Check for duplicate email
        if data.email:
            existing = self.get_agent_by_email(data.email)
            if existing:
                raise DuplicateAgentError(data.email)

        # Check if party already exists with this email
        existing_party = (
            self.db.query(Party)
            .filter(Party.primary_email == data.email)
            .first()
        ) if data.email else None

        if existing_party:
            # Party exists - add support_agent role
            party = existing_party
            # Check if already has the role
            existing_role = self.get_party_agent_role(party.id)
            if existing_role:
                raise DuplicateAgentError(data.email or str(party.id))
        else:
            # Create new party
            party = Party(
                type="person",
                status="active",
                name=data.display_name,
                primary_email=data.email,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(party)
            self.db.flush()

        # Build metadata for agent capabilities
        metadata = {}
        if data.domains:
            metadata["domains"] = {d: True for d in data.domains}
        if data.skills:
            metadata["skills"] = {s: 1 for s in data.skills}
        if data.channel_caps:
            metadata["channel_caps"] = data.channel_caps
        if data.capacity is not None:
            metadata["capacity"] = data.capacity
        if data.routing_weight is not None:
            metadata["routing_weight"] = data.routing_weight

        # Create support_agent role
        role = PartyRole(
            party_id=party.id,
            role="support_agent",
            status="active",
            metadata_=metadata,
            since=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(role)
        self.db.flush()

        # Refresh party to load relationships
        self.db.refresh(party)
        return party

    def update_agent(self, party_id: int, data: AgentUpdate) -> Party:
        """Update a support agent.

        Args:
            party_id: The party ID.
            data: Update data.

        Returns:
            Updated Party instance.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if not role:
            raise AgentNotFoundError(party_id)

        # Update Party fields
        if data.display_name is not None:
            party.name = data.display_name

        # Update PartyRole metadata
        metadata = dict(role.metadata_ or {})

        if data.domains is not None:
            metadata["domains"] = {d: True for d in data.domains} if data.domains else {}

        if data.skills is not None:
            metadata["skills"] = {s: 1 for s in data.skills} if data.skills else {}

        if data.capacity is not None:
            metadata["capacity"] = data.capacity

        if data.routing_weight is not None:
            metadata["routing_weight"] = data.routing_weight

        if data.channel_caps is not None:
            metadata["channel_caps"] = data.channel_caps if data.channel_caps else []

        role.metadata_ = metadata

        # Handle is_active by changing role status
        if data.is_active is not None:
            role.status = "active" if data.is_active else "inactive"

        party.updated_at = datetime.now(timezone.utc)
        role.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        self.db.refresh(party)
        return party

    def activate_agent(self, party_id: int) -> Party:
        """Activate a support agent.

        Args:
            party_id: The party ID.

        Returns:
            Updated Party instance.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if role:
            role.status = "active"
            role.updated_at = datetime.now(timezone.utc)
        party.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return party

    def deactivate_agent(self, party_id: int) -> Party:
        """Deactivate a support agent.

        Args:
            party_id: The party ID.

        Returns:
            Updated Party instance.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if role:
            role.status = "inactive"
            role.updated_at = datetime.now(timezone.utc)
        party.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return party

    def delete_agent(self, party_id: int) -> bool:
        """Remove support agent role from a party.

        This doesn't delete the Party, just ends the support_agent role.

        Args:
            party_id: The party ID.

        Returns:
            True if deleted.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if role:
            role.until = datetime.now(timezone.utc)
            role.status = "inactive"
            role.updated_at = datetime.now(timezone.utc)
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

    def list_teams_with_stats(
        self,
        active_only: Optional[bool] = None,
    ) -> tuple[List[Team], Dict[int, Dict[str, int]]]:
        """List teams with aggregated member and capacity stats."""
        query = self.db.query(Team)
        if active_only is not None:
            query = query.filter(Team.is_active == active_only)

        teams = query.order_by(Team.name.asc()).all()
        if not teams:
            return [], {}

        team_ids = [t.id for t in teams]
        members = self.db.query(TeamMember).filter(
            TeamMember.team_id.in_(team_ids)
        ).all()

        members_by_team: Dict[int, List[int]] = {t.id: [] for t in teams}
        party_ids: set[int] = set()
        for member in members:
            members_by_team.setdefault(member.team_id, []).append(member.party_id)
            party_ids.add(member.party_id)

        # Get parties with their roles
        parties = (
            self.db.query(Party)
            .options(joinedload(Party.roles))
            .filter(Party.id.in_(party_ids))
            .all()
        ) if party_ids else []
        parties_by_id = {p.id: p for p in parties}

        stats: Dict[int, Dict[str, int]] = {}
        for team in teams:
            party_list = [parties_by_id[p_id] for p_id in members_by_team.get(team.id, []) if p_id in parties_by_id]
            active_agents = [p for p in party_list if p.is_support_agent and p.status == "active"]
            stats[team.id] = {
                "member_count": len(party_list),
                "active_agents": len(active_agents),
                "total_capacity": sum(p.agent_capacity for p in active_agents),
            }

        return teams, stats

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
    ) -> List[Party]:
        """Get all support agents in a team.

        Args:
            team_id: The team ID.
            active_only: Only return active members.

        Returns:
            List of Party instances (support agents).
        """
        query = (
            self.db.query(Party)
            .join(TeamMember, TeamMember.party_id == Party.id)
            .join(PartyRole, PartyRole.party_id == Party.id)
            .filter(
                TeamMember.team_id == team_id,
                PartyRole.role == "support_agent",
                PartyRole.until.is_(None),
            )
        )

        if active_only:
            query = query.filter(
                TeamMember.is_active == True,
                Party.status == "active",
                PartyRole.status == "active",
            )

        return query.options(joinedload(Party.roles)).order_by(Party.name.asc()).all()

    def get_team_detail(self, team_id: int) -> Dict[str, Any]:
        """Get team details with members and workload."""
        team = self.get_team(team_id)
        members = self.db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
        party_ids = [m.party_id for m in members]
        parties = (
            self.db.query(Party)
            .options(joinedload(Party.roles))
            .filter(Party.id.in_(party_ids))
            .all()
        ) if party_ids else []

        open_statuses = [
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.WAITING.value,
            TicketStatus.ON_HOLD.value,
            TicketStatus.REOPENED.value,
        ]

        agent_workload: list[dict[str, Any]] = []
        for party in parties:
            if not party.is_support_agent:
                continue

            open_tickets = self.db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.assigned_to_party_id == party.id,
                UnifiedTicket.status.in_(open_statuses),
            ).scalar() or 0

            capacity = party.agent_capacity
            utilization = round(open_tickets / capacity * 100, 1) if capacity > 0 else 0
            agent_workload.append({
                "agent": party,
                "open_tickets": open_tickets,
                "capacity": capacity,
                "utilization": utilization,
            })

        active_agents = [p for p in parties if p.is_support_agent and p.status == "active"]
        stats = {
            "member_count": len(members),
            "active_agents": len(active_agents),
            "total_capacity": sum(p.agent_capacity for p in active_agents),
        }

        return {
            "team": team,
            "agents": agent_workload,
            "stats": stats,
        }

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
        party_id: int,
        role: str = "member",
    ) -> TeamMember:
        """Add a party (support agent) to a team.

        Args:
            team_id: The team ID.
            party_id: The party ID.
            role: Role in team (lead, member).

        Returns:
            Created TeamMember instance.

        Raises:
            TeamNotFoundError: If team not found.
            AgentNotFoundError: If party is not a support agent.
            TeamMembershipError: If already a member.
        """
        # Verify team exists
        self.get_team(team_id)

        # Verify party is a support agent
        party = self.get_agent(party_id)

        # Check if already a member
        existing = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.party_id == party_id,
            )
            .first()
        )
        if existing:
            if existing.is_active:
                raise TeamMembershipError(f"Party {party_id} is already a member of team {team_id}")
            # Reactivate membership
            existing.is_active = True
            existing.role = role
            self.db.flush()
            return existing

        member = TeamMember(
            team_id=team_id,
            party_id=party_id,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(member)
        self.db.flush()
        return member

    def remove_member(self, team_id: int, party_id: int) -> bool:
        """Remove a party from a team.

        Args:
            team_id: The team ID.
            party_id: The party ID.

        Returns:
            True if removed.

        Raises:
            TeamMembershipError: If not a member.
        """
        member = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.party_id == party_id,
                TeamMember.is_active == True,
            )
            .first()
        )
        if not member:
            raise TeamMembershipError(f"Party {party_id} is not a member of team {team_id}")

        member.is_active = False
        self.db.flush()
        return True

    def update_member_role(
        self,
        team_id: int,
        party_id: int,
        role: str,
    ) -> TeamMember:
        """Update a party's role in a team.

        Args:
            team_id: The team ID.
            party_id: The party ID.
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
                TeamMember.party_id == party_id,
                TeamMember.is_active == True,
            )
            .first()
        )
        if not member:
            raise TeamMembershipError(f"Party {party_id} is not a member of team {team_id}")

        member.role = role
        self.db.flush()
        return member

    def get_agent_teams(self, party_id: int) -> List[Team]:
        """Get all teams a party belongs to.

        Args:
            party_id: The party ID.

        Returns:
            List of Team instances.
        """
        return (
            self.db.query(Team)
            .join(TeamMember)
            .filter(
                TeamMember.party_id == party_id,
                TeamMember.is_active == True,
                Team.is_active == True,
            )
            .order_by(Team.name.asc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Workload
    # -------------------------------------------------------------------------

    def get_agent_workload(self, party_id: int) -> AgentWorkload:
        """Get a support agent's current workload.

        Args:
            party_id: The party ID.

        Returns:
            AgentWorkload instance.
        """
        party = self.get_agent(party_id)

        # Count open tickets
        open_tickets = (
            self.db.query(func.count(UnifiedTicket.id))
            .filter(
                UnifiedTicket.assigned_to_party_id == party_id,
                UnifiedTicket.status.in_([
                    TicketStatus.OPEN.value,
                    TicketStatus.IN_PROGRESS.value,
                    TicketStatus.WAITING.value,
                    TicketStatus.ON_HOLD.value,
                    TicketStatus.REOPENED.value,
                ]),
                UnifiedTicket.is_deleted == False,
            )
            .scalar()
            or 0
        )

        # Count open conversations
        open_conversations = (
            self.db.query(func.count(OmniConversation.id))
            .filter(
                OmniConversation.assigned_party_id == party_id,
                OmniConversation.status.in_(["open", "pending"]),
            )
            .scalar()
            or 0
        )

        total_active = open_tickets + open_conversations
        capacity = party.agent_capacity
        utilization = (total_active / capacity * 100) if capacity > 0 else 0.0

        return AgentWorkload(
            agent_id=party_id,
            open_tickets=open_tickets,
            open_conversations=open_conversations,
            total_active=total_active,
            capacity=capacity,
            utilization_pct=round(utilization, 1),
        )

    def get_agent_detail(
        self,
        party_id: int,
        recent_ticket_limit: int = 10,
    ) -> AgentDetailResult:
        """Get comprehensive agent detail data for the detail page.

        This method returns all data needed for the agent detail page in a
        single call, avoiding N+1 queries.

        Args:
            party_id: The party ID.
            recent_ticket_limit: Max number of recent open tickets to include.

        Returns:
            AgentDetailResult with party (agent), stats, team memberships, and recent tickets.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        party = self.get_agent(party_id)

        # Get team memberships with team data (single query with join)
        team_memberships = (
            self.db.query(TeamMember)
            .options(joinedload(TeamMember.team))
            .filter(TeamMember.party_id == party_id)
            .all()
        )

        # Get linked employee if exists (via Employee.party_id)
        employee = None
        from app.models.employee import Employee
        employee = (
            self.db.query(Employee)
            .filter(Employee.party_id == party_id)
            .first()
        )

        # Get recent open tickets
        recent_tickets = (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.assigned_to_party_id == party_id,
                UnifiedTicket.status.notin_(["closed", "resolved"]),
                UnifiedTicket.is_deleted == False,
            )
            .order_by(UnifiedTicket.created_at.desc())
            .limit(recent_ticket_limit)
            .all()
        )

        # Calculate stats
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        open_count = (
            self.db.query(func.count(UnifiedTicket.id))
            .filter(
                UnifiedTicket.assigned_to_party_id == party_id,
                UnifiedTicket.status.notin_(["closed", "resolved"]),
                UnifiedTicket.is_deleted == False,
            )
            .scalar()
            or 0
        )

        resolved_today = (
            self.db.query(func.count(UnifiedTicket.id))
            .filter(
                UnifiedTicket.assigned_to_party_id == party_id,
                UnifiedTicket.status == "resolved",
                UnifiedTicket.updated_at >= today,
                UnifiedTicket.is_deleted == False,
            )
            .scalar()
            or 0
        )

        stats = AgentDetailStats(
            open_tickets=open_count,
            resolved_today=resolved_today,
            team_count=len(team_memberships),
        )

        return AgentDetailResult(
            agent=party,  # Note: now returns Party instead of Agent
            employee=employee,
            stats=stats,
            team_memberships=team_memberships,
            recent_tickets=recent_tickets,
        )

    def get_team_workload(self, team_id: int) -> TeamWorkload:
        """Get a team's current workload.

        Args:
            team_id: The team ID.

        Returns:
            TeamWorkload instance.
        """
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

        total_open = 0
        total_utilization = 0.0
        available_count = 0

        for party in members:
            workload = self.get_agent_workload(party.id)
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

    def is_agent_available(self, party_id: int) -> bool:
        """Check if an agent is available (under capacity).

        Args:
            party_id: The party ID.

        Returns:
            True if agent is available.
        """
        workload = self.get_agent_workload(party_id)
        return workload.utilization_pct < 100

    def get_available_agents(self, team_id: int) -> List[Party]:
        """Get available agents in a team (under capacity).

        Args:
            team_id: The team ID.

        Returns:
            List of available Party instances.
        """
        members = self.get_team_members(team_id, active_only=True)
        available = []

        for party in members:
            if self.is_agent_available(party.id):
                available.append(party)

        return available

    # -------------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------------

    def get_agents_by_skill(self, skill: str) -> List[Party]:
        """Get agents with a specific skill.

        Args:
            skill: The skill name.

        Returns:
            List of Party instances with the skill.
        """
        return (
            self._base_agent_query()
            .filter(
                Party.status == "active",
                PartyRole.metadata_.op("->")("skills").op("->")(skill).isnot(None),
            )
            .order_by(Party.name.asc())
            .all()
        )

    def add_skill(self, party_id: int, skill: str, level: int = 1) -> Party:
        """Add a skill to an agent.

        Args:
            party_id: The party ID.
            skill: The skill name.
            level: Skill level (default 1).

        Returns:
            Updated Party instance.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if not role:
            raise AgentNotFoundError(party_id)

        metadata = dict(role.metadata_ or {})
        skills = dict(metadata.get("skills", {}))
        skills[skill] = level
        metadata["skills"] = skills
        role.metadata_ = metadata
        role.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        self.db.refresh(party)
        return party

    def remove_skill(self, party_id: int, skill: str) -> Party:
        """Remove a skill from an agent.

        Args:
            party_id: The party ID.
            skill: The skill name.

        Returns:
            Updated Party instance.
        """
        party = self.get_agent(party_id)
        role = self.get_party_agent_role(party_id)
        if not role:
            raise AgentNotFoundError(party_id)

        metadata = dict(role.metadata_ or {})
        skills = dict(metadata.get("skills", {}))
        skills.pop(skill, None)
        metadata["skills"] = skills if skills else {}
        role.metadata_ = metadata
        role.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        self.db.refresh(party)
        return party
