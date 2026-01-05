"""Network dashboard and analytics query service."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.ipv4_network import IPv4Network
from app.models.party import Party
from app.models.pop import Pop
from app.models.router import Router
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.ticket import Ticket, TicketStatus


class NetworkDashboardService:
    """Encapsulates network analytics queries for web routes."""

    def __init__(self, db: Session):
        self.db = db

    def get_customer_distribution(self) -> tuple[int, int]:
        customers_with_pop = (
            self.db.query(func.count(func.distinct(Subscription.party_id)))
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id.isnot(None), Subscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
            or 0
        )
        total_customers = (
            self.db.query(func.count(func.distinct(Subscription.party_id)))
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
            or 0
        )
        return customers_with_pop, total_customers

    def get_top_pops(self, limit: int = 10) -> list:
        customer_counts = (
            self.db.query(
                Router.pop_id.label("pop_id"),
                func.count(func.distinct(Subscription.party_id)).label("customer_count"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(Router.pop_id)
            .subquery()
        )

        return (
            self.db.query(
                Pop.id,
                Pop.name,
                Pop.city,
                func.coalesce(customer_counts.c.customer_count, 0).label("customer_count"),
            )
            .outerjoin(customer_counts, Pop.id == customer_counts.c.pop_id)
            .filter(Pop.is_active.is_(True))
            .order_by(func.coalesce(customer_counts.c.customer_count, 0).desc())
            .limit(limit)
            .all()
        )

    def get_network_ticket_count(self, since: datetime) -> int:
        return (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.created_at >= since,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
                or_(
                    Ticket.ticket_type.ilike("%network%"),
                    Ticket.ticket_type.ilike("%connectivity%"),
                    Ticket.issue_type.ilike("%network%"),
                ),
            )
            .scalar()
            or 0
        )

    def get_pop_enrichment(self, pop_ids: list[int]) -> list:
        if not pop_ids:
            return []

        customer_counts = (
            self.db.query(
                Router.pop_id,
                func.count(func.distinct(Subscription.party_id)).label("customer_count"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(Router.pop_id)
            .subquery()
        )

        router_counts = (
            self.db.query(
                Router.pop_id,
                func.count(Router.id).label("router_count"),
            )
            .group_by(Router.pop_id)
            .subquery()
        )

        return (
            self.db.query(
                Pop,
                func.coalesce(customer_counts.c.customer_count, 0).label("customer_count"),
                func.coalesce(router_counts.c.router_count, 0).label("router_count"),
            )
            .outerjoin(customer_counts, Pop.id == customer_counts.c.pop_id)
            .outerjoin(router_counts, Pop.id == router_counts.c.pop_id)
            .filter(Pop.id.in_(pop_ids))
            .order_by(func.coalesce(customer_counts.c.customer_count, 0).desc())
            .all()
        )

    def get_recent_customers(self, pop_id: int, limit: int = 10) -> list[Party]:
        return (
            self.db.query(Party)
            .join(Subscription, Subscription.party_id == Party.id)
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id == pop_id, Subscription.status == SubscriptionStatus.ACTIVE)
            .order_by(Party.created_at.desc())
            .distinct(Party.id)
            .limit(limit)
            .all()
        )

    def get_router_statuses(self) -> list[str]:
        statuses = (
            self.db.query(Router.status)
            .filter(Router.status.isnot(None))
            .distinct()
            .all()
        )
        return [status[0] for status in statuses if status[0]]

    def list_active_subscriptions(self, router_id: int, limit: int = 50) -> list[Subscription]:
        return (
            self.db.query(Subscription)
            .options(selectinload(Subscription.customer))
            .filter(
                Subscription.router_id == router_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.plan_name)
            .limit(limit)
            .all()
        )

    def get_networks_by_usage(self) -> list:
        return (
            self.db.query(
                IPv4Network.type_of_usage,
                func.count(IPv4Network.id).label("count"),
            )
            .filter(IPv4Network.type_of_usage.isnot(None))
            .group_by(IPv4Network.type_of_usage)
            .all()
        )

    def get_top_networks(self, limit: int = 10) -> list[IPv4Network]:
        return (
            self.db.query(IPv4Network)
            .filter(IPv4Network.network_type == "endnet")
            .order_by(IPv4Network.used.desc().nullslast())
            .limit(limit)
            .all()
        )

    def get_pop_ticket_count(self, pop_id: int, since: datetime) -> int:
        return (
            self.db.query(func.count(Ticket.id))
            .join(Party, Ticket.party_id == Party.id)
            .join(Subscription, Subscription.party_id == Party.id)
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id == pop_id, Ticket.created_at >= since)
            .scalar()
            or 0
        )

    def get_customers_without_pop(self) -> int:
        return (
            self.db.query(func.count(func.distinct(Subscription.party_id)))
            .filter(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.router_id.is_(None))
            .scalar()
            or 0
        )

    def get_pops_without_routers(self) -> list[Pop]:
        return (
            self.db.query(Pop)
            .outerjoin(Router, Pop.id == Router.pop_id)
            .filter(Pop.is_active.is_(True), Router.id.is_(None))
            .all()
        )

    def get_high_util_networks(self, limit: int = 15) -> list[IPv4Network]:
        return (
            self.db.query(IPv4Network)
            .filter(
                IPv4Network.network_type == "endnet",
                IPv4Network.total > 0,
                IPv4Network.used > 0,
                (IPv4Network.used * 100 / IPv4Network.total) > 80,
            )
            .order_by((IPv4Network.used * 100 / IPv4Network.total).desc())
            .limit(limit)
            .all()
        )

    def get_routers_without_subscriptions(self, limit: int = 20) -> list[Router]:
        return (
            self.db.query(Router)
            .outerjoin(
                Subscription,
                and_(
                    Subscription.router_id == Router.id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                ),
            )
            .filter(Subscription.id.is_(None))
            .limit(limit)
            .all()
        )
