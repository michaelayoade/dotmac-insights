"""Tariff service - business logic for tariff/plan management.

This service encapsulates tariff-related business logic:
- Core listing and retrieval of tariffs
- Subscription count aggregations
- Tariff statistics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.tariff import Tariff, TariffType
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError
from app.services.types import PaginatedResult, PaginationParams

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TariffService"]


class TariffService:
    """Service for tariff management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    def list_tariffs(
        self,
        tariff_type: Optional[str] = None,
        enabled_only: bool = True,
        search: Optional[str] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Tariff]:
        """List tariffs with optional filters.

        Args:
            tariff_type: Filter by tariff type (internet, recurring, one_time).
            enabled_only: Only return enabled tariffs.
            search: Search by title.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing tariffs and total count.
        """
        query = self.db.query(Tariff)

        if enabled_only:
            query = query.filter(Tariff.enabled == True)

        if tariff_type:
            try:
                type_enum = TariffType(tariff_type)
                query = query.filter(Tariff.tariff_type == type_enum)
            except ValueError:
                pass

        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    Tariff.title.ilike(like),
                    Tariff.service_name.ilike(like),
                )
            )

        query = query.order_by(Tariff.title)
        return paginate(query, pagination)

    def get_tariff(self, tariff_id: int) -> Tariff:
        """Get a tariff by ID.

        Args:
            tariff_id: The tariff ID.

        Returns:
            The Tariff.

        Raises:
            NotFoundError: If tariff not found.
        """
        tariff = self.db.query(Tariff).filter(Tariff.id == tariff_id).first()
        if not tariff:
            raise NotFoundError(f"Tariff {tariff_id} not found")
        return tariff

    def get_tariff_by_splynx_id(
        self, splynx_id: int, tariff_type: str = "internet"
    ) -> Optional[Tariff]:
        """Get a tariff by Splynx ID and type.

        Args:
            splynx_id: The Splynx tariff ID.
            tariff_type: The tariff type.

        Returns:
            The Tariff or None if not found.
        """
        try:
            type_enum = TariffType(tariff_type)
        except ValueError:
            return None

        return self.db.query(Tariff).filter(
            Tariff.splynx_id == splynx_id,
            Tariff.tariff_type == type_enum,
        ).first()

    def get_subscription_count(self, tariff_id: int) -> int:
        """Get count of active subscriptions using this tariff.

        Args:
            tariff_id: The tariff ID.

        Returns:
            Count of active subscriptions.
        """
        return self.db.query(func.count(Subscription.id)).filter(
            Subscription.tariff_id == tariff_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).scalar() or 0

    def get_tariff_stats(self, tariff_id: int) -> dict:
        """Get statistics for a tariff.

        Args:
            tariff_id: The tariff ID.

        Returns:
            Dictionary with tariff statistics.
        """
        tariff = self.get_tariff(tariff_id)

        active = self.db.query(func.count(Subscription.id)).filter(
            Subscription.tariff_id == tariff_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).scalar() or 0

        total = self.db.query(func.count(Subscription.id)).filter(
            Subscription.tariff_id == tariff_id,
        ).scalar() or 0

        mrr = self.db.query(func.sum(Subscription.price)).filter(
            Subscription.tariff_id == tariff_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).scalar() or Decimal("0")

        return {
            "tariff_id": tariff_id,
            "tariff_title": tariff.title,
            "tariff_type": tariff.tariff_type.value,
            "price": float(tariff.price),
            "active_subscriptions": active,
            "total_subscriptions": total,
            "mrr": float(mrr),
        }

    def get_overview_stats(self) -> dict:
        """Get overall tariff statistics.

        Returns:
            Dictionary with overview statistics.
        """
        total = self.db.query(func.count(Tariff.id)).scalar() or 0

        internet = self.db.query(func.count(Tariff.id)).filter(
            Tariff.tariff_type == TariffType.INTERNET,
            Tariff.enabled == True,
        ).scalar() or 0

        recurring = self.db.query(func.count(Tariff.id)).filter(
            Tariff.tariff_type == TariffType.RECURRING,
            Tariff.enabled == True,
        ).scalar() or 0

        one_time = self.db.query(func.count(Tariff.id)).filter(
            Tariff.tariff_type == TariffType.ONE_TIME,
            Tariff.enabled == True,
        ).scalar() or 0

        return {
            "total": total,
            "internet": internet,
            "recurring": recurring,
            "one_time": one_time,
        }
