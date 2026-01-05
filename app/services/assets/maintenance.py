"""Asset maintenance service - business logic for asset maintenance operations.

This service encapsulates all maintenance-related business logic:
- Track assets requiring maintenance
- Manage maintenance status
- Track warranty and insurance expiry
- Generate alerts for upcoming due dates

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset, AssetStatus

from app.services.errors import NotFoundError, ValidationError
from app.services.validation.soft_validation_service import SoftValidationService

from .types import (
    MaintenanceFilters,
    MaintenanceCompleteData,
    AssetAlert,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AssetMaintenanceService"]


class AssetMaintenanceService:
    """Service for asset maintenance business logic.

    Handles maintenance tracking, warranty monitoring, and insurance expiry alerts.

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
    # Maintenance Queries
    # -------------------------------------------------------------------------

    def get_assets_requiring_maintenance(
        self,
        filters: Optional[MaintenanceFilters] = None,
    ) -> List[Asset]:
        """Get assets that require maintenance.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of assets marked as requiring maintenance.
        """
        query = self.db.query(Asset).filter(
            Asset.maintenance_required == True,
            Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]),
        )

        if filters:
            if filters.location:
                query = query.filter(Asset.location == filters.location)
            if filters.custodian_id:
                query = query.filter(Asset.custodian_id == filters.custodian_id)

        return query.order_by(Asset.asset_name).all()

    def get_assets_in_maintenance(self) -> List[Asset]:
        """Get assets currently in maintenance.

        Returns:
            List of assets with IN_MAINTENANCE status.
        """
        return (
            self.db.query(Asset)
            .filter(Asset.status == AssetStatus.IN_MAINTENANCE)
            .order_by(Asset.updated_at.desc())
            .all()
        )

    def get_due_maintenance(self, days_ahead: int = 7) -> List[Asset]:
        """Get assets with maintenance due soon.

        Currently returns assets marked as requiring maintenance.
        Could be extended to support scheduled maintenance dates.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of assets with upcoming or overdue maintenance.
        """
        return self.get_assets_requiring_maintenance()

    # -------------------------------------------------------------------------
    # Maintenance Operations
    # -------------------------------------------------------------------------

    def mark_in_maintenance(self, asset_id: int) -> Asset:
        """Mark an asset as being in maintenance.

        Args:
            asset_id: The asset ID.

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If status transition not allowed.
        """
        asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        valid_statuses = [
            AssetStatus.SUBMITTED,
            AssetStatus.PARTIALLY_DEPRECIATED,
            AssetStatus.FULLY_DEPRECIATED,
        ]
        if asset.status not in valid_statuses:
            raise ValidationError(
                f"Cannot mark asset as in maintenance with status {asset.status.value}"
            )

        asset.status = AssetStatus.IN_MAINTENANCE
        asset.maintenance_required = True
        asset.updated_at = datetime.utcnow()

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(asset)
        return asset

    def complete_maintenance(
        self, asset_id: int, data: Optional[MaintenanceCompleteData] = None
    ) -> Asset:
        """Complete maintenance and return asset to service.

        Args:
            asset_id: The asset ID.
            data: Optional maintenance completion data.

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset not in maintenance.
        """
        asset = (
            self.db.query(Asset)
            .options(selectinload(Asset.depreciation_schedules))
            .filter(Asset.id == asset_id)
            .first()
        )
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        if asset.status != AssetStatus.IN_MAINTENANCE:
            raise ValidationError("Asset is not in maintenance")

        # Determine correct status based on depreciation
        if not asset.calculate_depreciation:
            asset.status = AssetStatus.SUBMITTED
        elif asset.asset_value <= Decimal("0"):
            asset.status = AssetStatus.FULLY_DEPRECIATED
        elif asset.depreciation_schedules:
            booked = sum(1 for s in asset.depreciation_schedules if s.depreciation_booked)
            if booked > 0:
                asset.status = AssetStatus.PARTIALLY_DEPRECIATED
            else:
                asset.status = AssetStatus.SUBMITTED
        else:
            asset.status = AssetStatus.SUBMITTED

        asset.maintenance_required = False
        asset.updated_at = datetime.utcnow()

        # Handle maintenance cost if provided
        if (
            data
            and data.maintenance_cost is not None
            and data.maintenance_cost > 0
            and data.capitalize_cost
        ):
            # Add maintenance cost to asset value
            asset.gross_purchase_amount = (asset.gross_purchase_amount or Decimal("0")) + data.maintenance_cost
            asset.asset_value = (asset.asset_value or Decimal("0")) + data.maintenance_cost

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(asset)
        return asset

    def mark_maintenance_required(self, asset_id: int, required: bool = True) -> Asset:
        """Mark or unmark an asset as requiring maintenance.

        This doesn't change the status, just sets the maintenance_required flag.

        Args:
            asset_id: The asset ID.
            required: Whether maintenance is required.

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
        """
        asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        asset.maintenance_required = required
        asset.updated_at = datetime.utcnow()

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(asset)
        return asset

    # -------------------------------------------------------------------------
    # Warranty Tracking
    # -------------------------------------------------------------------------

    def get_expiring_warranties(self, days_ahead: int = 30) -> List[Asset]:
        """Get assets with warranty expiring soon.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of assets with expiring warranties.
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        return (
            self.db.query(Asset)
            .filter(
                Asset.warranty_expiry_date.isnot(None),
                Asset.warranty_expiry_date >= today,
                Asset.warranty_expiry_date <= end_date,
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]),
            )
            .order_by(Asset.warranty_expiry_date)
            .all()
        )

    def get_expired_warranties(self) -> List[Asset]:
        """Get assets with expired warranties.

        Returns:
            List of assets with expired warranties that are still active.
        """
        today = date.today()

        return (
            self.db.query(Asset)
            .filter(
                Asset.warranty_expiry_date.isnot(None),
                Asset.warranty_expiry_date < today,
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]),
            )
            .order_by(Asset.warranty_expiry_date)
            .all()
        )

    # -------------------------------------------------------------------------
    # Insurance Tracking
    # -------------------------------------------------------------------------

    def get_expiring_insurance(self, days_ahead: int = 30) -> List[Asset]:
        """Get assets with insurance expiring soon.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of assets with expiring insurance.
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        return (
            self.db.query(Asset)
            .filter(
                Asset.insurance_end_date.isnot(None),
                Asset.insurance_end_date >= today,
                Asset.insurance_end_date <= end_date,
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]),
            )
            .order_by(Asset.insurance_end_date)
            .all()
        )

    def get_expired_insurance(self) -> List[Asset]:
        """Get assets with expired insurance.

        Returns:
            List of assets with expired insurance that are still active.
        """
        today = date.today()

        return (
            self.db.query(Asset)
            .filter(
                Asset.insurance_end_date.isnot(None),
                Asset.insurance_end_date < today,
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]),
            )
            .order_by(Asset.insurance_end_date)
            .all()
        )

    def get_uninsured_assets(self) -> List[Asset]:
        """Get assets without insurance.

        Returns:
            List of active assets without insurance coverage.
        """
        return (
            self.db.query(Asset)
            .filter(
                or_(
                    Asset.insurance_end_date.is_(None),
                    Asset.insured_value == Decimal("0"),
                ),
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED, AssetStatus.DRAFT]),
            )
            .order_by(Asset.asset_value.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------------------

    def get_all_alerts(self, days_ahead: int = 30) -> List[AssetAlert]:
        """Get all asset alerts (maintenance, warranty, insurance).

        Args:
            days_ahead: Number of days to look ahead for expiring items.

        Returns:
            List of AssetAlert objects for all alert types.
        """
        today = date.today()
        alerts: List[AssetAlert] = []

        # Maintenance alerts
        for asset in self.get_assets_requiring_maintenance():
            alerts.append(AssetAlert(
                alert_type="maintenance",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                location=asset.location,
                custodian_id=asset.custodian_id,
                custodian_name=asset.custodian,
                due_date=today,  # Overdue if maintenance_required
                days_until_due=0,
            ))

        # Warranty expiry alerts
        for asset in self.get_expiring_warranties(days_ahead):
            days_remaining = (asset.warranty_expiry_date - today).days
            alerts.append(AssetAlert(
                alert_type="warranty",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                location=asset.location,
                custodian_id=asset.custodian_id,
                custodian_name=asset.custodian,
                due_date=asset.warranty_expiry_date,
                days_until_due=days_remaining,
            ))

        # Insurance expiry alerts
        for asset in self.get_expiring_insurance(days_ahead):
            days_remaining = (asset.insurance_end_date - today).days
            alerts.append(AssetAlert(
                alert_type="insurance",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                location=asset.location,
                custodian_id=asset.custodian_id,
                custodian_name=asset.custodian,
                due_date=asset.insurance_end_date,
                days_until_due=days_remaining,
            ))

        # Sort by days until due (most urgent first)
        alerts.sort(key=lambda a: a.days_until_due)

        return alerts

    def get_alert_summary(self, days_ahead: int = 30) -> dict:
        """Get summary count of all alerts.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            Dictionary with alert counts by type.
        """
        return {
            "maintenance_required": len(self.get_assets_requiring_maintenance()),
            "warranty_expiring": len(self.get_expiring_warranties(days_ahead)),
            "warranty_expired": len(self.get_expired_warranties()),
            "insurance_expiring": len(self.get_expiring_insurance(days_ahead)),
            "insurance_expired": len(self.get_expired_insurance()),
            "uninsured": len(self.get_uninsured_assets()),
            "total": len(self.get_all_alerts(days_ahead)),
        }
