"""POP service - business logic for Points of Presence management.

This service encapsulates POP-related business logic:
- Core CRUD for POPs
- Statistics and metrics
- Party (organization) linking

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.pop import Pop
from app.models.router import Router
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.party import Party
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .network_types import (
    PopFilters,
    PopCreateData,
    PopUpdateData,
    PopStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["PopService"]


class PopService:
    """Service for POP management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # POP CRUD
    # -------------------------------------------------------------------------

    def list_pops(
        self,
        filters: Optional[PopFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_counts: bool = False,
    ) -> PaginatedResult[Pop]:
        """List POPs with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_counts: Whether to include customer/router counts.

        Returns:
            PaginatedResult containing POPs and total count.
        """
        query = self.db.query(Pop)

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Pop.name.ilike(like),
                        Pop.code.ilike(like),
                        Pop.city.ilike(like),
                    )
                )

            if filters.city:
                query = query.filter(Pop.city.ilike(f"%{filters.city}%"))

            if filters.state:
                query = query.filter(Pop.state.ilike(f"%{filters.state}%"))

            if filters.is_active is not None:
                query = query.filter(Pop.is_active == filters.is_active)

            if filters.has_routers is not None:
                if filters.has_routers:
                    # Has at least one router
                    subq = self.db.query(Router.pop_id).filter(
                        Router.pop_id.isnot(None)
                    ).distinct().subquery()
                    query = query.filter(Pop.id.in_(subq))
                else:
                    # Has no routers
                    subq = self.db.query(Router.pop_id).filter(
                        Router.pop_id.isnot(None)
                    ).distinct().subquery()
                    query = query.filter(~Pop.id.in_(subq))

        query = query.order_by(Pop.name)
        return paginate(query, pagination)

    def get_pop(self, pop_id: int) -> Pop:
        """Get a POP by ID.

        Args:
            pop_id: The POP ID.

        Returns:
            The Pop.

        Raises:
            NotFoundError: If POP not found.
        """
        pop = self.db.query(Pop).filter(Pop.id == pop_id).first()
        if not pop:
            raise NotFoundError(f"POP {pop_id} not found")
        return pop

    def get_pop_by_splynx_id(self, splynx_id: int) -> Optional[Pop]:
        """Get a POP by Splynx ID.

        Args:
            splynx_id: The Splynx POP ID.

        Returns:
            The Pop or None if not found.
        """
        return self.db.query(Pop).filter(Pop.splynx_id == splynx_id).first()

    def create_pop(self, data: PopCreateData) -> Pop:
        """Create a new POP.

        Args:
            data: POP creation data.

        Returns:
            The created Pop (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        # Validate org party if provided
        if data.org_party_id:
            party = self.db.query(Party).filter(Party.id == data.org_party_id).first()
            if not party:
                raise ValidationError(f"Party {data.org_party_id} not found")

        pop = Pop(
            name=data.name,
            code=data.code,
            splynx_id=data.splynx_id,
            address=data.address,
            city=data.city,
            state=data.state,
            latitude=data.latitude,
            longitude=data.longitude,
            is_active=data.is_active,
        )

        self.db.add(pop)
        self.db.flush()

        return pop

    def update_pop(self, pop_id: int, data: PopUpdateData) -> Pop:
        """Update a POP.

        Args:
            pop_id: The POP ID.
            data: Fields to update.

        Returns:
            The updated Pop (not yet committed).

        Raises:
            NotFoundError: If POP not found.
        """
        pop = self.get_pop(pop_id)

        fields = ["name", "code", "address", "city", "state",
                  "latitude", "longitude", "is_active"]
        for field_name in fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(pop, field_name, value)

        return pop

    def delete_pop(self, pop_id: int) -> None:
        """Soft delete a POP (deactivate).

        Args:
            pop_id: The POP ID.

        Raises:
            NotFoundError: If POP not found.
        """
        pop = self.get_pop(pop_id)
        pop.is_active = False

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_pop_stats(self, pop_id: int) -> PopStats:
        """Get statistics for a POP.

        Args:
            pop_id: The POP ID.

        Returns:
            PopStats with metrics.
        """
        pop = self.get_pop(pop_id)

        customer_count = (
            self.db.query(func.count(func.distinct(Subscription.party_id)))
            .join(Router, Subscription.router_id == Router.id)
            .filter(
                Router.pop_id == pop_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .scalar()
            or 0
        )

        router_count = self.db.query(func.count(Router.id)).filter(
            Router.pop_id == pop_id,
        ).scalar() or 0

        # MRR via customer subscriptions
        mrr = (
            self.db.query(func.sum(Subscription.price))
            .join(Router, Subscription.router_id == Router.id)
            .filter(
                Router.pop_id == pop_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .scalar()
            or Decimal("0")
        )

        # Active subscriptions
        active_subscriptions = (
            self.db.query(func.count(Subscription.id))
            .join(Router, Subscription.router_id == Router.id)
            .filter(
                Router.pop_id == pop_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .scalar()
            or 0
        )

        return PopStats(
            pop_id=pop_id,
            pop_name=pop.name,
            customer_count=customer_count,
            active_subscriptions=active_subscriptions,
            router_count=router_count,
            mrr=mrr,
        )

    def get_cities(self) -> List[str]:
        """Get unique cities for filter dropdown.

        Returns:
            List of unique city names.
        """
        result = self.db.query(Pop.city).filter(
            Pop.city.isnot(None),
            Pop.city != "",
        ).distinct().order_by(Pop.city).all()
        return [r[0] for r in result if r[0]]

    def get_states(self) -> List[str]:
        """Get unique states for filter dropdown.

        Returns:
            List of unique state names.
        """
        result = self.db.query(Pop.state).filter(
            Pop.state.isnot(None),
            Pop.state != "",
        ).distinct().order_by(Pop.state).all()
        return [r[0] for r in result if r[0]]

    def get_overview_stats(self) -> dict:
        """Get overall POP statistics.

        Returns:
            Dictionary with overview statistics.
        """
        total = self.db.query(func.count(Pop.id)).scalar() or 0
        active = self.db.query(func.count(Pop.id)).filter(
            Pop.is_active == True
        ).scalar() or 0

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
        }
