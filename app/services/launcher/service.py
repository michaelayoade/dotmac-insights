"""Launcher service for managing favorites and aggregating module badges.

This service handles:
- User favorite modules (CRUD operations)
- Module badge/stats aggregation from various dashboard services
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.user_preference import UserPreference

if TYPE_CHECKING:
    from app.auth import Principal

logger = structlog.get_logger()


@dataclass
class ModuleBadge:
    """Badge data for a module card on the launcher."""

    count: int
    label: str
    color: str  # "amber", "red", "blue", "green"
    href: Optional[str] = None


class LauncherService:
    """Service for launcher page data and favorites management."""

    def __init__(self, db: Session, user: "Principal") -> None:
        self.db = db
        self.user = user

    # =========================================================================
    # FAVORITES MANAGEMENT
    # =========================================================================

    def get_user_favorites(self) -> List[str]:
        """Get list of favorite module IDs for current user."""
        pref = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == self.user.id)
            .first()
        )

        if pref and pref.favorite_modules:
            return list(pref.favorite_modules)
        return []

    def _get_or_create_preference(self) -> UserPreference:
        """Get or create user preference record."""
        pref = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == self.user.id)
            .first()
        )

        if not pref:
            pref = UserPreference(user_id=self.user.id)
            self.db.add(pref)
            self.db.flush()

        return pref

    def set_favorites(self, module_ids: List[str]) -> None:
        """Set the user's favorite modules."""
        pref = self._get_or_create_preference()
        pref.favorite_modules = module_ids
        self.db.commit()

    def add_favorite(self, module_id: str) -> List[str]:
        """Add a module to favorites. Returns updated list."""
        pref = self._get_or_create_preference()

        favorites = list(pref.favorite_modules or [])
        if module_id not in favorites:
            favorites.append(module_id)
            pref.favorite_modules = favorites
            self.db.commit()

        return favorites

    def remove_favorite(self, module_id: str) -> List[str]:
        """Remove a module from favorites. Returns updated list."""
        pref = self._get_or_create_preference()

        favorites = list(pref.favorite_modules or [])
        if module_id in favorites:
            favorites.remove(module_id)
            pref.favorite_modules = favorites
            self.db.commit()

        return favorites

    # =========================================================================
    # MODULE BADGES
    # =========================================================================

    def get_module_badge(self, module_id: str) -> Optional[ModuleBadge]:
        """Get quick stats badge for a module.

        Aggregates from module-specific dashboard services.
        Returns None if no actionable badge data.
        """
        badge_fetchers = {
            "customer": self._get_customer_badge,
            "finance": self._get_finance_badge,
            "operations": self._get_operations_badge,
            "isp": self._get_isp_badge,
            "hr": self._get_hr_badge,
            "support": self._get_support_badge,
            "sales": self._get_sales_badge,
        }

        fetcher = badge_fetchers.get(module_id)
        if fetcher:
            try:
                return fetcher()
            except Exception as e:
                logger.warning(
                    "badge_fetch_failed",
                    module_id=module_id,
                    error=str(e),
                )
                return None
        return None

    def _get_customer_badge(self) -> Optional[ModuleBadge]:
        """Get CRM badge - active leads count."""
        try:
            from sqlalchemy import func
            from app.models.lead import Lead

            count = (
                self.db.query(func.count(Lead.id))
                .filter(Lead.status.in_(["new", "contacted", "qualified"]))
                .scalar()
                or 0
            )

            if count > 0:
                return ModuleBadge(
                    count=count,
                    label="leads",
                    color="blue",
                    href="/crm/leads",
                )
        except Exception:
            pass
        return None

    def _get_finance_badge(self) -> Optional[ModuleBadge]:
        """Get Finance badge - pending approvals."""
        try:
            from app.services.accounting.approvals import ApprovalsService

            service = ApprovalsService(self.db, self.user)
            stats = service.get_stats()
            pending = stats.get("pending", 0)

            if pending > 0:
                return ModuleBadge(
                    count=pending,
                    label="pending",
                    color="amber",
                    href="/accounting/approvals",
                )
        except Exception:
            pass
        return None

    def _get_operations_badge(self) -> Optional[ModuleBadge]:
        """Get Operations badge - open service orders."""
        try:
            from app.services.operations.dashboard import OperationsDashboardService

            service = OperationsDashboardService(self.db, self.user)
            counts = service.get_dashboard_counts()
            open_orders = counts.get("open_orders", 0)

            if open_orders > 0:
                return ModuleBadge(
                    count=open_orders,
                    label="orders",
                    color="amber",
                    href="/field-service",
                )
        except Exception:
            pass
        return None

    def _get_isp_badge(self) -> Optional[ModuleBadge]:
        """Get ISP badge - expiring subscriptions (next 7 days)."""
        try:
            from sqlalchemy import func
            from datetime import date, timedelta
            from app.models.subscription import Subscription, SubscriptionStatus

            next_week = date.today() + timedelta(days=7)
            expiring = (
                self.db.query(func.count(Subscription.id))
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.end_date <= next_week,
                    Subscription.end_date >= date.today(),
                )
                .scalar()
                or 0
            )

            if expiring > 0:
                return ModuleBadge(
                    count=expiring,
                    label="expiring",
                    color="red",
                    href="/subscriptions?filter=expiring",
                )
        except Exception:
            pass
        return None

    def _get_hr_badge(self) -> Optional[ModuleBadge]:
        """Get HR badge - pending leave requests."""
        try:
            from sqlalchemy import func
            from app.models.hr import LeaveRequest, LeaveStatus

            pending = (
                self.db.query(func.count(LeaveRequest.id))
                .filter(LeaveRequest.status == LeaveStatus.PENDING)
                .scalar()
                or 0
            )

            if pending > 0:
                return ModuleBadge(
                    count=pending,
                    label="pending",
                    color="amber",
                    href="/hr/leave?status=pending",
                )
        except Exception:
            pass
        return None

    def _get_support_badge(self) -> Optional[ModuleBadge]:
        """Get Support badge - open tickets."""
        try:
            from sqlalchemy import func
            from app.models.unified_ticket import UnifiedTicket, TicketStatus

            open_count = (
                self.db.query(func.count(UnifiedTicket.id))
                .filter(
                    UnifiedTicket.status.in_([
                        TicketStatus.NEW,
                        TicketStatus.OPEN,
                        TicketStatus.PENDING,
                    ])
                )
                .scalar()
                or 0
            )

            if open_count > 0:
                return ModuleBadge(
                    count=open_count,
                    label="open",
                    color="amber",
                    href="/support/tickets?status=open",
                )
        except Exception:
            pass
        return None

    def _get_sales_badge(self) -> Optional[ModuleBadge]:
        """Get Sales badge - open quotations."""
        try:
            from sqlalchemy import func
            from app.models.sales import Quotation, QuotationStatus

            open_quotes = (
                self.db.query(func.count(Quotation.id))
                .filter(
                    Quotation.status.in_([
                        QuotationStatus.DRAFT,
                        QuotationStatus.OPEN,
                    ])
                )
                .scalar()
                or 0
            )

            if open_quotes > 0:
                return ModuleBadge(
                    count=open_quotes,
                    label="quotes",
                    color="blue",
                    href="/sales/quotations?status=open",
                )
        except Exception:
            pass
        return None
