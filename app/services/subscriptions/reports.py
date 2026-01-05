"""Subscription Reports and Dashboard Analytics.

Comprehensive reporting service for subscription metrics:
- Dashboard summaries and KPIs
- MRR analytics (growth, breakdown, trends)
- Churn analysis and retention
- Revenue reports
- Usage analytics
- Provisioning success rates
- Customer lifetime value
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_, case, extract, distinct
from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.tariff import Tariff

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    # Enums
    "ReportPeriod",
    "ReportGroupBy",
    # Dashboard DTOs
    "DashboardSummary",
    "DashboardKPIs",
    "DashboardCharts",
    # MRR DTOs
    "MRRSummary",
    "MRRBreakdown",
    "MRRTrend",
    "MRRMovement",
    # Churn DTOs
    "ChurnSummary",
    "ChurnByReason",
    "RetentionCohort",
    # Revenue DTOs
    "RevenueSummary",
    "RevenueByType",
    "RevenueByPlan",
    "ARAgingSummary",
    # Usage DTOs
    "UsageReport",
    "TopUsersReport",
    "UsageTrend",
    # Provisioning DTOs
    "ProvisioningReport",
    "ProvisioningSuccessRate",
    # Customer DTOs
    "CustomerLTVReport",
    "CustomerSegment",
    # Service
    "SubscriptionReportsService",
]


# =============================================================================
# ENUMS
# =============================================================================

class ReportPeriod(str, Enum):
    """Report time periods."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    LAST_QUARTER = "last_quarter"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    LAST_365_DAYS = "last_365_days"
    CUSTOM = "custom"


class ReportGroupBy(str, Enum):
    """Grouping options for reports."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    SERVICE_TYPE = "service_type"
    PLAN = "plan"
    TARIFF = "tariff"
    STATUS = "status"
    ROUTER = "router"
    ZONE = "zone"


# =============================================================================
# DASHBOARD DTOs
# =============================================================================

@dataclass
class DashboardKPIs:
    """Key performance indicators for dashboard."""

    # Subscription counts
    total_subscriptions: int = 0
    active_subscriptions: int = 0
    suspended_subscriptions: int = 0
    pending_subscriptions: int = 0
    cancelled_subscriptions: int = 0

    # Growth
    new_this_month: int = 0
    new_last_month: int = 0
    growth_rate: Decimal = Decimal("0")  # % change

    # Churn
    churned_this_month: int = 0
    churn_rate: Decimal = Decimal("0")  # %

    # Financial
    mrr: Decimal = Decimal("0")
    mrr_growth: Decimal = Decimal("0")  # % change from last month
    arr: Decimal = Decimal("0")
    average_revenue_per_user: Decimal = Decimal("0")

    # Provisioning
    provisioned_count: int = 0
    pending_provisioning: int = 0
    failed_provisioning: int = 0
    provisioning_success_rate: Decimal = Decimal("0")  # %

    # Usage
    total_active_sessions: int = 0
    total_bandwidth_gb: Decimal = Decimal("0")


@dataclass
class DashboardCharts:
    """Chart data for dashboard."""

    # MRR trend (last 12 months)
    mrr_trend: List[Dict[str, Any]] = field(default_factory=list)
    # Format: [{"month": "2024-01", "mrr": 1000000, "count": 150}, ...]

    # Subscriptions by status (pie chart)
    by_status: Dict[str, int] = field(default_factory=dict)

    # Subscriptions by service type (pie chart)
    by_service_type: Dict[str, int] = field(default_factory=dict)

    # New vs churned (bar chart, last 6 months)
    growth_vs_churn: List[Dict[str, Any]] = field(default_factory=list)
    # Format: [{"month": "2024-01", "new": 20, "churned": 5}, ...]

    # Top plans by subscriber count
    top_plans: List[Dict[str, Any]] = field(default_factory=list)

    # Revenue by service type
    revenue_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class DashboardSummary:
    """Complete dashboard summary."""

    kpis: DashboardKPIs = field(default_factory=DashboardKPIs)
    charts: DashboardCharts = field(default_factory=DashboardCharts)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str = "NGN"


# =============================================================================
# MRR DTOs
# =============================================================================

@dataclass
class MRRBreakdown:
    """MRR breakdown by category."""

    category: str  # service_type, plan, tariff, etc.
    value: str
    mrr: Decimal = Decimal("0")
    count: int = 0
    percentage: Decimal = Decimal("0")


@dataclass
class MRRMovement:
    """MRR movement analysis."""

    period_start: date
    period_end: date

    # Opening and closing
    opening_mrr: Decimal = Decimal("0")
    closing_mrr: Decimal = Decimal("0")
    net_change: Decimal = Decimal("0")
    net_change_percent: Decimal = Decimal("0")

    # Components
    new_mrr: Decimal = Decimal("0")  # From new subscriptions
    expansion_mrr: Decimal = Decimal("0")  # From upgrades
    contraction_mrr: Decimal = Decimal("0")  # From downgrades
    churned_mrr: Decimal = Decimal("0")  # From cancellations
    reactivation_mrr: Decimal = Decimal("0")  # From reactivations

    # Counts
    new_count: int = 0
    upgraded_count: int = 0
    downgraded_count: int = 0
    churned_count: int = 0
    reactivated_count: int = 0


@dataclass
class MRRTrend:
    """MRR trend over time."""

    period: str  # "2024-01", "2024-Q1", etc.
    mrr: Decimal = Decimal("0")
    subscription_count: int = 0
    arpu: Decimal = Decimal("0")
    growth_rate: Decimal = Decimal("0")  # % change from previous period


@dataclass
class MRRSummary:
    """Complete MRR analytics."""

    current_mrr: Decimal = Decimal("0")
    previous_mrr: Decimal = Decimal("0")
    mrr_growth: Decimal = Decimal("0")
    arr: Decimal = Decimal("0")

    # Breakdown
    by_service_type: List[MRRBreakdown] = field(default_factory=list)
    by_plan: List[MRRBreakdown] = field(default_factory=list)
    by_billing_cycle: List[MRRBreakdown] = field(default_factory=list)

    # Trends
    trends: List[MRRTrend] = field(default_factory=list)

    # Movement
    movement: Optional[MRRMovement] = None


# =============================================================================
# CHURN DTOs
# =============================================================================

@dataclass
class ChurnByReason:
    """Churn breakdown by reason."""

    reason: str
    count: int = 0
    mrr_lost: Decimal = Decimal("0")
    percentage: Decimal = Decimal("0")


@dataclass
class RetentionCohort:
    """Cohort retention data."""

    cohort_month: str  # "2024-01"
    cohort_size: int = 0

    # Retention by month (month 0 = 100%)
    retention: List[Decimal] = field(default_factory=list)
    # [100, 95, 90, 88, ...] percentages


@dataclass
class ChurnSummary:
    """Churn analysis summary."""

    period_start: date
    period_end: date

    # Current period
    churned_count: int = 0
    churn_rate: Decimal = Decimal("0")  # %
    mrr_lost: Decimal = Decimal("0")

    # Comparison
    previous_churned_count: int = 0
    previous_churn_rate: Decimal = Decimal("0")
    churn_rate_change: Decimal = Decimal("0")

    # By reason
    by_reason: List[ChurnByReason] = field(default_factory=list)

    # Retention cohorts
    cohorts: List[RetentionCohort] = field(default_factory=list)

    # At-risk (suspended, payment failed)
    at_risk_count: int = 0
    at_risk_mrr: Decimal = Decimal("0")


# =============================================================================
# REVENUE DTOs
# =============================================================================

@dataclass
class RevenueByType:
    """Revenue breakdown by category."""

    category: str
    value: str
    revenue: Decimal = Decimal("0")
    count: int = 0
    percentage: Decimal = Decimal("0")


@dataclass
class RevenueByPlan:
    """Revenue by plan/tariff."""

    plan_id: int
    plan_name: str
    subscriber_count: int = 0
    monthly_revenue: Decimal = Decimal("0")
    total_revenue: Decimal = Decimal("0")
    arpu: Decimal = Decimal("0")
    percentage: Decimal = Decimal("0")


@dataclass
class ARAgingSummary:
    """Accounts receivable aging."""

    currency: str = "NGN"
    total_outstanding: Decimal = Decimal("0")

    current: Decimal = Decimal("0")  # 0-30 days
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_91_plus: Decimal = Decimal("0")

    # By service type
    by_service_type: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class RevenueSummary:
    """Revenue summary report."""

    period_start: date
    period_end: date
    currency: str = "NGN"

    # Totals
    total_revenue: Decimal = Decimal("0")
    subscription_revenue: Decimal = Decimal("0")
    usage_revenue: Decimal = Decimal("0")
    fee_revenue: Decimal = Decimal("0")  # installation, reconnection, etc.

    # Comparison
    previous_total: Decimal = Decimal("0")
    revenue_growth: Decimal = Decimal("0")

    # Breakdown
    by_service_type: List[RevenueByType] = field(default_factory=list)
    by_plan: List[RevenueByPlan] = field(default_factory=list)

    # AR aging
    ar_aging: Optional[ARAgingSummary] = None


# =============================================================================
# USAGE DTOs
# =============================================================================

@dataclass
class UsageTrend:
    """Usage trend data point."""

    period: str  # "2024-01-15", "2024-01", etc.
    upload_gb: Decimal = Decimal("0")
    download_gb: Decimal = Decimal("0")
    total_gb: Decimal = Decimal("0")
    active_users: int = 0


@dataclass
class TopUsersReport:
    """Top users by usage."""

    subscription_id: int
    party_id: int
    party_name: str
    plan_name: str
    upload_gb: Decimal = Decimal("0")
    download_gb: Decimal = Decimal("0")
    total_gb: Decimal = Decimal("0")
    data_cap_gb: Optional[Decimal] = None
    usage_percent: Optional[Decimal] = None


@dataclass
class UsageReport:
    """Usage analytics report."""

    period_start: date
    period_end: date

    # Totals
    total_upload_gb: Decimal = Decimal("0")
    total_download_gb: Decimal = Decimal("0")
    total_gb: Decimal = Decimal("0")

    # Averages
    avg_per_user_gb: Decimal = Decimal("0")
    peak_day: Optional[date] = None
    peak_day_gb: Decimal = Decimal("0")

    # Active users
    active_users: int = 0
    users_over_cap: int = 0

    # Trends
    trends: List[UsageTrend] = field(default_factory=list)

    # Top users
    top_users: List[TopUsersReport] = field(default_factory=list)


# =============================================================================
# PROVISIONING DTOs
# =============================================================================

@dataclass
class ProvisioningSuccessRate:
    """Provisioning success rate by category."""

    category: str  # router, access_method, etc.
    value: str
    total: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: Decimal = Decimal("0")


@dataclass
class ProvisioningReport:
    """Provisioning analytics report."""

    period_start: date
    period_end: date

    # Totals
    total_operations: int = 0
    successful: int = 0
    failed: int = 0
    pending: int = 0
    overall_success_rate: Decimal = Decimal("0")

    # By action type
    by_action: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # {"CREATE": {"total": 100, "success": 95, "failed": 5}, ...}

    # By router
    by_router: List[ProvisioningSuccessRate] = field(default_factory=list)

    # By access method
    by_access_method: List[ProvisioningSuccessRate] = field(default_factory=list)

    # Average duration
    avg_duration_ms: int = 0

    # Recent failures
    recent_failures: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# CUSTOMER DTOs
# =============================================================================

@dataclass
class CustomerSegment:
    """Customer segment data."""

    segment: str  # "high_value", "at_risk", "new", etc.
    count: int = 0
    mrr: Decimal = Decimal("0")
    avg_tenure_months: Decimal = Decimal("0")
    avg_ltv: Decimal = Decimal("0")


@dataclass
class CustomerLTVReport:
    """Customer lifetime value report."""

    # Overall metrics
    avg_ltv: Decimal = Decimal("0")
    avg_tenure_months: Decimal = Decimal("0")
    avg_monthly_revenue: Decimal = Decimal("0")

    # Distribution
    ltv_distribution: Dict[str, int] = field(default_factory=dict)
    # {"0-10000": 50, "10000-50000": 100, "50000+": 25}

    # By service type
    by_service_type: Dict[str, Decimal] = field(default_factory=dict)

    # Segments
    segments: List[CustomerSegment] = field(default_factory=list)

    # Top customers by LTV
    top_customers: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# REPORTS SERVICE
# =============================================================================

class SubscriptionReportsService:
    """Service for generating subscription reports and analytics."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Period Helpers
    # -------------------------------------------------------------------------

    def _get_period_dates(
        self,
        period: ReportPeriod,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None,
    ) -> Tuple[date, date]:
        """Get start and end dates for a report period."""
        today = date.today()

        if period == ReportPeriod.TODAY:
            return today, today
        elif period == ReportPeriod.YESTERDAY:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif period == ReportPeriod.THIS_WEEK:
            start = today - timedelta(days=today.weekday())
            return start, today
        elif period == ReportPeriod.LAST_WEEK:
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end
        elif period == ReportPeriod.THIS_MONTH:
            start = today.replace(day=1)
            return start, today
        elif period == ReportPeriod.LAST_MONTH:
            first_of_month = today.replace(day=1)
            end = first_of_month - timedelta(days=1)
            start = end.replace(day=1)
            return start, end
        elif period == ReportPeriod.THIS_QUARTER:
            quarter = (today.month - 1) // 3
            start = date(today.year, quarter * 3 + 1, 1)
            return start, today
        elif period == ReportPeriod.LAST_QUARTER:
            quarter = (today.month - 1) // 3
            if quarter == 0:
                start = date(today.year - 1, 10, 1)
                end = date(today.year - 1, 12, 31)
            else:
                start = date(today.year, (quarter - 1) * 3 + 1, 1)
                end_month = quarter * 3
                if end_month == 3:
                    end = date(today.year, 3, 31)
                elif end_month == 6:
                    end = date(today.year, 6, 30)
                else:
                    end = date(today.year, 9, 30)
            return start, end
        elif period == ReportPeriod.THIS_YEAR:
            start = date(today.year, 1, 1)
            return start, today
        elif period == ReportPeriod.LAST_YEAR:
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return start, end
        elif period == ReportPeriod.LAST_7_DAYS:
            return today - timedelta(days=7), today
        elif period == ReportPeriod.LAST_30_DAYS:
            return today - timedelta(days=30), today
        elif period == ReportPeriod.LAST_90_DAYS:
            return today - timedelta(days=90), today
        elif period == ReportPeriod.LAST_365_DAYS:
            return today - timedelta(days=365), today
        elif period == ReportPeriod.CUSTOM and custom_start and custom_end:
            return custom_start, custom_end
        else:
            return today - timedelta(days=30), today

    def _normalize_to_monthly(self, price: Decimal, billing_cycle: str) -> Decimal:
        """Normalize price to monthly equivalent."""
        multipliers = {
            "daily": Decimal("30"),
            "weekly": Decimal("4.33"),
            "monthly": Decimal("1"),
            "quarterly": Decimal("0.333"),
            "yearly": Decimal("0.0833"),
        }
        return price * multipliers.get(billing_cycle, Decimal("1"))

    # -------------------------------------------------------------------------
    # Dashboard
    # -------------------------------------------------------------------------

    def get_dashboard_summary(self, currency: str = "NGN") -> DashboardSummary:
        """Get complete dashboard summary."""
        kpis = self._get_dashboard_kpis(currency)
        charts = self._get_dashboard_charts(currency)

        return DashboardSummary(
            kpis=kpis,
            charts=charts,
            currency=currency,
        )

    def _get_dashboard_kpis(self, currency: str = "NGN") -> DashboardKPIs:
        """Calculate dashboard KPIs."""
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        # Subscription counts
        total = self.db.query(Subscription).count()
        active = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        suspended = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED
        ).count()
        pending = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.PENDING
        ).count()
        cancelled = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.CANCELLED
        ).count()

        # New subscriptions
        new_this_month = self.db.query(Subscription).filter(
            Subscription.created_at >= first_of_month,
            Subscription.status != SubscriptionStatus.CANCELLED,
        ).count()

        new_last_month = self.db.query(Subscription).filter(
            Subscription.created_at >= last_month_start,
            Subscription.created_at < first_of_month,
            Subscription.status != SubscriptionStatus.CANCELLED,
        ).count()

        # Growth rate
        growth_rate = Decimal("0")
        if new_last_month > 0:
            growth_rate = ((new_this_month - new_last_month) / new_last_month) * 100

        # Churned this month
        churned_this_month = self.db.query(Subscription).filter(
            Subscription.cancelled_date >= first_of_month,
        ).count()

        # Churn rate
        churn_rate = Decimal("0")
        if active > 0:
            churn_rate = (churned_this_month / (active + churned_this_month)) * 100

        # MRR calculation
        mrr = self._calculate_total_mrr(currency)

        # Previous month MRR (approximate)
        # For accurate comparison, would need historical snapshot
        previous_mrr = mrr * Decimal("0.95")  # Placeholder

        mrr_growth = Decimal("0")
        if previous_mrr > 0:
            mrr_growth = ((mrr - previous_mrr) / previous_mrr) * 100

        # ARR
        arr = mrr * 12

        # ARPU
        arpu = Decimal("0")
        if active > 0:
            arpu = mrr / active

        # Provisioning stats
        provisioned = self.db.query(Subscription).filter(
            Subscription.provisioned_at.isnot(None),
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).count()

        pending_prov = self.db.query(Subscription).filter(
            Subscription.provisioned_at.is_(None),
            Subscription.router_id.isnot(None),
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
        ).count()

        failed_prov = self.db.query(Subscription).filter(
            Subscription.provisioning_error.isnot(None),
        ).count()

        prov_success_rate = Decimal("0")
        total_prov = provisioned + failed_prov
        if total_prov > 0:
            prov_success_rate = (provisioned / total_prov) * 100

        return DashboardKPIs(
            total_subscriptions=total,
            active_subscriptions=active,
            suspended_subscriptions=suspended,
            pending_subscriptions=pending,
            cancelled_subscriptions=cancelled,
            new_this_month=new_this_month,
            new_last_month=new_last_month,
            growth_rate=growth_rate,
            churned_this_month=churned_this_month,
            churn_rate=churn_rate,
            mrr=mrr,
            mrr_growth=mrr_growth,
            arr=arr,
            average_revenue_per_user=arpu,
            provisioned_count=provisioned,
            pending_provisioning=pending_prov,
            failed_provisioning=failed_prov,
            provisioning_success_rate=prov_success_rate,
        )

    def _get_dashboard_charts(self, currency: str = "NGN") -> DashboardCharts:
        """Get dashboard chart data."""
        # MRR trend (last 12 months)
        mrr_trend = self._get_mrr_trend_data(12, currency)

        # By status
        by_status = {}
        for status in SubscriptionStatus:
            count = self.db.query(Subscription).filter(
                Subscription.status == status
            ).count()
            by_status[status.value] = count

        # By service type
        by_service_type = {}
        for stype in SubscriptionType:
            count = self.db.query(Subscription).filter(
                Subscription.service_type == stype,
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).count()
            by_service_type[stype.value] = count

        # Growth vs churn (last 6 months)
        growth_vs_churn = self._get_growth_vs_churn_data(6)

        # Top plans
        top_plans = self._get_top_plans(10, currency)

        # Revenue by type
        revenue_by_type = {}
        for stype in SubscriptionType:
            mrr = self._calculate_mrr_by_type(stype.value, currency)
            revenue_by_type[stype.value] = float(mrr)

        return DashboardCharts(
            mrr_trend=mrr_trend,
            by_status=by_status,
            by_service_type=by_service_type,
            growth_vs_churn=growth_vs_churn,
            top_plans=top_plans,
            revenue_by_type=revenue_by_type,
        )

    def _get_mrr_trend_data(self, months: int, currency: str) -> List[Dict[str, Any]]:
        """Get MRR trend for last N months."""
        trends = []
        today = date.today()

        for i in range(months - 1, -1, -1):
            # Calculate month
            month_date = today.replace(day=1) - timedelta(days=i * 30)
            month_str = month_date.strftime("%Y-%m")

            # Get subscriptions active in that month
            # This is simplified - ideal would use historical snapshots
            month_end = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

            count = self.db.query(Subscription).filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.created_at <= month_end,
                Subscription.currency == currency,
            ).count()

            # Estimate MRR based on current prices
            mrr = self.db.query(func.sum(
                case(
                    (Subscription.billing_cycle == "daily", Subscription.price * 30),
                    (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                    (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                    (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                    else_=Subscription.price
                )
            )).filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.created_at <= month_end,
                Subscription.currency == currency,
            ).scalar() or Decimal("0")

            trends.append({
                "month": month_str,
                "mrr": float(mrr),
                "count": count,
            })

        return trends

    def _get_growth_vs_churn_data(self, months: int) -> List[Dict[str, Any]]:
        """Get new vs churned for last N months."""
        data = []
        today = date.today()

        for i in range(months - 1, -1, -1):
            month_date = today.replace(day=1) - timedelta(days=i * 30)
            month_start = month_date.replace(day=1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)

            new_count = self.db.query(Subscription).filter(
                Subscription.created_at >= month_start,
                Subscription.created_at < next_month,
            ).count()

            churned_count = self.db.query(Subscription).filter(
                Subscription.cancelled_date >= month_start,
                Subscription.cancelled_date < next_month,
            ).count()

            data.append({
                "month": month_start.strftime("%Y-%m"),
                "new": new_count,
                "churned": churned_count,
            })

        return data

    def _get_top_plans(self, limit: int, currency: str) -> List[Dict[str, Any]]:
        """Get top plans by subscriber count."""
        results = self.db.query(
            Subscription.plan_name,
            func.count(Subscription.id).label("count"),
            func.sum(Subscription.price).label("revenue"),
        ).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).group_by(
            Subscription.plan_name
        ).order_by(
            func.count(Subscription.id).desc()
        ).limit(limit).all()

        return [
            {
                "plan": row[0],
                "count": row[1],
                "revenue": float(row[2] or 0),
            }
            for row in results
        ]

    # -------------------------------------------------------------------------
    # MRR Analytics
    # -------------------------------------------------------------------------

    def get_mrr_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
        currency: str = "NGN",
    ) -> MRRSummary:
        """Get comprehensive MRR analytics."""
        period_start, period_end = self._get_period_dates(period)

        current_mrr = self._calculate_total_mrr(currency)

        # Calculate previous period MRR
        days_in_period = (period_end - period_start).days
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days_in_period)
        # For accurate previous MRR, would need historical data
        previous_mrr = current_mrr * Decimal("0.95")  # Placeholder

        mrr_growth = Decimal("0")
        if previous_mrr > 0:
            mrr_growth = ((current_mrr - previous_mrr) / previous_mrr) * 100

        # Breakdown by service type
        by_service_type = []
        for stype in SubscriptionType:
            type_mrr = self._calculate_mrr_by_type(stype.value, currency)
            pct = (type_mrr / current_mrr * 100) if current_mrr > 0 else Decimal("0")
            count = self.db.query(Subscription).filter(
                Subscription.service_type == stype,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.currency == currency,
            ).count()
            by_service_type.append(MRRBreakdown(
                category="service_type",
                value=stype.value,
                mrr=type_mrr,
                count=count,
                percentage=pct,
            ))

        # Breakdown by billing cycle
        by_billing_cycle = []
        for cycle in ["daily", "weekly", "monthly", "quarterly", "yearly"]:
            cycle_mrr = self._calculate_mrr_by_billing_cycle(cycle, currency)
            pct = (cycle_mrr / current_mrr * 100) if current_mrr > 0 else Decimal("0")
            count = self.db.query(Subscription).filter(
                Subscription.billing_cycle == cycle,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.currency == currency,
            ).count()
            by_billing_cycle.append(MRRBreakdown(
                category="billing_cycle",
                value=cycle,
                mrr=cycle_mrr,
                count=count,
                percentage=pct,
            ))

        # Top plans
        by_plan = self._get_mrr_by_plan(currency, limit=10)

        # Trends
        trends = [
            MRRTrend(
                period=t["month"],
                mrr=Decimal(str(t["mrr"])),
                subscription_count=t["count"],
                arpu=Decimal(str(t["mrr"] / t["count"])) if t["count"] > 0 else Decimal("0"),
            )
            for t in self._get_mrr_trend_data(12, currency)
        ]

        return MRRSummary(
            current_mrr=current_mrr,
            previous_mrr=previous_mrr,
            mrr_growth=mrr_growth,
            arr=current_mrr * 12,
            by_service_type=by_service_type,
            by_plan=by_plan,
            by_billing_cycle=by_billing_cycle,
            trends=trends,
        )

    def _calculate_total_mrr(self, currency: str = "NGN") -> Decimal:
        """Calculate total MRR."""
        result = self.db.query(func.sum(
            case(
                (Subscription.billing_cycle == "daily", Subscription.price * 30),
                (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                else_=Subscription.price
            )
        )).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).scalar()

        return result or Decimal("0")

    def _calculate_mrr_by_type(self, service_type: str, currency: str) -> Decimal:
        """Calculate MRR for a service type."""
        try:
            stype = SubscriptionType(service_type)
        except ValueError:
            return Decimal("0")

        result = self.db.query(func.sum(
            case(
                (Subscription.billing_cycle == "daily", Subscription.price * 30),
                (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                else_=Subscription.price
            )
        )).filter(
            Subscription.service_type == stype,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).scalar()

        return result or Decimal("0")

    def _calculate_mrr_by_billing_cycle(self, cycle: str, currency: str) -> Decimal:
        """Calculate MRR for a billing cycle."""
        result = self.db.query(func.sum(
            case(
                (Subscription.billing_cycle == "daily", Subscription.price * 30),
                (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                else_=Subscription.price
            )
        )).filter(
            Subscription.billing_cycle == cycle,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).scalar()

        return result or Decimal("0")

    def _get_mrr_by_plan(self, currency: str, limit: int = 10) -> List[MRRBreakdown]:
        """Get MRR breakdown by plan."""
        results = self.db.query(
            Subscription.plan_name,
            func.count(Subscription.id).label("count"),
            func.sum(
                case(
                    (Subscription.billing_cycle == "daily", Subscription.price * 30),
                    (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                    (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                    (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                    else_=Subscription.price
                )
            ).label("mrr"),
        ).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).group_by(
            Subscription.plan_name
        ).order_by(
            func.sum(Subscription.price).desc()
        ).limit(limit).all()

        total_mrr = self._calculate_total_mrr(currency)

        return [
            MRRBreakdown(
                category="plan",
                value=row[0],
                count=row[1],
                mrr=row[2] or Decimal("0"),
                percentage=(row[2] / total_mrr * 100) if total_mrr > 0 else Decimal("0"),
            )
            for row in results
        ]

    # -------------------------------------------------------------------------
    # Churn Analysis
    # -------------------------------------------------------------------------

    def get_churn_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
        currency: str = "NGN",
    ) -> ChurnSummary:
        """Get churn analysis summary."""
        period_start, period_end = self._get_period_dates(period)

        # Calculate previous period
        days_in_period = (period_end - period_start).days
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days_in_period)

        # Current period churn
        churned_count = self.db.query(Subscription).filter(
            Subscription.cancelled_date >= period_start,
            Subscription.cancelled_date <= period_end,
        ).count()

        churned_mrr = self.db.query(func.sum(
            case(
                (Subscription.billing_cycle == "daily", Subscription.price * 30),
                (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                else_=Subscription.price
            )
        )).filter(
            Subscription.cancelled_date >= period_start,
            Subscription.cancelled_date <= period_end,
            Subscription.currency == currency,
        ).scalar() or Decimal("0")

        # Calculate churn rate
        active_at_start = self.db.query(Subscription).filter(
            Subscription.created_at < period_start,
            or_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                and_(
                    Subscription.status == SubscriptionStatus.CANCELLED,
                    Subscription.cancelled_date >= period_start,
                )
            ),
        ).count()

        churn_rate = Decimal("0")
        if active_at_start > 0:
            churn_rate = (churned_count / active_at_start) * 100

        # Previous period
        previous_churned = self.db.query(Subscription).filter(
            Subscription.cancelled_date >= prev_start,
            Subscription.cancelled_date <= prev_end,
        ).count()

        previous_active = self.db.query(Subscription).filter(
            Subscription.created_at < prev_start,
            or_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.cancelled_date >= prev_start,
            ),
        ).count()

        previous_churn_rate = Decimal("0")
        if previous_active > 0:
            previous_churn_rate = (previous_churned / previous_active) * 100

        # At-risk (suspended)
        at_risk_count = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED,
        ).count()

        at_risk_mrr = self.db.query(func.sum(
            case(
                (Subscription.billing_cycle == "daily", Subscription.price * 30),
                (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                else_=Subscription.price
            )
        )).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED,
            Subscription.currency == currency,
        ).scalar() or Decimal("0")

        return ChurnSummary(
            period_start=period_start,
            period_end=period_end,
            churned_count=churned_count,
            churn_rate=churn_rate,
            mrr_lost=churned_mrr,
            previous_churned_count=previous_churned,
            previous_churn_rate=previous_churn_rate,
            churn_rate_change=churn_rate - previous_churn_rate,
            at_risk_count=at_risk_count,
            at_risk_mrr=at_risk_mrr,
        )

    # -------------------------------------------------------------------------
    # Revenue Reports
    # -------------------------------------------------------------------------

    def get_revenue_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
        currency: str = "NGN",
    ) -> RevenueSummary:
        """Get revenue summary report."""
        period_start, period_end = self._get_period_dates(period)

        # For actual revenue, integrate with accounting
        # This uses subscription prices as proxy
        mrr = self._calculate_total_mrr(currency)
        days_in_period = (period_end - period_start).days + 1
        estimated_revenue = mrr * (Decimal(str(days_in_period)) / Decimal("30"))

        # By service type
        by_service_type = []
        for stype in SubscriptionType:
            type_mrr = self._calculate_mrr_by_type(stype.value, currency)
            type_revenue = type_mrr * (Decimal(str(days_in_period)) / Decimal("30"))
            pct = (type_revenue / estimated_revenue * 100) if estimated_revenue > 0 else Decimal("0")
            by_service_type.append(RevenueByType(
                category="service_type",
                value=stype.value,
                revenue=type_revenue,
                percentage=pct,
            ))

        # By plan
        by_plan = []
        plan_data = self._get_mrr_by_plan(currency, limit=10)
        for p in plan_data:
            by_plan.append(RevenueByPlan(
                plan_id=0,  # Would need tariff_id
                plan_name=p.value,
                subscriber_count=p.count,
                monthly_revenue=p.mrr,
                total_revenue=p.mrr * (Decimal(str(days_in_period)) / Decimal("30")),
                arpu=p.mrr / p.count if p.count > 0 else Decimal("0"),
                percentage=p.percentage,
            ))

        return RevenueSummary(
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            total_revenue=estimated_revenue,
            subscription_revenue=estimated_revenue,
            by_service_type=by_service_type,
            by_plan=by_plan,
        )

    # -------------------------------------------------------------------------
    # Usage Reports
    # -------------------------------------------------------------------------

    def get_usage_report(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
        limit_top_users: int = 20,
    ) -> UsageReport:
        """Get usage analytics report."""
        period_start, period_end = self._get_period_dates(period)

        # This would integrate with UsageService
        # Placeholder implementation
        from app.models.usage import SubscriptionUsage

        # Get usage totals
        usage_totals = self.db.query(
            func.sum(SubscriptionUsage.upload_bytes).label("upload"),
            func.sum(SubscriptionUsage.download_bytes).label("download"),
            func.count(distinct(SubscriptionUsage.subscription_id)).label("users"),
        ).filter(
            SubscriptionUsage.usage_date >= period_start,
            SubscriptionUsage.usage_date <= period_end,
        ).first()

        total_upload = Decimal(str((usage_totals[0] or 0) / (1024**3)))  # GB
        total_download = Decimal(str((usage_totals[1] or 0) / (1024**3)))
        active_users = usage_totals[2] or 0

        # Top users
        top_users_query = self.db.query(
            SubscriptionUsage.subscription_id,
            Subscription.party_id,
            Subscription.plan_name,
            Subscription.data_cap,
            func.sum(SubscriptionUsage.upload_bytes).label("upload"),
            func.sum(SubscriptionUsage.download_bytes).label("download"),
        ).join(
            Subscription, Subscription.id == SubscriptionUsage.subscription_id
        ).filter(
            SubscriptionUsage.usage_date >= period_start,
            SubscriptionUsage.usage_date <= period_end,
        ).group_by(
            SubscriptionUsage.subscription_id,
            Subscription.party_id,
            Subscription.plan_name,
            Subscription.data_cap,
        ).order_by(
            (func.sum(SubscriptionUsage.upload_bytes) + func.sum(SubscriptionUsage.download_bytes)).desc()
        ).limit(limit_top_users).all()

        top_users = []
        for row in top_users_query:
            upload_gb = Decimal(str((row[4] or 0) / (1024**3)))
            download_gb = Decimal(str((row[5] or 0) / (1024**3)))
            total_gb = upload_gb + download_gb
            data_cap = Decimal(str(row[3])) if row[3] else None
            usage_pct = (total_gb / data_cap * 100) if data_cap else None

            top_users.append(TopUsersReport(
                subscription_id=row[0],
                party_id=row[1],
                party_name=f"Party #{row[1]}",  # Would join with Party
                plan_name=row[2],
                upload_gb=upload_gb,
                download_gb=download_gb,
                total_gb=total_gb,
                data_cap_gb=data_cap,
                usage_percent=usage_pct,
            ))

        return UsageReport(
            period_start=period_start,
            period_end=period_end,
            total_upload_gb=total_upload,
            total_download_gb=total_download,
            total_gb=total_upload + total_download,
            avg_per_user_gb=(total_upload + total_download) / active_users if active_users > 0 else Decimal("0"),
            active_users=active_users,
            top_users=top_users,
        )

    # -------------------------------------------------------------------------
    # Provisioning Reports
    # -------------------------------------------------------------------------

    def get_provisioning_report(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> ProvisioningReport:
        """Get provisioning analytics report."""
        period_start, period_end = self._get_period_dates(period)

        from app.models.provisioning_log import ProvisioningLog

        # Overall stats
        total = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
        ).count()

        successful = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
            ProvisioningLog.status == "SUCCESS",
        ).count()

        failed = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
            ProvisioningLog.status == "FAILED",
        ).count()

        pending = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
            ProvisioningLog.status == "PENDING",
        ).count()

        success_rate = Decimal("0")
        if total > 0:
            success_rate = (successful / total) * 100

        # By action
        by_action = {}
        actions = self.db.query(
            ProvisioningLog.action,
            ProvisioningLog.status,
            func.count(ProvisioningLog.id),
        ).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
        ).group_by(
            ProvisioningLog.action,
            ProvisioningLog.status,
        ).all()

        for action, status, count in actions:
            if action not in by_action:
                by_action[action] = {"total": 0, "success": 0, "failed": 0}
            by_action[action]["total"] += count
            if status == "SUCCESS":
                by_action[action]["success"] += count
            elif status == "FAILED":
                by_action[action]["failed"] += count

        # By router
        by_router_query = self.db.query(
            ProvisioningLog.router_id,
            func.count(ProvisioningLog.id).label("total"),
            func.sum(case((ProvisioningLog.status == "SUCCESS", 1), else_=0)).label("success"),
            func.sum(case((ProvisioningLog.status == "FAILED", 1), else_=0)).label("failed"),
        ).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
            ProvisioningLog.router_id.isnot(None),
        ).group_by(
            ProvisioningLog.router_id
        ).all()

        by_router = [
            ProvisioningSuccessRate(
                category="router",
                value=str(row[0]),
                total=row[1],
                successful=row[2] or 0,
                failed=row[3] or 0,
                success_rate=Decimal(str((row[2] or 0) / row[1] * 100)) if row[1] > 0 else Decimal("0"),
            )
            for row in by_router_query
        ]

        # Average duration
        avg_duration = self.db.query(
            func.avg(ProvisioningLog.duration_ms)
        ).filter(
            ProvisioningLog.started_at >= period_start,
            ProvisioningLog.started_at <= period_end,
            ProvisioningLog.duration_ms.isnot(None),
        ).scalar() or 0

        # Recent failures
        recent_failures_query = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.status == "FAILED",
        ).order_by(
            ProvisioningLog.started_at.desc()
        ).limit(10).all()

        recent_failures = [
            {
                "id": f.id,
                "subscription_id": f.subscription_id,
                "router_id": f.router_id,
                "action": f.action,
                "error": f.error_message,
                "started_at": f.started_at.isoformat() if f.started_at else None,
            }
            for f in recent_failures_query
        ]

        return ProvisioningReport(
            period_start=period_start,
            period_end=period_end,
            total_operations=total,
            successful=successful,
            failed=failed,
            pending=pending,
            overall_success_rate=success_rate,
            by_action=by_action,
            by_router=by_router,
            avg_duration_ms=int(avg_duration),
            recent_failures=recent_failures,
        )

    # -------------------------------------------------------------------------
    # Customer LTV Reports
    # -------------------------------------------------------------------------

    def get_customer_ltv_report(self, currency: str = "NGN") -> CustomerLTVReport:
        """Get customer lifetime value report."""
        from app.models.party import Party

        # Calculate LTV metrics
        # LTV = Average Monthly Revenue * Average Customer Lifespan

        # Get average monthly revenue per customer
        avg_monthly = self.db.query(
            func.avg(
                case(
                    (Subscription.billing_cycle == "daily", Subscription.price * 30),
                    (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                    (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                    (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                    else_=Subscription.price
                )
            )
        ).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.currency == currency,
        ).scalar() or Decimal("0")

        # Calculate average tenure
        today = datetime.now(timezone.utc)
        tenure_query = self.db.query(
            func.avg(
                extract('epoch', today - Subscription.created_at) / (30 * 24 * 3600)  # months
            )
        ).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).scalar() or 0

        avg_tenure_months = Decimal(str(round(tenure_query, 1)))

        # Estimate LTV
        avg_ltv = avg_monthly * avg_tenure_months

        # LTV distribution
        ltv_brackets = [
            ("0-10000", 0, 10000),
            ("10000-50000", 10000, 50000),
            ("50000-100000", 50000, 100000),
            ("100000-500000", 100000, 500000),
            ("500000+", 500000, float('inf')),
        ]

        ltv_distribution = {}
        for label, low, high in ltv_brackets:
            # Simplified - would need per-customer calculation
            ltv_distribution[label] = 0  # Placeholder

        # By service type
        by_service_type = {}
        for stype in SubscriptionType:
            type_avg = self.db.query(
                func.avg(
                    case(
                        (Subscription.billing_cycle == "daily", Subscription.price * 30),
                        (Subscription.billing_cycle == "weekly", Subscription.price * Decimal("4.33")),
                        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
                        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
                        else_=Subscription.price
                    )
                )
            ).filter(
                Subscription.service_type == stype,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.currency == currency,
            ).scalar() or Decimal("0")
            by_service_type[stype.value] = type_avg * avg_tenure_months

        # Customer segments
        segments = []

        # High value (top 20% by spend)
        high_value_threshold = avg_monthly * Decimal("2")
        high_value_count = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.price >= high_value_threshold,
            Subscription.currency == currency,
        ).count()

        segments.append(CustomerSegment(
            segment="high_value",
            count=high_value_count,
            mrr=self._calculate_total_mrr(currency) * Decimal("0.5"),  # Estimate
            avg_ltv=avg_ltv * Decimal("2"),
        ))

        # At risk (suspended)
        at_risk_count = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED,
        ).count()
        segments.append(CustomerSegment(
            segment="at_risk",
            count=at_risk_count,
        ))

        # New (last 30 days)
        new_threshold = today - timedelta(days=30)
        new_count = self.db.query(Subscription).filter(
            Subscription.created_at >= new_threshold,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).count()
        segments.append(CustomerSegment(
            segment="new",
            count=new_count,
            avg_tenure_months=Decimal("0.5"),
        ))

        return CustomerLTVReport(
            avg_ltv=avg_ltv,
            avg_tenure_months=avg_tenure_months,
            avg_monthly_revenue=avg_monthly,
            ltv_distribution=ltv_distribution,
            by_service_type=by_service_type,
            segments=segments,
        )

    # -------------------------------------------------------------------------
    # Export Helpers
    # -------------------------------------------------------------------------

    def export_to_dict(self, report: Any) -> Dict[str, Any]:
        """Convert a report dataclass to dictionary for JSON export."""
        from dataclasses import asdict, is_dataclass

        if is_dataclass(report):
            result = asdict(report)
            # Convert Decimals to floats for JSON
            return self._convert_decimals(result)
        return report

    def _convert_decimals(self, obj: Any) -> Any:
        """Recursively convert Decimal to float."""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(i) for i in obj]
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
