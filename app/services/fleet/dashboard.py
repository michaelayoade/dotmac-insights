"""Dashboard service for fleet analytics.

This service handles:
- Fleet summary statistics
- Aggregated metrics
- Dashboard data
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle

from .vehicle_types import VehicleSummary

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["FleetDashboardService"]


class FleetDashboardService:
    """Service for computing fleet dashboard metrics.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for scoping if needed).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def get_fleet_summary(
        self,
        company: Optional[str] = None,
        insurance_expiry_days: int = 30,
    ) -> VehicleSummary:
        """Get comprehensive fleet summary statistics.

        Args:
            company: Optional company filter
            insurance_expiry_days: Days ahead to check for insurance expiry

        Returns:
            VehicleSummary with all fleet metrics
        """
        # Base condition for company filter
        base_condition = Vehicle.company == company if company else True

        # Count totals
        total = self.db.execute(
            select(func.count()).select_from(Vehicle).where(base_condition)
        ).scalar() or 0

        active = self.db.execute(
            select(func.count())
            .select_from(Vehicle)
            .where(
                and_(
                    base_condition,
                    Vehicle.is_active == True,
                )
            )
        ).scalar() or 0

        # By fuel type
        fuel_type_query = (
            select(Vehicle.fuel_type, func.count())
            .where(
                and_(
                    base_condition,
                    Vehicle.fuel_type.isnot(None),
                )
            )
            .group_by(Vehicle.fuel_type)
        )
        fuel_type_rows = self.db.execute(fuel_type_query).all()
        by_fuel_type: Dict[str, int] = {row[0]: row[1] for row in fuel_type_rows}

        # By make (top 10)
        make_query = (
            select(Vehicle.make, func.count())
            .where(
                and_(
                    base_condition,
                    Vehicle.make.isnot(None),
                )
            )
            .group_by(Vehicle.make)
            .order_by(desc(func.count()))
            .limit(10)
        )
        make_rows = self.db.execute(make_query).all()
        by_make: Dict[str, int] = {row[0]: row[1] for row in make_rows}

        # Insurance expiring soon
        expiry_threshold = date.today() + timedelta(days=insurance_expiry_days)
        insurance_expiring = self.db.execute(
            select(func.count())
            .select_from(Vehicle)
            .where(
                and_(
                    base_condition,
                    Vehicle.is_active == True,
                    Vehicle.insurance_end_date.isnot(None),
                    Vehicle.insurance_end_date <= expiry_threshold,
                    Vehicle.insurance_end_date >= date.today(),
                )
            )
        ).scalar() or 0

        # Total value and avg odometer
        totals = self.db.execute(
            select(
                func.coalesce(func.sum(Vehicle.vehicle_value), 0),
                func.coalesce(func.avg(Vehicle.odometer_value), 0),
            ).where(base_condition)
        ).one_or_none()

        if totals is None:
            total_value = Decimal("0")
            avg_odometer = Decimal("0")
        else:
            total_value = Decimal(str(totals[0]))
            avg_odometer = Decimal(str(round(float(totals[1]), 2)))

        return VehicleSummary(
            total_vehicles=total,
            active_vehicles=active,
            inactive_vehicles=total - active,
            by_fuel_type=by_fuel_type,
            by_make=by_make,
            insurance_expiring_soon=insurance_expiring,
            total_value=total_value,
            avg_odometer=avg_odometer,
        )

    def get_by_fuel_type(
        self,
        company: Optional[str] = None,
    ) -> Dict[str, int]:
        """Get vehicle count by fuel type.

        Args:
            company: Optional company filter

        Returns:
            Dict mapping fuel type to count
        """
        base_condition = Vehicle.company == company if company else True

        query = (
            select(Vehicle.fuel_type, func.count())
            .where(
                and_(
                    base_condition,
                    Vehicle.fuel_type.isnot(None),
                )
            )
            .group_by(Vehicle.fuel_type)
            .order_by(desc(func.count()))
        )
        rows = self.db.execute(query).all()
        return {row[0]: row[1] for row in rows}

    def get_by_make(
        self,
        company: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, int]:
        """Get vehicle count by make.

        Args:
            company: Optional company filter
            limit: Maximum number of makes to return

        Returns:
            Dict mapping make to count
        """
        base_condition = Vehicle.company == company if company else True

        query = (
            select(Vehicle.make, func.count())
            .where(
                and_(
                    base_condition,
                    Vehicle.make.isnot(None),
                )
            )
            .group_by(Vehicle.make)
            .order_by(desc(func.count()))
            .limit(limit)
        )
        rows = self.db.execute(query).all()
        return {row[0]: row[1] for row in rows}

    def get_insurance_expiry_summary(
        self,
        company: Optional[str] = None,
    ) -> Dict[str, int]:
        """Get insurance expiry summary by time period.

        Args:
            company: Optional company filter

        Returns:
            Dict with counts: expired, expiring_7_days, expiring_30_days, expiring_90_days
        """
        base_condition = Vehicle.company == company if company else True
        today = date.today()

        def count_in_range(start: date, end: Optional[date] = None) -> int:
            conditions = [
                base_condition,
                Vehicle.is_active == True,
                Vehicle.insurance_end_date.isnot(None),
            ]
            if end is not None:
                conditions.append(Vehicle.insurance_end_date >= start)
                conditions.append(Vehicle.insurance_end_date <= end)
            else:
                conditions.append(Vehicle.insurance_end_date < start)

            return self.db.execute(
                select(func.count())
                .select_from(Vehicle)
                .where(and_(*conditions))
            ).scalar() or 0

        return {
            "expired": count_in_range(today),
            "expiring_7_days": count_in_range(today, today + timedelta(days=7)),
            "expiring_30_days": count_in_range(today, today + timedelta(days=30)),
            "expiring_90_days": count_in_range(today, today + timedelta(days=90)),
        }

    def get_acquisition_trend(
        self,
        company: Optional[str] = None,
        months: int = 12,
    ) -> Dict[str, int]:
        """Get vehicle acquisition trend by month.

        Args:
            company: Optional company filter
            months: Number of months to look back

        Returns:
            Dict mapping "YYYY-MM" to acquisition count
        """
        from sqlalchemy import extract

        base_condition = Vehicle.company == company if company else True
        cutoff = date.today() - timedelta(days=months * 30)

        query = (
            select(
                extract("year", Vehicle.acquisition_date).label("year"),
                extract("month", Vehicle.acquisition_date).label("month"),
                func.count(Vehicle.id).label("count"),
            )
            .where(
                and_(
                    base_condition,
                    Vehicle.acquisition_date.isnot(None),
                    Vehicle.acquisition_date >= cutoff,
                )
            )
            .group_by(
                extract("year", Vehicle.acquisition_date),
                extract("month", Vehicle.acquisition_date),
            )
            .order_by(
                extract("year", Vehicle.acquisition_date),
                extract("month", Vehicle.acquisition_date),
            )
        )
        rows = self.db.execute(query).all()

        return {
            f"{int(row.year)}-{int(row.month):02d}": row.count
            for row in rows
        }
