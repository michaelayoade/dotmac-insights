"""Usage service - business logic for bandwidth/traffic usage tracking.

This service handles:
- Usage data retrieval and aggregation
- Data cap monitoring
- Usage statistics and reporting
- Billing-cycle usage calculations
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.customer_usage import CustomerUsage
from app.models.subscription import Subscription
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams

from .subscription_types import (
    UsageFilters,
    UsageRecord,
    UsageSummary,
    DataCapStatus,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["UsageService"]


class UsageService:
    """Service for usage/bandwidth tracking and reporting."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Usage Records
    # -------------------------------------------------------------------------

    def list_usage(
        self,
        filters: Optional[UsageFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[CustomerUsage]:
        """List usage records with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing usage records and total count.
        """
        query = self.db.query(CustomerUsage)

        if filters:
            if filters.subscription_id:
                query = query.filter(
                    CustomerUsage.subscription_id == filters.subscription_id
                )

            if filters.party_id:
                # Join through subscription to filter by party
                query = query.join(
                    Subscription, CustomerUsage.subscription_id == Subscription.id
                ).filter(Subscription.party_id == filters.party_id)

            if filters.date_from:
                query = query.filter(CustomerUsage.usage_date >= filters.date_from)

            if filters.date_to:
                query = query.filter(CustomerUsage.usage_date <= filters.date_to)

        query = query.order_by(CustomerUsage.usage_date.desc())
        return paginate(query, pagination)

    def get_usage_record(self, usage_id: int) -> Optional[CustomerUsage]:
        """Get a single usage record by ID."""
        return self.db.query(CustomerUsage).filter(CustomerUsage.id == usage_id).first()

    def get_subscription_usage(
        self,
        subscription_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[CustomerUsage]:
        """Get usage records for a subscription within date range.

        Args:
            subscription_id: The subscription ID.
            date_from: Start date (defaults to 30 days ago).
            date_to: End date (defaults to today).

        Returns:
            List of usage records.
        """
        if date_from is None:
            date_from = date.today() - timedelta(days=30)
        if date_to is None:
            date_to = date.today()

        return (
            self.db.query(CustomerUsage)
            .filter(
                CustomerUsage.subscription_id == subscription_id,
                CustomerUsage.usage_date >= date_from,
                CustomerUsage.usage_date <= date_to,
            )
            .order_by(CustomerUsage.usage_date.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Usage Summaries
    # -------------------------------------------------------------------------

    def get_usage_summary(
        self,
        subscription_id: int,
        period_start: date,
        period_end: date,
    ) -> UsageSummary:
        """Get aggregated usage summary for a subscription period.

        Args:
            subscription_id: The subscription ID.
            period_start: Start date of period.
            period_end: End date of period.

        Returns:
            UsageSummary with aggregated data.
        """
        # Get aggregates
        result = (
            self.db.query(
                func.sum(CustomerUsage.upload_bytes).label("total_upload"),
                func.sum(CustomerUsage.download_bytes).label("total_download"),
                func.count(CustomerUsage.id).label("day_count"),
            )
            .filter(
                CustomerUsage.subscription_id == subscription_id,
                CustomerUsage.usage_date >= period_start,
                CustomerUsage.usage_date <= period_end,
            )
            .first()
        )

        total_upload = result.total_upload or 0
        total_download = result.total_download or 0
        day_count = result.day_count or 1

        total_upload_gb = total_upload / (1024**3)
        total_download_gb = total_download / (1024**3)
        total_gb = (total_upload + total_download) / (1024**3)

        # Get peak day
        peak = (
            self.db.query(
                CustomerUsage.usage_date,
                (CustomerUsage.upload_bytes + CustomerUsage.download_bytes).label(
                    "total"
                ),
            )
            .filter(
                CustomerUsage.subscription_id == subscription_id,
                CustomerUsage.usage_date >= period_start,
                CustomerUsage.usage_date <= period_end,
            )
            .order_by(
                (CustomerUsage.upload_bytes + CustomerUsage.download_bytes).desc()
            )
            .first()
        )

        peak_day = peak.usage_date if peak else None
        peak_day_gb = peak.total / (1024**3) if peak else 0.0

        return UsageSummary(
            subscription_id=subscription_id,
            period_start=period_start,
            period_end=period_end,
            total_upload_gb=round(total_upload_gb, 2),
            total_download_gb=round(total_download_gb, 2),
            total_gb=round(total_gb, 2),
            daily_average_gb=round(total_gb / day_count, 2) if day_count > 0 else 0.0,
            peak_day=peak_day,
            peak_day_gb=round(peak_day_gb, 2),
        )

    def get_daily_summary(
        self,
        subscription_id: int,
        target_date: date,
    ) -> UsageRecord:
        """Get usage summary for a specific day.

        Args:
            subscription_id: The subscription ID.
            target_date: The date to get usage for.

        Returns:
            UsageRecord for the day (zeros if no data).
        """
        record = (
            self.db.query(CustomerUsage)
            .filter(
                CustomerUsage.subscription_id == subscription_id,
                CustomerUsage.usage_date == target_date,
            )
            .first()
        )

        if record:
            return UsageRecord(
                id=record.id,
                subscription_id=subscription_id,
                usage_date=target_date,
                upload_bytes=record.upload_bytes,
                download_bytes=record.download_bytes,
                total_bytes=record.total_bytes,
                upload_gb=record.upload_gb,
                download_gb=record.download_gb,
                total_gb=record.total_gb,
            )

        # Return empty record for no data
        return UsageRecord(
            id=0,
            subscription_id=subscription_id,
            usage_date=target_date,
            upload_bytes=0,
            download_bytes=0,
            total_bytes=0,
            upload_gb=0.0,
            download_gb=0.0,
            total_gb=0.0,
        )

    # -------------------------------------------------------------------------
    # Data Cap Monitoring
    # -------------------------------------------------------------------------

    def get_data_cap_status(self, subscription_id: int) -> DataCapStatus:
        """Get data cap status for a subscription.

        Calculates usage against data cap for current billing cycle.

        Args:
            subscription_id: The subscription ID.

        Returns:
            DataCapStatus with cap and usage information.
        """
        from app.models.subscription import Subscription

        sub = (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )

        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found")

        # Calculate billing cycle dates
        cycle_start, cycle_end = self._get_billing_cycle_dates(sub)

        # Get usage for current cycle
        summary = self.get_usage_summary(subscription_id, cycle_start, cycle_end)

        # Calculate cap status
        data_cap_gb = sub.data_cap / (1024**3) if sub.data_cap else None
        used_gb = summary.total_gb

        if data_cap_gb:
            remaining_gb = max(0, data_cap_gb - used_gb)
            usage_percent = min(100, (used_gb / data_cap_gb) * 100)
            is_exceeded = used_gb >= data_cap_gb
        else:
            remaining_gb = None
            usage_percent = None
            is_exceeded = False

        return DataCapStatus(
            subscription_id=subscription_id,
            data_cap_gb=data_cap_gb,
            used_gb=round(used_gb, 2),
            remaining_gb=round(remaining_gb, 2) if remaining_gb is not None else None,
            usage_percent=round(usage_percent, 1) if usage_percent is not None else None,
            is_exceeded=is_exceeded,
            billing_cycle_start=cycle_start,
            billing_cycle_end=cycle_end,
        )

    def get_subscriptions_near_cap(
        self, threshold_percent: float = 80.0
    ) -> List[DataCapStatus]:
        """Get subscriptions approaching or exceeding data cap.

        Args:
            threshold_percent: Alert threshold (default 80%).

        Returns:
            List of DataCapStatus for subscriptions at/above threshold.
        """
        from app.models.subscription import Subscription, SubscriptionStatus

        # Get active subscriptions with data caps
        subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.data_cap.isnot(None),
                Subscription.data_cap > 0,
            )
            .all()
        )

        results = []
        for sub in subs:
            status = self.get_data_cap_status(sub.id)
            if status.usage_percent and status.usage_percent >= threshold_percent:
                results.append(status)

        # Sort by usage percent descending
        results.sort(key=lambda x: x.usage_percent or 0, reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Usage Statistics
    # -------------------------------------------------------------------------

    def get_usage_stats(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict:
        """Get aggregate usage statistics.

        Args:
            date_from: Start date (defaults to 30 days ago).
            date_to: End date (defaults to today).

        Returns:
            Dictionary with usage statistics.
        """
        if date_from is None:
            date_from = date.today() - timedelta(days=30)
        if date_to is None:
            date_to = date.today()

        # Total usage
        totals = (
            self.db.query(
                func.sum(CustomerUsage.upload_bytes).label("total_upload"),
                func.sum(CustomerUsage.download_bytes).label("total_download"),
                func.count(func.distinct(CustomerUsage.subscription_id)).label(
                    "active_subscriptions"
                ),
            )
            .filter(
                CustomerUsage.usage_date >= date_from,
                CustomerUsage.usage_date <= date_to,
            )
            .first()
        )

        total_upload = totals.total_upload or 0
        total_download = totals.total_download or 0

        # Daily averages
        days = (date_to - date_from).days + 1

        # Top consumers
        top_users = (
            self.db.query(
                CustomerUsage.subscription_id,
                func.sum(CustomerUsage.upload_bytes + CustomerUsage.download_bytes).label(
                    "total"
                ),
            )
            .filter(
                CustomerUsage.usage_date >= date_from,
                CustomerUsage.usage_date <= date_to,
            )
            .group_by(CustomerUsage.subscription_id)
            .order_by(
                func.sum(CustomerUsage.upload_bytes + CustomerUsage.download_bytes).desc()
            )
            .limit(10)
            .all()
        )

        return {
            "period_start": date_from.isoformat(),
            "period_end": date_to.isoformat(),
            "total_upload_tb": round(total_upload / (1024**4), 2),
            "total_download_tb": round(total_download / (1024**4), 2),
            "total_traffic_tb": round((total_upload + total_download) / (1024**4), 2),
            "daily_avg_gb": round(
                (total_upload + total_download) / (1024**3) / days, 2
            )
            if days > 0
            else 0,
            "active_subscriptions": totals.active_subscriptions or 0,
            "top_consumers": [
                {
                    "subscription_id": row.subscription_id,
                    "total_gb": round(row.total / (1024**3), 2),
                }
                for row in top_users
            ],
        }

    # -------------------------------------------------------------------------
    # Daily Usage Billing Support
    # -------------------------------------------------------------------------

    def get_billable_usage(
        self,
        subscription_id: int,
        billing_date: date,
    ) -> dict:
        """Get usage data for daily billing calculation.

        For subscriptions with usage-based billing, this returns the
        usage metrics needed to calculate daily charges.

        Args:
            subscription_id: The subscription ID.
            billing_date: The date to bill for.

        Returns:
            Dictionary with billable usage metrics.
        """
        record = self.get_daily_summary(subscription_id, billing_date)

        return {
            "subscription_id": subscription_id,
            "billing_date": billing_date.isoformat(),
            "upload_gb": record.upload_gb,
            "download_gb": record.download_gb,
            "total_gb": record.total_gb,
            "total_bytes": record.total_bytes,
        }

    def calculate_usage_charge(
        self,
        subscription_id: int,
        billing_date: date,
        rate_per_gb: Decimal,
        included_gb: Decimal = Decimal("0"),
    ) -> dict:
        """Calculate usage-based charge for a day.

        For metered/usage-based billing models.

        Args:
            subscription_id: The subscription ID.
            billing_date: The date to calculate for.
            rate_per_gb: Price per GB of usage.
            included_gb: Free tier GB included in plan.

        Returns:
            Dictionary with charge calculation details.
        """
        usage = self.get_billable_usage(subscription_id, billing_date)
        total_gb = Decimal(str(usage["total_gb"]))

        # Calculate billable GB (after free tier)
        billable_gb = max(Decimal("0"), total_gb - included_gb)

        # Calculate charge
        charge = billable_gb * rate_per_gb

        return {
            "subscription_id": subscription_id,
            "billing_date": billing_date.isoformat(),
            "total_usage_gb": float(total_gb),
            "included_gb": float(included_gb),
            "billable_gb": float(billable_gb),
            "rate_per_gb": float(rate_per_gb),
            "charge_amount": float(charge),
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_billing_cycle_dates(self, subscription) -> tuple[date, date]:
        """Calculate current billing cycle dates for a subscription.

        Args:
            subscription: The Subscription model instance.

        Returns:
            Tuple of (cycle_start, cycle_end) dates.
        """
        today = date.today()

        # Use start_date or created_at as billing anchor
        if subscription.start_date:
            anchor = subscription.start_date.date() if isinstance(
                subscription.start_date, datetime
            ) else subscription.start_date
        else:
            anchor = subscription.created_at.date() if isinstance(
                subscription.created_at, datetime
            ) else subscription.created_at

        billing_cycle = subscription.billing_cycle or "monthly"

        if billing_cycle == "daily":
            # Daily billing - cycle is just today
            return today, today

        elif billing_cycle == "weekly":
            # Weekly billing - 7 day cycle
            days_since_anchor = (today - anchor).days
            cycle_day = days_since_anchor % 7
            cycle_start = today - timedelta(days=cycle_day)
            cycle_end = cycle_start + timedelta(days=6)

        elif billing_cycle == "monthly":
            # Monthly billing - use anchor day of month
            anchor_day = min(anchor.day, 28)  # Handle Feb edge case

            if today.day >= anchor_day:
                # Current cycle started this month
                cycle_start = today.replace(day=anchor_day)
                # Calculate next month
                if today.month == 12:
                    next_month = today.replace(year=today.year + 1, month=1, day=anchor_day)
                else:
                    next_month = today.replace(month=today.month + 1, day=anchor_day)
                cycle_end = next_month - timedelta(days=1)
            else:
                # Current cycle started last month
                if today.month == 1:
                    last_month = today.replace(year=today.year - 1, month=12, day=anchor_day)
                else:
                    last_month = today.replace(month=today.month - 1, day=anchor_day)
                cycle_start = last_month
                cycle_end = today.replace(day=anchor_day) - timedelta(days=1)

        elif billing_cycle == "quarterly":
            # Quarterly billing - 3 month cycle
            months_since_anchor = (
                (today.year - anchor.year) * 12 + (today.month - anchor.month)
            )
            cycle_month = months_since_anchor % 3
            cycle_start_month = today.month - cycle_month

            if cycle_start_month < 1:
                cycle_start = today.replace(
                    year=today.year - 1,
                    month=12 + cycle_start_month,
                    day=min(anchor.day, 28),
                )
            else:
                cycle_start = today.replace(
                    month=cycle_start_month, day=min(anchor.day, 28)
                )

            # End is 3 months after start
            end_month = cycle_start.month + 3
            if end_month > 12:
                cycle_end = cycle_start.replace(
                    year=cycle_start.year + 1,
                    month=end_month - 12,
                    day=min(anchor.day, 28),
                ) - timedelta(days=1)
            else:
                cycle_end = cycle_start.replace(
                    month=end_month, day=min(anchor.day, 28)
                ) - timedelta(days=1)

        elif billing_cycle == "yearly":
            # Yearly billing
            if today >= anchor.replace(year=today.year):
                cycle_start = anchor.replace(year=today.year)
                cycle_end = anchor.replace(year=today.year + 1) - timedelta(days=1)
            else:
                cycle_start = anchor.replace(year=today.year - 1)
                cycle_end = anchor.replace(year=today.year) - timedelta(days=1)

        else:
            # Default to monthly
            cycle_start = today.replace(day=1)
            if today.month == 12:
                cycle_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(
                    days=1
                )
            else:
                cycle_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        return cycle_start, cycle_end
