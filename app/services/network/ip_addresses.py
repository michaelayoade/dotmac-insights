"""IP Address service - business logic for IPv4 address management.

This service encapsulates IP address-related business logic:
- Listing and retrieval of addresses
- Address statistics and utilization

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.ipv4_address import IPv4Address
from app.services.base import paginate
from app.services.errors import NotFoundError
from app.services.types import PaginatedResult, PaginationParams

from .network_types import IPv4AddressFilters

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["IPAddressService"]


class IPAddressService:
    """Service for IP address management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    def list_addresses(
        self,
        filters: Optional[IPv4AddressFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[IPv4Address]:
        """List IPv4 addresses with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing addresses and total count.
        """
        query = self.db.query(IPv4Address)

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        IPv4Address.ip.ilike(like),
                        IPv4Address.hostname.ilike(like),
                        IPv4Address.title.ilike(like),
                    )
                )

            if filters.is_used is not None:
                query = query.filter(IPv4Address.is_used == filters.is_used)

            if filters.status:
                query = query.filter(IPv4Address.status == filters.status)

            if filters.network_id:
                query = query.filter(IPv4Address.ipv4_network_id == filters.network_id)

            if filters.module:
                query = query.filter(IPv4Address.module == filters.module)

        query = query.order_by(IPv4Address.ip)
        return paginate(query, pagination)

    def get_address(self, address_id: int) -> IPv4Address:
        """Get an IP address by ID.

        Args:
            address_id: The address ID.

        Returns:
            The IPv4Address.

        Raises:
            NotFoundError: If address not found.
        """
        addr = self.db.query(IPv4Address).filter(
            IPv4Address.id == address_id
        ).first()
        if not addr:
            raise NotFoundError(f"IPv4Address {address_id} not found")
        return addr

    def get_address_by_ip(self, ip: str) -> Optional[IPv4Address]:
        """Get an IP address by IP string.

        Args:
            ip: The IP address string.

        Returns:
            The IPv4Address or None if not found.
        """
        return self.db.query(IPv4Address).filter(IPv4Address.ip == ip).first()

    def get_address_by_splynx_id(self, splynx_id: int) -> Optional[IPv4Address]:
        """Get an IP address by Splynx ID.

        Args:
            splynx_id: The Splynx address ID.

        Returns:
            The IPv4Address or None if not found.
        """
        return self.db.query(IPv4Address).filter(
            IPv4Address.splynx_id == splynx_id
        ).first()

    def get_addresses_for_network(
        self, network_id: int, used_only: bool = False
    ) -> list[IPv4Address]:
        """Get all addresses in a network.

        Args:
            network_id: The network ID.
            used_only: Only return used addresses.

        Returns:
            List of IPv4Address.
        """
        query = self.db.query(IPv4Address).filter(
            IPv4Address.ipv4_network_id == network_id
        )
        if used_only:
            query = query.filter(IPv4Address.is_used == True)
        return query.order_by(IPv4Address.ip).all()

    def get_stats(self) -> dict:
        """Get IP address statistics.

        Returns:
            Dictionary with address statistics.
        """
        total = self.db.query(func.count(IPv4Address.id)).scalar() or 0
        used = self.db.query(func.count(IPv4Address.id)).filter(
            IPv4Address.is_used == True
        ).scalar() or 0

        return {
            "total_ips": total,
            "used_ips": used,
            "available_ips": total - used,
            "utilization": round(used / total * 100, 1) if total > 0 else 0,
        }

    def get_stats_by_network(self, network_id: int) -> dict:
        """Get IP address statistics for a specific network.

        Args:
            network_id: The network ID.

        Returns:
            Dictionary with address statistics for the network.
        """
        base = self.db.query(IPv4Address).filter(
            IPv4Address.ipv4_network_id == network_id
        )

        total = base.count()
        used = base.filter(IPv4Address.is_used == True).count()

        return {
            "network_id": network_id,
            "total_ips": total,
            "used_ips": used,
            "available_ips": total - used,
            "utilization": round(used / total * 100, 1) if total > 0 else 0,
        }
