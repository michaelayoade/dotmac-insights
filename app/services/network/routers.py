"""Router service - business logic for router/NAS management.

This service encapsulates router-related business logic:
- Core CRUD for routers
- Statistics and metrics
- POP relationships

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.router import Router
from app.models.pop import Pop
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .network_types import (
    RouterFilters,
    RouterCreateData,
    RouterUpdateData,
    RouterStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["RouterService"]


class RouterService:
    """Service for router management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Router CRUD
    # -------------------------------------------------------------------------

    def list_routers(
        self,
        filters: Optional[RouterFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_pop: bool = False,
    ) -> PaginatedResult[Router]:
        """List routers with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_pop: Whether to eagerly load POP relationship.

        Returns:
            PaginatedResult containing routers and total count.
        """
        query = self.db.query(Router)

        if include_pop:
            query = query.options(joinedload(Router.pop))

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Router.title.ilike(like),
                        Router.ip.ilike(like),
                        Router.nas_ip.ilike(like),
                        Router.model.ilike(like),
                    )
                )

            if filters.pop_id:
                query = query.filter(Router.pop_id == filters.pop_id)

            if filters.status:
                query = query.filter(Router.status == filters.status)

            if filters.nas_type:
                query = query.filter(Router.nas_type == filters.nas_type)

        query = query.order_by(Router.title)
        return paginate(query, pagination)

    def get_router(self, router_id: int, include_pop: bool = False) -> Router:
        """Get a router by ID.

        Args:
            router_id: The router ID.
            include_pop: Whether to eagerly load POP relationship.

        Returns:
            The Router.

        Raises:
            NotFoundError: If router not found.
        """
        query = self.db.query(Router)

        if include_pop:
            query = query.options(joinedload(Router.pop))

        router = query.filter(Router.id == router_id).first()
        if not router:
            raise NotFoundError(f"Router {router_id} not found")

        return router

    def get_router_by_splynx_id(self, splynx_id: int) -> Optional[Router]:
        """Get a router by Splynx ID.

        Args:
            splynx_id: The Splynx router ID.

        Returns:
            The Router or None if not found.
        """
        return self.db.query(Router).filter(Router.splynx_id == splynx_id).first()

    def create_router(self, data: RouterCreateData) -> Router:
        """Create a new router.

        Args:
            data: Router creation data.

        Returns:
            The created Router (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        # Validate POP if provided
        if data.pop_id:
            pop = self.db.query(Pop).filter(Pop.id == data.pop_id).first()
            if not pop:
                raise ValidationError(f"POP {data.pop_id} not found")

        router = Router(
            title=data.title,
            splynx_id=data.splynx_id,
            model=data.model,
            ip=data.ip,
            nas_ip=data.nas_ip,
            nas_type=data.nas_type,
            pop_id=data.pop_id,
            location_id=data.location_id,
            address=data.address,
            gps=data.gps,
            radius_secret=data.radius_secret,
            radius_coa_port=data.radius_coa_port,
            radius_accounting_interval=data.radius_accounting_interval,
            authorization_method=data.authorization_method,
            accounting_method=data.accounting_method,
            api_login=data.api_login,
            api_password=data.api_password,
            api_port=data.api_port,
            ssh_port=data.ssh_port,
            status=data.status,
        )

        self.db.add(router)
        self.db.flush()

        return router

    def update_router(self, router_id: int, data: RouterUpdateData) -> Router:
        """Update a router.

        Args:
            router_id: The router ID.
            data: Fields to update.

        Returns:
            The updated Router (not yet committed).

        Raises:
            NotFoundError: If router not found.
        """
        router = self.get_router(router_id)

        fields = ["title", "model", "ip", "nas_ip", "nas_type", "pop_id",
                  "status", "radius_secret", "api_login", "api_password"]
        for field_name in fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(router, field_name, value)

        return router

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_router_stats(self, router_id: int) -> RouterStats:
        """Get statistics for a router.

        Args:
            router_id: The router ID.

        Returns:
            RouterStats with metrics.
        """
        router = self.get_router(router_id)

        active = self.db.query(func.count(Subscription.id)).filter(
            Subscription.router_id == router_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).scalar() or 0

        total = self.db.query(func.count(Subscription.id)).filter(
            Subscription.router_id == router_id,
        ).scalar() or 0

        return RouterStats(
            router_id=router_id,
            router_title=router.title,
            active_subscriptions=active,
            total_subscriptions=total,
        )

    def get_routers_for_pop(self, pop_id: int) -> List[Router]:
        """Get all routers at a specific POP.

        Args:
            pop_id: The POP ID.

        Returns:
            List of Router.
        """
        return self.db.query(Router).filter(
            Router.pop_id == pop_id
        ).order_by(Router.title).all()

    def get_overview_stats(self) -> dict:
        """Get overall router statistics.

        Returns:
            Dictionary with overview statistics.
        """
        total = self.db.query(func.count(Router.id)).scalar() or 0
        with_ip = self.db.query(func.count(Router.id)).filter(
            Router.ip.isnot(None)
        ).scalar() or 0
        with_pop = self.db.query(func.count(Router.id)).filter(
            Router.pop_id.isnot(None)
        ).scalar() or 0

        return {
            "total": total,
            "with_ip": with_ip,
            "with_pop": with_pop,
        }
