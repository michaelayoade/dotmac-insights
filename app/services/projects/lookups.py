"""Project lookup helpers for UI routes."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee
from app.models.field_service import ServiceOrder
from app.models.party import CustomerAccount, Party
from app.models.project import Project
from app.models.unified_ticket import UnifiedTicket
from app.services.projects.milestones import MilestoneService
from app.services.projects.milestone_types import MilestoneFilters


class ProjectsLookupService:
    """Lookup service for project UI data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_customers(self, limit: int = 100) -> List[CustomerAccount]:
        return (
            self.db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(limit)
            .all()
        )

    def list_customer_options(self, limit: int = 100) -> List[dict]:
        customers = self.list_customers(limit=limit)
        return [
            {"value": str(c.id), "label": c.party.name if c.party else f"Account {c.id}"}
            for c in customers
        ]

    def list_manager_options(self) -> List[dict]:
        employees = (
            self.db.query(Employee)
            .filter(
                Employee.is_deleted == False,
                Employee.status == "active",
            )
            .order_by(Employee.first_name)
            .all()
        )
        return [
            {
                "value": str(e.id),
                "label": f"{e.first_name} {e.last_name}".strip() or e.email,
            }
            for e in employees
        ]

    def list_active_projects(self, limit: int = 200) -> List[Project]:
        return (
            self.db.query(Project)
            .filter(
                Project.is_deleted == False,
                Project.status.notin_(["completed", "cancelled"]),
            )
            .order_by(Project.project_name)
            .limit(limit)
            .all()
        )

    def list_project_options(self, limit: int = 100) -> List[dict]:
        projects = self.list_active_projects(limit=limit)
        return [
            {"value": str(project.id), "label": project.project_name}
            for project in projects
        ]

    def list_milestone_options(self, project_id: int) -> List[dict]:
        milestone_service = MilestoneService(self.db)
        milestones = milestone_service.list_project_milestones(
            project_id, MilestoneFilters()
        )
        return [
            {"value": str(milestone.id), "label": milestone.name}
            for milestone in milestones
        ]

    def get_employee(self, employee_id: int) -> Optional[Employee]:
        return self.db.query(Employee).filter(Employee.id == employee_id).first()

    def list_related_service_orders(
        self,
        project_id: int,
        limit: int = 10,
    ) -> List[ServiceOrder]:
        return (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.project_id == project_id)
            .order_by(ServiceOrder.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_service_order_stats(self, project_id: int) -> dict:
        total = (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.project_id == project_id)
            .count()
        )
        return {"total": total}

    def list_related_tickets(
        self,
        project_name: str,
        limit: int = 10,
    ) -> List[UnifiedTicket]:
        return (
            self.db.query(UnifiedTicket)
            .options(joinedload(UnifiedTicket.assignee))
            .filter(
                UnifiedTicket.project_name == project_name,
                UnifiedTicket.is_deleted == False,
            )
            .order_by(UnifiedTicket.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_ticket_stats(self, project_name: str) -> dict:
        total = (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.project_name == project_name,
                UnifiedTicket.is_deleted == False,
            )
            .count()
        )
        open_count = (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.project_name == project_name,
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.status.in_(["open", "in_progress"]),
            )
            .count()
        )
        return {"total": total, "open": open_count}
