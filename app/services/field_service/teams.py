"""Team service for field service teams and technicians.

This service handles:
- Team CRUD operations
- Team member management
- Technician queries and skills
- Service zone management
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.field_service import (
    FieldTeam,
    FieldTeamMember,
    TechnicianSkill,
    ServiceZone,
    ServiceOrder,
    ServiceOrderStatus,
)
from app.models.employee import Employee, EmploymentStatus
from app.services.types import PaginatedResult, PaginationParams

from .team_types import (
    TeamFilters,
    TeamCreateData,
    TeamUpdateData,
    TeamMemberData,
    TechnicianFilters,
    TechnicianSkillData,
    ZoneFilters,
    ZoneCreateData,
    ZoneUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TeamService"]


class TeamService:
    """Service for managing field teams and technicians.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Team Query Methods
    # -------------------------------------------------------------------------

    def list_teams(
        self,
        filters: Optional[TeamFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[FieldTeam]:
        """List field teams with filtering and pagination.

        Args:
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Paginated list of teams
        """
        if filters is None:
            filters = TeamFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(FieldTeam)

        if filters.is_active is not None:
            query = query.filter(FieldTeam.is_active == filters.is_active)
        if filters.search:
            query = query.filter(FieldTeam.name.ilike(f"%{filters.search}%"))
        if filters.company:
            query = query.filter(FieldTeam.company == filters.company)

        total = query.count()
        teams = (
            query.order_by(FieldTeam.name)
            .offset(pagination.offset)
            .limit(pagination.limit)
            .all()
        )

        return PaginatedResult(
            items=teams,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_team(self, team_id: int) -> FieldTeam:
        """Get a team by ID.

        Args:
            team_id: ID of the team

        Returns:
            The team

        Raises:
            NotFoundError: If team not found
        """
        from app.services.errors import NotFoundError

        team = self.db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
        if not team:
            raise NotFoundError(f"Team with ID {team_id} not found")
        return team

    def count_team_members(self, team_id: int, active_only: bool = True) -> int:
        """Count members in a team."""
        query = self.db.query(FieldTeamMember).filter(FieldTeamMember.team_id == team_id)
        if active_only:
            query = query.filter(FieldTeamMember.is_active == True)
        return query.count()

    def list_team_members(
        self,
        team_id: int,
        active_only: bool = False,
    ) -> List[FieldTeamMember]:
        """List team members with employee details."""
        query = (
            self.db.query(FieldTeamMember)
            .options(joinedload(FieldTeamMember.employee))
            .filter(FieldTeamMember.team_id == team_id)
        )
        if active_only:
            query = query.filter(FieldTeamMember.is_active == True)
        return query.all()

    def get_team_member(
        self,
        team_id: int,
        member_id: int,
    ) -> Optional[FieldTeamMember]:
        """Get a specific team member record."""
        return (
            self.db.query(FieldTeamMember)
            .filter(
                FieldTeamMember.team_id == team_id,
                FieldTeamMember.id == member_id,
            )
            .first()
        )

    def list_available_employees(
        self,
        team_id: int,
        limit: int = 50,
    ) -> List[Employee]:
        """List active employees not currently in the team."""
        member_ids = (
            self.db.query(FieldTeamMember.party_id)
            .filter(FieldTeamMember.team_id == team_id)
            .all()
        )
        exclude_ids = [row.party_id for row in member_ids if row.party_id]

        query = self.db.query(Employee).filter(
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE,
        )
        if exclude_ids:
            query = query.filter(~Employee.party_id.in_(exclude_ids))
        return query.order_by(Employee.name).limit(limit).all()

    def get_team_stats(self, team_id: int) -> dict:
        """Get team statistics.

        Args:
            team_id: ID of the team

        Returns:
            Dict with active_orders, today_orders counts
        """
        today = date.today()

        active_orders = (
            self.db.query(func.count(ServiceOrder.id))
            .filter(
                ServiceOrder.assigned_team_id == team_id,
                ServiceOrder.status.notin_(
                    [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]
                ),
            )
            .scalar()
            or 0
        )

        today_orders = (
            self.db.query(func.count(ServiceOrder.id))
            .filter(
                ServiceOrder.assigned_team_id == team_id,
                ServiceOrder.scheduled_date == today,
            )
            .scalar()
            or 0
        )

        return {
            "active_orders": active_orders,
            "today_orders": today_orders,
        }

    # -------------------------------------------------------------------------
    # Team Mutation Methods
    # -------------------------------------------------------------------------

    def create_team(self, data: TeamCreateData) -> FieldTeam:
        """Create a new field team.

        Args:
            data: Team creation data

        Returns:
            The created team (not yet committed)
        """
        team = FieldTeam(
            name=data.name,
            description=data.description,
            coverage_zone_ids=data.coverage_zone_ids,
            max_daily_orders=data.max_daily_orders,
            supervisor_id=data.supervisor_id,
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
            company=data.company,
        )
        self.db.add(team)
        self.db.flush()
        return team

    def update_team(
        self,
        team_id: int,
        data: TeamUpdateData,
    ) -> FieldTeam:
        """Update a field team.

        Args:
            team_id: ID of the team to update
            data: Team update data

        Returns:
            The updated team (not yet committed)

        Raises:
            NotFoundError: If team not found
        """
        team = self.get_team(team_id)

        if data.name is not None:
            team.name = data.name
        if data.description is not None:
            team.description = data.description
        if data.coverage_zone_ids is not None:
            team.coverage_zone_ids = data.coverage_zone_ids
        if data.max_daily_orders is not None:
            team.max_daily_orders = data.max_daily_orders
        if data.supervisor_id is not None:
            team.supervisor_id = data.supervisor_id
        if data.contact_phone is not None:
            team.contact_phone = data.contact_phone
        if data.contact_email is not None:
            team.contact_email = data.contact_email
        if data.is_active is not None:
            team.is_active = data.is_active

        return team

    def deactivate_team(self, team_id: int) -> FieldTeam:
        """Deactivate a field team.

        Args:
            team_id: ID of the team to deactivate

        Returns:
            The deactivated team

        Raises:
            NotFoundError: If team not found
        """
        team = self.get_team(team_id)
        team.is_active = False
        return team

    # -------------------------------------------------------------------------
    # Team Member Methods
    # -------------------------------------------------------------------------

    def add_member(
        self,
        team_id: int,
        data: TeamMemberData,
    ) -> FieldTeamMember:
        """Add a member to a team.

        Args:
            team_id: ID of the team
            data: Team member data

        Returns:
            The created or reactivated team member

        Raises:
            NotFoundError: If team or employee not found
            ValidationError: If already an active member
        """
        from app.services.errors import NotFoundError, ValidationError

        team = self.get_team(team_id)

        employee = self.db.query(Employee).filter(Employee.id == data.employee_id).first()
        if not employee:
            raise NotFoundError(f"Employee with ID {data.employee_id} not found")
        if not employee.party_id:
            raise NotFoundError(f"Employee {data.employee_id} has no party_id")

        # Check if already a member
        existing = (
            self.db.query(FieldTeamMember)
            .filter(
                FieldTeamMember.team_id == team_id,
                FieldTeamMember.party_id == employee.party_id,
            )
            .first()
        )

        if existing:
            if existing.is_active:
                raise ValidationError("Employee is already a member of this team")
            # Reactivate
            existing.is_active = True
            existing.role = data.role
            return existing

        member = FieldTeamMember(
            team_id=team_id,
            party_id=employee.party_id,
            role=data.role,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def remove_member(
        self,
        team_id: int,
        employee_id: int,
    ) -> None:
        """Remove a member from a team.

        Args:
            team_id: ID of the team
            employee_id: ID of the employee to remove

        Raises:
            NotFoundError: If team member not found
        """
        from app.services.errors import NotFoundError

        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee or not employee.party_id:
            raise NotFoundError(f"Employee with ID {employee_id} not found")

        member = (
            self.db.query(FieldTeamMember)
            .filter(
                FieldTeamMember.team_id == team_id,
                FieldTeamMember.party_id == employee.party_id,
            )
            .first()
        )

        if not member:
            raise NotFoundError("Team member not found")

        member.is_active = False

    # -------------------------------------------------------------------------
    # Technician Methods
    # -------------------------------------------------------------------------

    def list_technicians(
        self,
        filters: Optional[TechnicianFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Employee]:
        """List field technicians with filtering and pagination.

        Args:
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Paginated list of employees who are technicians
        """
        if filters is None:
            filters = TechnicianFilters()
        if pagination is None:
            pagination = PaginationParams()

        # Get employees who are team members
        query = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True,
            ),
        ).distinct()

        if filters.team_id:
            query = query.filter(FieldTeamMember.team_id == filters.team_id)

        if filters.skill_type:
            query = query.join(
                TechnicianSkill,
                TechnicianSkill.employee_id == Employee.id,
            ).filter(
                TechnicianSkill.skill_type == filters.skill_type,
                TechnicianSkill.is_active == True,
            )

        if filters.search:
            query = query.filter(Employee.name.ilike(f"%{filters.search}%"))

        if filters.company:
            query = query.filter(Employee.company == filters.company)

        total = query.count()
        technicians = (
            query.offset(pagination.offset)
            .limit(pagination.limit)
            .all()
        )

        return PaginatedResult(
            items=technicians,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_technician(self, technician_id: int) -> Employee:
        """Get a technician by ID.

        Args:
            technician_id: ID of the technician (employee)

        Returns:
            The employee

        Raises:
            NotFoundError: If not found
        """
        from app.services.errors import NotFoundError

        tech = self.db.query(Employee).filter(Employee.id == technician_id).first()
        if not tech:
            raise NotFoundError(f"Technician with ID {technician_id} not found")
        return tech

    def get_technician_skills(self, technician_id: int) -> List[TechnicianSkill]:
        """Get skills for a technician.

        Args:
            technician_id: ID of the technician

        Returns:
            List of active skills
        """
        return (
            self.db.query(TechnicianSkill)
            .filter(
                TechnicianSkill.employee_id == technician_id,
                TechnicianSkill.is_active == True,
            )
            .all()
        )

    def get_technician_teams(self, technician_id: int) -> List[FieldTeamMember]:
        """Get team memberships for a technician.

        Args:
            technician_id: ID of the technician

        Returns:
            List of active team memberships
        """
        employee = self.db.query(Employee).filter(Employee.id == technician_id).first()
        if not employee or not employee.party_id:
            return []
        return (
            self.db.query(FieldTeamMember)
            .filter(
                FieldTeamMember.party_id == employee.party_id,
                FieldTeamMember.is_active == True,
            )
            .all()
        )

    # -------------------------------------------------------------------------
    # Skill Methods
    # -------------------------------------------------------------------------

    def add_skill(
        self,
        technician_id: int,
        data: TechnicianSkillData,
    ) -> TechnicianSkill:
        """Add a skill to a technician.

        Args:
            technician_id: ID of the technician
            data: Skill data

        Returns:
            The created skill

        Raises:
            NotFoundError: If technician not found
        """
        from app.services.errors import NotFoundError

        employee = self.db.query(Employee).filter(Employee.id == technician_id).first()
        if not employee:
            raise NotFoundError(f"Technician with ID {technician_id} not found")

        skill = TechnicianSkill(
            employee_id=technician_id,
            skill_type=data.skill_type,
            proficiency_level=data.proficiency_level,
            certification=data.certification,
            certification_number=data.certification_number,
            certification_date=data.certification_date,
            certification_expiry=data.certification_expiry,
        )
        self.db.add(skill)
        self.db.flush()
        return skill

    def remove_skill(
        self,
        technician_id: int,
        skill_id: int,
    ) -> None:
        """Remove a skill from a technician.

        Args:
            technician_id: ID of the technician
            skill_id: ID of the skill to remove

        Raises:
            NotFoundError: If skill not found
        """
        from app.services.errors import NotFoundError

        skill = (
            self.db.query(TechnicianSkill)
            .filter(
                TechnicianSkill.id == skill_id,
                TechnicianSkill.employee_id == technician_id,
            )
            .first()
        )

        if not skill:
            raise NotFoundError("Skill not found")

        skill.is_active = False

    # -------------------------------------------------------------------------
    # Zone Methods
    # -------------------------------------------------------------------------

    def list_zones(
        self,
        filters: Optional[ZoneFilters] = None,
    ) -> List[ServiceZone]:
        """List service zones.

        Args:
            filters: Optional filters

        Returns:
            List of zones
        """
        if filters is None:
            filters = ZoneFilters()

        query = self.db.query(ServiceZone)

        if filters.is_active is not None:
            query = query.filter(ServiceZone.is_active == filters.is_active)
        if filters.company:
            query = query.filter(ServiceZone.company == filters.company)

        return query.order_by(ServiceZone.name).all()

    def get_zone(self, zone_id: int) -> ServiceZone:
        """Get a zone by ID.

        Args:
            zone_id: ID of the zone

        Returns:
            The zone

        Raises:
            NotFoundError: If not found
        """
        from app.services.errors import NotFoundError

        zone = self.db.query(ServiceZone).filter(ServiceZone.id == zone_id).first()
        if not zone:
            raise NotFoundError(f"Zone with ID {zone_id} not found")
        return zone

    def create_zone(self, data: ZoneCreateData) -> ServiceZone:
        """Create a service zone.

        Args:
            data: Zone creation data

        Returns:
            The created zone

        Raises:
            ValidationError: If zone code already exists
        """
        from app.services.errors import ValidationError

        existing = (
            self.db.query(ServiceZone).filter(ServiceZone.code == data.code).first()
        )
        if existing:
            raise ValidationError(f"Zone with code '{data.code}' already exists")

        zone = ServiceZone(
            name=data.name,
            code=data.code,
            description=data.description,
            coverage_areas=data.coverage_areas,
            center_latitude=data.center_latitude,
            center_longitude=data.center_longitude,
            default_team_id=data.default_team_id,
            company=data.company,
        )
        self.db.add(zone)
        self.db.flush()
        return zone

    def update_zone(
        self,
        zone_id: int,
        data: ZoneUpdateData,
    ) -> ServiceZone:
        """Update a service zone.

        Args:
            zone_id: ID of the zone to update
            data: Zone update data

        Returns:
            The updated zone

        Raises:
            NotFoundError: If not found
        """
        zone = self.get_zone(zone_id)

        if data.name is not None:
            zone.name = data.name
        if data.description is not None:
            zone.description = data.description
        if data.coverage_areas is not None:
            zone.coverage_areas = data.coverage_areas
        if data.center_latitude is not None:
            zone.center_latitude = data.center_latitude
        if data.center_longitude is not None:
            zone.center_longitude = data.center_longitude
        if data.default_team_id is not None:
            zone.default_team_id = data.default_team_id
        if data.is_active is not None:
            zone.is_active = data.is_active

        return zone
