"""IP Network services - business logic for IPv4/IPv6 network management.

This service encapsulates IP network-related business logic:
- Listing and retrieval of networks
- Network statistics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.ipv4_network import IPv4Network
from app.models.ipv6_network import IPv6Network
from app.services.base import paginate
from app.services.errors import NotFoundError
from app.services.types import PaginatedResult, PaginationParams

from .network_types import IPv4NetworkFilters, IPv6NetworkFilters

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["IPv4NetworkService", "IPv6NetworkService"]


class IPv4NetworkService:
    """Service for IPv4 network management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    def list_networks(
        self,
        filters: Optional[IPv4NetworkFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[IPv4Network]:
        """List IPv4 networks with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing networks and total count.
        """
        query = self.db.query(IPv4Network)

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        IPv4Network.network.ilike(like),
                        IPv4Network.title.ilike(like),
                    )
                )

            if filters.network_type:
                query = query.filter(IPv4Network.network_type == filters.network_type)

            if filters.type_of_usage:
                query = query.filter(IPv4Network.type_of_usage == filters.type_of_usage)

            if filters.location_id:
                query = query.filter(IPv4Network.location_id == filters.location_id)

            if filters.parent_id:
                query = query.filter(IPv4Network.parent_id == filters.parent_id)

        query = query.order_by(IPv4Network.network)
        return paginate(query, pagination)

    def get_network(self, network_id: int) -> IPv4Network:
        """Get an IPv4 network by ID.

        Args:
            network_id: The network ID.

        Returns:
            The IPv4Network.

        Raises:
            NotFoundError: If network not found.
        """
        network = self.db.query(IPv4Network).filter(
            IPv4Network.id == network_id
        ).first()
        if not network:
            raise NotFoundError(f"IPv4Network {network_id} not found")
        return network

    def get_network_by_splynx_id(self, splynx_id: int) -> Optional[IPv4Network]:
        """Get an IPv4 network by Splynx ID.

        Args:
            splynx_id: The Splynx network ID.

        Returns:
            The IPv4Network or None if not found.
        """
        return self.db.query(IPv4Network).filter(
            IPv4Network.splynx_id == splynx_id
        ).first()

    def get_child_networks(self, parent_id: int) -> list[IPv4Network]:
        """Get child networks of a parent network.

        Args:
            parent_id: The parent network ID.

        Returns:
            List of child IPv4Network.
        """
        return self.db.query(IPv4Network).filter(
            IPv4Network.parent_id == parent_id
        ).order_by(IPv4Network.network).all()

    def get_stats(self) -> dict:
        """Get overall IPv4 network statistics.

        Returns:
            Dictionary with network statistics.
        """
        total = self.db.query(func.count(IPv4Network.id)).scalar() or 0
        root_networks = self.db.query(func.count(IPv4Network.id)).filter(
            IPv4Network.network_type == "rootnet"
        ).scalar() or 0
        end_networks = self.db.query(func.count(IPv4Network.id)).filter(
            IPv4Network.network_type == "endnet"
        ).scalar() or 0

        # Usage breakdown
        pools = self.db.query(func.count(IPv4Network.id)).filter(
            IPv4Network.type_of_usage == "pool"
        ).scalar() or 0
        static = self.db.query(func.count(IPv4Network.id)).filter(
            IPv4Network.type_of_usage == "static"
        ).scalar() or 0
        management = self.db.query(func.count(IPv4Network.id)).filter(
            IPv4Network.type_of_usage == "management"
        ).scalar() or 0

        return {
            "total_networks": total,
            "root_networks": root_networks,
            "end_networks": end_networks,
            "pools": pools,
            "static": static,
            "management": management,
        }


class IPv6NetworkService:
    """Service for IPv6 network management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    def list_networks(
        self,
        filters: Optional[IPv6NetworkFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[IPv6Network]:
        """List IPv6 networks with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing networks and total count.
        """
        query = self.db.query(IPv6Network)

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        IPv6Network.network.ilike(like),
                        IPv6Network.title.ilike(like),
                    )
                )

            if filters.network_type:
                query = query.filter(IPv6Network.network_type == filters.network_type)

            if filters.type_of_usage:
                query = query.filter(IPv6Network.type_of_usage == filters.type_of_usage)

            if filters.location_id:
                query = query.filter(IPv6Network.location_id == filters.location_id)

        query = query.order_by(IPv6Network.network)
        return paginate(query, pagination)

    def get_network(self, network_id: int) -> IPv6Network:
        """Get an IPv6 network by ID.

        Args:
            network_id: The network ID.

        Returns:
            The IPv6Network.

        Raises:
            NotFoundError: If network not found.
        """
        network = self.db.query(IPv6Network).filter(
            IPv6Network.id == network_id
        ).first()
        if not network:
            raise NotFoundError(f"IPv6Network {network_id} not found")
        return network

    def get_stats(self) -> dict:
        """Get overall IPv6 network statistics.

        Returns:
            Dictionary with network statistics.
        """
        total = self.db.query(func.count(IPv6Network.id)).scalar() or 0

        return {
            "total_networks": total,
        }
