"""Operations dashboard service.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus
from app.models.field_service import ServiceOrder, ServiceOrderStatus
from app.models.inventory import Warehouse
from app.models.asset import Asset, AssetStatus
from app.models.vehicle import Vehicle

if TYPE_CHECKING:
    from app.auth import Principal


class OperationsDashboardService:
    """Service for operations module dashboard metrics."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def get_dashboard_counts(self) -> Dict[str, int]:
        """Return key counts for the operations dashboard."""
        active_projects = (
            self.db.query(func.count(Project.id))
            .filter(
                Project.status.in_([
                    ProjectStatus.OPEN,
                    ProjectStatus.ON_HOLD,
                ])
            )
            .scalar()
            or 0
        )

        open_orders = (
            self.db.query(func.count(ServiceOrder.id))
            .filter(
                ServiceOrder.status.in_([
                    ServiceOrderStatus.DRAFT,
                    ServiceOrderStatus.SCHEDULED,
                    ServiceOrderStatus.DISPATCHED,
                    ServiceOrderStatus.IN_PROGRESS,
                ])
            )
            .scalar()
            or 0
        )

        warehouse_count = (
            self.db.query(func.count(Warehouse.id))
            .filter(
                Warehouse.disabled == False,
                Warehouse.is_deleted == False,
            )
            .scalar()
            or 0
        )

        active_assets = (
            self.db.query(func.count(Asset.id))
            .filter(
                Asset.status.in_([
                    AssetStatus.SUBMITTED,
                    AssetStatus.PARTIALLY_DEPRECIATED,
                    AssetStatus.FULLY_DEPRECIATED,
                ])
            )
            .scalar()
            or 0
        )

        vehicle_count = (
            self.db.query(func.count(Vehicle.id))
            .filter(Vehicle.is_active == True)
            .scalar()
            or 0
        )

        return {
            "active_projects": active_projects,
            "open_orders": open_orders,
            "warehouse_count": warehouse_count,
            "active_assets": active_assets,
            "vehicle_count": vehicle_count,
        }
