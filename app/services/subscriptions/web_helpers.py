"""Helper services for subscription web routes."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.router import Router
from app.models.pop import Pop
from app.models.party import Party, PartyStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tariff import Tariff, TariffType


class SubscriptionWebHelpers:
    """Shared helpers for subscription web UI queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_router_options(self) -> list[dict[str, str]]:
        routers = (
            self.db.query(Router)
            .filter(Router.is_active == True)
            .order_by(Router.title)
            .all()
        )
        return [{"value": str(r.id), "label": f"{r.title} ({r.ip})"} for r in routers]

    def get_pop_options(self) -> list[dict[str, str]]:
        pops = (
            self.db.query(Pop)
            .filter(Pop.is_active == True)
            .order_by(Pop.name)
            .all()
        )
        return [{"value": str(p.id), "label": p.name} for p in pops]

    def get_tariff_options(self, tariff_type: Optional[str] = None) -> list[dict[str, Any]]:
        query = self.db.query(Tariff).filter(Tariff.enabled == True)
        if tariff_type:
            query = query.filter(Tariff.tariff_type == TariffType(tariff_type))
        tariffs = query.order_by(Tariff.title).all()
        return [
            {
                "value": str(t.id),
                "label": f"{t.title} - {t.price:,.0f} {t.currency}",
                "price": float(t.price),
                "download_speed": t.download_speed,
                "upload_speed": t.upload_speed,
            }
            for t in tariffs
        ]

    def get_party_options(self, search: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
        query = self.db.query(Party).filter(Party.status == PartyStatus.ACTIVE)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Party.name.ilike(search_term),
                    Party.primary_email.ilike(search_term),
                    Party.primary_phone.ilike(search_term),
                )
            )
        parties = query.order_by(Party.name).limit(limit).all()
        return [
            {
                "value": str(p.id),
                "label": p.name or p.primary_email or f"Party {p.id}",
                "email": p.primary_email,
                "phone": p.primary_phone,
                "type": p.type,
            }
            for p in parties
        ]

    def compute_subscription_stats(self) -> dict[str, Any]:
        active = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
            or 0
        )
        suspended = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.SUSPENDED)
            .scalar()
            or 0
        )
        pending = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.PENDING)
            .scalar()
            or 0
        )
        cancelled = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.status == SubscriptionStatus.CANCELLED)
            .scalar()
            or 0
        )
        total = active + suspended + pending + cancelled

        mrr_monthly = (
            self.db.query(func.sum(Subscription.price))
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "monthly",
            )
            .scalar()
            or Decimal("0")
        )
        mrr_quarterly = (
            self.db.query(func.sum(Subscription.price / 3))
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "quarterly",
            )
            .scalar()
            or Decimal("0")
        )
        mrr_yearly = (
            self.db.query(func.sum(Subscription.price / 12))
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "yearly",
            )
            .scalar()
            or Decimal("0")
        )
        total_mrr = float(mrr_monthly) + float(mrr_quarterly) + float(mrr_yearly)

        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.created_at >= start_of_month)
            .scalar()
            or 0
        )
        failed_provisioning = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.provisioning_error.isnot(None))
            .scalar()
            or 0
        )

        return {
            "active": active,
            "suspended": suspended,
            "pending": pending,
            "cancelled": cancelled,
            "total": total,
            "mrr": total_mrr,
            "new_this_month": new_this_month,
            "failed_provisioning": failed_provisioning,
        }
