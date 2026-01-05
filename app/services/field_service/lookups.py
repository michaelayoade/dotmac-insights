"""Field service lookup helpers for UI routes.

Provides read-only queries for select options and related entities.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee, EmploymentStatus
from app.models.field_service import FieldTeam, FieldTeamMember, ServiceZone
from app.models.party import CustomerAccount, Party
from app.models.project import Project
from app.models.unified_ticket import UnifiedTicket


class FieldServiceLookupService:
    """Lookup service for field service UI data.

    Encapsulates simple queries so routes avoid direct DB access.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------------------------------------------------------------
    # Customers
    # ---------------------------------------------------------------------

    def list_customers(self, limit: int = 100) -> List[CustomerAccount]:
        return (
            self.db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(limit)
            .all()
        )

    def get_customer(self, customer_account_id: int) -> Optional[CustomerAccount]:
        return (
            self.db.query(CustomerAccount)
            .options(joinedload(CustomerAccount.party))
            .filter(CustomerAccount.id == customer_account_id)
            .first()
        )

    def get_project(self, project_id: int) -> Optional[Project]:
        return (
            self.db.query(Project)
            .filter(Project.id == project_id)
            .first()
        )

    def get_unified_ticket(self, ticket_id: int) -> Optional[UnifiedTicket]:
        return (
            self.db.query(UnifiedTicket)
            .filter(UnifiedTicket.id == ticket_id)
            .first()
        )

    # ---------------------------------------------------------------------
    # Employees & Teams
    # ---------------------------------------------------------------------

    def list_employees(
        self,
        limit: int = 100,
        active_only: bool = False,
        exclude_ids: Optional[Iterable[int]] = None,
    ) -> List[Employee]:
        query = self.db.query(Employee).filter(Employee.is_deleted == False)
        if active_only:
            query = query.filter(Employee.status == EmploymentStatus.ACTIVE)
        if exclude_ids:
            exclude_list = [int(emp_id) for emp_id in exclude_ids]
            if exclude_list:
                query = query.filter(~Employee.id.in_(exclude_list))
        return query.order_by(Employee.name).limit(limit).all()

    def list_technician_options(self, limit: int = 250) -> List[dict]:
        employees = self.list_employees(limit=limit, active_only=True)
        options = []
        for emp in employees:
            label = f"{emp.first_name} {emp.last_name}".strip()
            if not label:
                label = emp.email or emp.name or f"Employee {emp.id}"
            options.append({"value": str(emp.id), "label": label})
        return options

    def list_teams(self, active_only: bool = True) -> List[FieldTeam]:
        query = self.db.query(FieldTeam)
        if active_only:
            query = query.filter(FieldTeam.is_active == True)
        return query.order_by(FieldTeam.name).all()

    def list_team_options(self) -> List[dict]:
        return [
            {"value": str(team.id), "label": team.name}
            for team in self.list_teams(active_only=True)
        ]

    def list_zones(self, active_only: bool = True) -> List[ServiceZone]:
        query = self.db.query(ServiceZone)
        if active_only:
            query = query.filter(ServiceZone.is_active == True)
        return query.order_by(ServiceZone.name).all()

    def list_zone_options(self) -> List[dict]:
        return [
            {"value": str(zone.id), "label": zone.name}
            for zone in self.list_zones(active_only=True)
        ]

    def list_team_members(
        self,
        team_id: int,
        active_only: bool = False,
    ) -> List[FieldTeamMember]:
        query = (
            self.db.query(FieldTeamMember)
            .options(joinedload(FieldTeamMember.employee))
            .filter(FieldTeamMember.team_id == team_id)
        )
        if active_only:
            query = query.filter(FieldTeamMember.is_active == True)
        return query.all()

    def count_team_members(self, team_id: int, active_only: bool = True) -> int:
        query = self.db.query(FieldTeamMember).filter(FieldTeamMember.team_id == team_id)
        if active_only:
            query = query.filter(FieldTeamMember.is_active == True)
        return query.count()

    def get_team_member(
        self,
        team_id: int,
        member_id: int,
    ) -> Optional[FieldTeamMember]:
        return (
            self.db.query(FieldTeamMember)
            .filter(FieldTeamMember.id == member_id, FieldTeamMember.team_id == team_id)
            .first()
        )
