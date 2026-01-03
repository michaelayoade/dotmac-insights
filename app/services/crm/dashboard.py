"""CRM dashboard service - business logic for CRM dashboard and KPIs.

This service encapsulates CRM dashboard operations:
- Dashboard summary with KPI cards
- Pipeline visualization
- Funnel charts
- Activity summaries
- Leaderboards

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import (
    Opportunity,
    OpportunityStatus,
    OpportunityStage,
    Activity,
    ActivityStatus,
    ActivityType,
)
from app.models.party import Party, PartyRole
from app.services.base import scoped_query
from app.utils.datetime_utils import utc_now

from .dashboard_types import (
    DashboardFilters,
    DashboardSummary,
    KPICard,
    PipelineChart,
    FunnelChart,
    StageDistribution,
    RevenueTrend,
    ConversionTrend,
    SalesForecast,
    TeamActivitySummary,
    UpcomingTask,
    OverdueItems,
    SalesRepRanking,
)

if TYPE_CHECKING:
    from app.auth import Principal


# Lead role code
LEAD_ROLE = "lead"


class CRMDashboardService:
    """Service for CRM dashboard and KPIs.

    All methods are read-only queries. No commits needed.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Main Dashboard
    # -------------------------------------------------------------------------

    def get_dashboard_summary(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> DashboardSummary:
        """Get complete CRM dashboard summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            DashboardSummary with all metrics.
        """
        today = date.today()
        period_start = self._get_period_start(filters.period if filters else "month", today)

        # Lead metrics
        leads_query = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
        )
        total_leads = leads_query.count()

        new_leads = (
            leads_query.filter(PartyRole.since >= period_start).count()
        )

        qualified_leads = (
            leads_query.filter(PartyRole.qualification.in_(["Hot", "Warm", "Qualified"])).count()
        )

        # Opportunity metrics
        opp_query = scoped_query(self.db.query(Opportunity), self.principal)

        total_opps = opp_query.count()
        open_opps = opp_query.filter(Opportunity.status == OpportunityStatus.OPEN).count()

        open_opps_list = (
            opp_query.filter(Opportunity.status == OpportunityStatus.OPEN).all()
        )
        pipeline_value = sum(o.deal_value or Decimal("0") for o in open_opps_list)

        # Weighted pipeline
        stages = self.db.query(OpportunityStage).all()
        stage_probs = {s.id: (s.probability or 50) / 100 for s in stages}

        weighted_value = Decimal("0")
        for opp in open_opps_list:
            prob = stage_probs.get(opp.stage_id, 0.5)
            weighted_value += (opp.deal_value or Decimal("0")) * Decimal(str(prob))

        # Activity metrics
        activity_query = scoped_query(self.db.query(Activity), self.principal)
        now = utc_now()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        activities_due_today = (
            activity_query.filter(
                Activity.scheduled_at >= today_start,
                Activity.scheduled_at <= today_end,
                Activity.status == ActivityStatus.PLANNED,
            ).count()
        )

        overdue_activities = (
            activity_query.filter(
                Activity.scheduled_at < now,
                Activity.status == ActivityStatus.PLANNED,
            ).count()
        )

        activities_completed = (
            activity_query.filter(
                Activity.completed_at >= period_start,
                Activity.status == ActivityStatus.COMPLETED,
            ).count()
        )

        # Won deals
        won_deals = (
            opp_query.filter(
                Opportunity.status == OpportunityStatus.WON,
                Opportunity.closed_at >= period_start,
            ).all()
        )
        won_count = len(won_deals)
        won_value = sum(o.deal_value or Decimal("0") for o in won_deals)
        avg_deal = (won_value / won_count) if won_count > 0 else Decimal("0")

        # Win rate
        closed_opps = (
            opp_query.filter(
                Opportunity.status.in_([OpportunityStatus.WON, OpportunityStatus.LOST]),
                Opportunity.closed_at >= period_start,
            ).count()
        )
        win_rate = (won_count / closed_opps * 100) if closed_opps > 0 else 0.0

        # Lead conversion rate
        converted_count = (
            self.db.query(func.count(func.distinct(Opportunity.party_id)))
            .filter(Opportunity.created_at >= period_start)
            .scalar() or 0
        )
        lead_conv_rate = (converted_count / new_leads * 100) if new_leads > 0 else 0.0

        # Build KPI cards
        kpi_cards = self._build_kpi_cards(
            total_leads=total_leads,
            new_leads=new_leads,
            pipeline_value=pipeline_value,
            won_value=won_value,
            win_rate=win_rate,
            activities_due=activities_due_today,
        )

        return DashboardSummary(
            total_leads=total_leads,
            new_leads_this_period=new_leads,
            qualified_leads=qualified_leads,
            lead_conversion_rate=lead_conv_rate,
            total_opportunities=total_opps,
            open_opportunities=open_opps,
            pipeline_value=pipeline_value,
            weighted_pipeline_value=weighted_value,
            activities_due_today=activities_due_today,
            overdue_activities=overdue_activities,
            activities_completed_this_period=activities_completed,
            won_deals_this_period=won_count,
            won_value_this_period=won_value,
            avg_deal_size=avg_deal,
            win_rate=win_rate,
            kpi_cards=kpi_cards,
        )

    def get_kpi_cards(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> List[KPICard]:
        """Get KPI cards for dashboard.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of KPICard.
        """
        summary = self.get_dashboard_summary(filters)
        return summary.kpi_cards

    def _build_kpi_cards(
        self,
        total_leads: int,
        new_leads: int,
        pipeline_value: Decimal,
        won_value: Decimal,
        win_rate: float,
        activities_due: int,
    ) -> List[KPICard]:
        """Build KPI cards from metrics."""
        return [
            KPICard(
                key="new_leads",
                title="New Leads",
                value=new_leads,
                formatted_value=str(new_leads),
                trend=None,
                trend_direction=None,
                comparison_period="this month",
                icon="user-plus",
                color="blue",
            ),
            KPICard(
                key="pipeline_value",
                title="Pipeline Value",
                value=pipeline_value,
                formatted_value=f"₦{pipeline_value:,.0f}",
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="chart-bar",
                color="green",
            ),
            KPICard(
                key="won_revenue",
                title="Won Revenue",
                value=won_value,
                formatted_value=f"₦{won_value:,.0f}",
                trend=None,
                trend_direction=None,
                comparison_period="this month",
                icon="currency-dollar",
                color="emerald",
            ),
            KPICard(
                key="win_rate",
                title="Win Rate",
                value=win_rate,
                formatted_value=f"{win_rate:.1f}%",
                trend=None,
                trend_direction=None,
                comparison_period=None,
                icon="trophy",
                color="amber",
            ),
            KPICard(
                key="activities_due",
                title="Activities Due",
                value=activities_due,
                formatted_value=str(activities_due),
                trend=None,
                trend_direction=None,
                comparison_period="today",
                icon="calendar",
                color="purple",
            ),
        ]

    # -------------------------------------------------------------------------
    # Pipeline Visualization
    # -------------------------------------------------------------------------

    def get_pipeline_chart(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> PipelineChart:
        """Get pipeline chart data.

        Args:
            filters: Optional filter criteria.

        Returns:
            PipelineChart with stage breakdown.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.OPEN)

        if filters and filters.owner_id:
            query = query.filter(Opportunity.owner_id == filters.owner_id)

        opportunities = query.all()

        # Get stages
        stages_list = self.db.query(OpportunityStage).order_by(OpportunityStage.order).all()
        stage_info = {s.id: {"name": s.name, "color": s.color, "order": s.order} for s in stages_list}

        # Group by stage
        by_stage: Dict[int, Dict[str, Any]] = {}
        for opp in opportunities:
            if opp.stage_id not in by_stage:
                info = stage_info.get(opp.stage_id, {"name": "Unknown", "color": None, "order": 999})
                by_stage[opp.stage_id] = {
                    "id": opp.stage_id,
                    "name": info["name"],
                    "color": info["color"],
                    "order": info["order"],
                    "count": 0,
                    "value": Decimal("0"),
                }
            by_stage[opp.stage_id]["count"] += 1
            by_stage[opp.stage_id]["value"] += opp.deal_value or Decimal("0")

        stages = sorted(by_stage.values(), key=lambda x: x["order"])
        total_count = sum(s["count"] for s in stages)
        total_value = sum(s["value"] for s in stages)
        avg_per_stage = (total_value / len(stages)) if stages else Decimal("0")

        return PipelineChart(
            stages=stages,
            total_count=total_count,
            total_value=total_value,
            avg_per_stage=avg_per_stage,
        )

    def get_funnel_chart(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> FunnelChart:
        """Get lead/opportunity funnel data.

        Args:
            filters: Optional filter criteria.

        Returns:
            FunnelChart with funnel levels.
        """
        period_start = self._get_period_start(
            filters.period if filters else "month",
            date.today()
        )

        # Lead counts by qualification
        leads_query = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
        )
        if period_start:
            leads_query = leads_query.filter(PartyRole.since >= period_start)

        leads = leads_query.all()
        total_leads = len(leads)

        # Leads by qualification stage
        new_leads = len([l for l in leads if not l.qualification or l.qualification == "Cold"])
        qualified = len([l for l in leads if l.qualification in ("Warm", "Hot", "Qualified")])

        # Opportunities created
        opp_query = scoped_query(self.db.query(Opportunity), self.principal)
        if period_start:
            opp_query = opp_query.filter(Opportunity.created_at >= period_start)

        opportunities = opp_query.all()
        total_opps = len(opportunities)
        won = len([o for o in opportunities if o.status == OpportunityStatus.WON])

        # Build funnel
        levels = []
        if total_leads > 0:
            levels.append({
                "name": "All Leads",
                "count": total_leads,
                "value": Decimal("0"),
                "conversion_rate": 100.0,
            })

        if qualified > 0:
            levels.append({
                "name": "Qualified Leads",
                "count": qualified,
                "value": Decimal("0"),
                "conversion_rate": (qualified / total_leads * 100) if total_leads > 0 else 0,
            })

        if total_opps > 0:
            opp_value = sum(o.deal_value or Decimal("0") for o in opportunities)
            levels.append({
                "name": "Opportunities",
                "count": total_opps,
                "value": opp_value,
                "conversion_rate": (total_opps / qualified * 100) if qualified > 0 else 0,
            })

        if won > 0:
            won_value = sum(
                o.deal_value or Decimal("0")
                for o in opportunities if o.status == OpportunityStatus.WON
            )
            levels.append({
                "name": "Won Deals",
                "count": won,
                "value": won_value,
                "conversion_rate": (won / total_opps * 100) if total_opps > 0 else 0,
            })

        overall_conversion = (won / total_leads * 100) if total_leads > 0 else 0.0

        return FunnelChart(
            levels=levels,
            overall_conversion=overall_conversion,
            drop_off_stages=[],
        )

    def get_stage_distribution(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> List[StageDistribution]:
        """Get opportunity distribution by stage.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of StageDistribution.
        """
        pipeline = self.get_pipeline_chart(filters)
        total_value = pipeline.total_value

        results = []
        for stage_data in pipeline.stages:
            pct = float(stage_data["value"] / total_value * 100) if total_value > 0 else 0.0
            avg_value = (
                stage_data["value"] / stage_data["count"]
            ) if stage_data["count"] > 0 else Decimal("0")

            results.append(StageDistribution(
                stage_id=stage_data["id"],
                stage_name=stage_data["name"],
                opportunity_count=stage_data["count"],
                total_value=stage_data["value"],
                avg_value=avg_value,
                avg_days_in_stage=0.0,  # Would need stage transition tracking
                percentage_of_pipeline=pct,
            ))

        return results

    # -------------------------------------------------------------------------
    # Trends
    # -------------------------------------------------------------------------

    def get_revenue_trend(
        self,
        filters: Optional[DashboardFilters] = None,
        period: str = "monthly",
    ) -> RevenueTrend:
        """Get revenue trend over time.

        Args:
            filters: Optional filter criteria.
            period: Grouping period.

        Returns:
            RevenueTrend with data points.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.WON)
        query = query.filter(Opportunity.closed_at.isnot(None))

        if filters:
            if filters.start_date:
                query = query.filter(Opportunity.closed_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Opportunity.closed_at <= filters.end_date)
            if filters.owner_id:
                query = query.filter(Opportunity.owner_id == filters.owner_id)

        won_opps = query.all()

        # Group by period
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"value": Decimal("0"), "count": 0}
        )

        for opp in won_opps:
            if opp.closed_at:
                if period == "monthly":
                    key = opp.closed_at.strftime("%Y-%m")
                elif period == "weekly":
                    key = opp.closed_at.strftime("%Y-W%W")
                else:
                    key = opp.closed_at.strftime("%Y-%m-%d")

                grouped[key]["value"] += opp.deal_value or Decimal("0")
                grouped[key]["count"] += 1

        data_points = []
        for period_key in sorted(grouped.keys()):
            data = grouped[period_key]
            avg = (data["value"] / data["count"]) if data["count"] > 0 else Decimal("0")
            data_points.append({
                "period": period_key,
                "value": data["value"],
                "count": data["count"],
                "avg": avg,
            })

        total = sum(d["value"] for d in data_points)
        avg_rev = (total / len(data_points)) if data_points else Decimal("0")

        # Determine trend
        if len(data_points) >= 2:
            recent = data_points[-1]["value"]
            previous = data_points[-2]["value"]
            if recent > previous:
                direction = "up"
                pct = float((recent - previous) / previous * 100) if previous > 0 else 0
            elif recent < previous:
                direction = "down"
                pct = float((previous - recent) / previous * 100) if previous > 0 else 0
            else:
                direction = "stable"
                pct = 0.0
        else:
            direction = "stable"
            pct = 0.0

        return RevenueTrend(
            period_type=period,
            data_points=data_points,
            total_revenue=total,
            avg_revenue=avg_rev,
            trend_direction=direction,
            trend_percentage=pct,
        )

    def get_conversion_trend(
        self,
        filters: Optional[DashboardFilters] = None,
        period: str = "weekly",
    ) -> ConversionTrend:
        """Get conversion rate trend over time.

        Args:
            filters: Optional filter criteria.
            period: Grouping period.

        Returns:
            ConversionTrend with data points.
        """
        # Get closed opportunities grouped by period
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status.in_([OpportunityStatus.WON, OpportunityStatus.LOST]))
        query = query.filter(Opportunity.closed_at.isnot(None))

        if filters:
            if filters.start_date:
                query = query.filter(Opportunity.closed_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Opportunity.closed_at <= filters.end_date)

        closed_opps = query.all()

        grouped: Dict[str, Dict[str, int]] = defaultdict(lambda: {"won": 0, "total": 0})

        for opp in closed_opps:
            if opp.closed_at:
                if period == "monthly":
                    key = opp.closed_at.strftime("%Y-%m")
                elif period == "weekly":
                    key = opp.closed_at.strftime("%Y-W%W")
                else:
                    key = opp.closed_at.strftime("%Y-%m-%d")

                grouped[key]["total"] += 1
                if opp.status == OpportunityStatus.WON:
                    grouped[key]["won"] += 1

        data_points = []
        rates = []
        for period_key in sorted(grouped.keys()):
            data = grouped[period_key]
            rate = (data["won"] / data["total"] * 100) if data["total"] > 0 else 0.0
            rates.append((period_key, rate))
            data_points.append({
                "period": period_key,
                "rate": rate,
                "converted": data["won"],
                "total": data["total"],
            })

        avg_rate = sum(r[1] for r in rates) / len(rates) if rates else 0.0
        best = max(rates, key=lambda x: x[1])[0] if rates else None
        worst = min(rates, key=lambda x: x[1])[0] if rates else None

        return ConversionTrend(
            period_type=period,
            data_points=data_points,
            avg_conversion_rate=avg_rate,
            best_period=best,
            worst_period=worst,
        )

    # -------------------------------------------------------------------------
    # Forecast
    # -------------------------------------------------------------------------

    def get_forecast(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> SalesForecast:
        """Get sales forecast.

        Args:
            filters: Optional filter criteria.

        Returns:
            SalesForecast with predictions.
        """
        today = date.today()
        quarter = (today.month - 1) // 3 + 1
        forecast_period = f"{today.year}-Q{quarter}"

        # Get open opportunities
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.OPEN)

        opportunities = query.all()

        # Get stage probabilities
        stages = self.db.query(OpportunityStage).all()
        stage_probs = {s.id: (s.probability or 50) / 100 for s in stages}
        stage_names = {s.id: s.name for s in stages}

        # Calculate forecast
        total_pipeline = Decimal("0")
        weighted_total = Decimal("0")
        by_stage: Dict[int, Decimal] = defaultdict(Decimal)

        for opp in opportunities:
            val = opp.deal_value or Decimal("0")
            prob = stage_probs.get(opp.stage_id, 0.5)
            total_pipeline += val
            weighted_total += val * Decimal(str(prob))
            by_stage[opp.stage_id] += val * Decimal(str(prob))

        # Build by_stage list
        by_stage_list = [
            {
                "stage": stage_names.get(sid, "Unknown"),
                "predicted": val,
                "probability": stage_probs.get(sid, 0.5) * 100,
            }
            for sid, val in by_stage.items()
        ]

        # Best/worst case (simplified)
        best_case = total_pipeline
        worst_case = weighted_total * Decimal("0.7")

        return SalesForecast(
            forecast_period=forecast_period,
            predicted_revenue=weighted_total,
            confidence_level=70.0,
            best_case=best_case,
            worst_case=worst_case,
            by_month=[],
            by_stage=by_stage_list,
        )

    # -------------------------------------------------------------------------
    # Activity & Tasks
    # -------------------------------------------------------------------------

    def get_team_activity_summary(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> TeamActivitySummary:
        """Get team activity summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            TeamActivitySummary.
        """
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        query = scoped_query(self.db.query(Activity), self.principal)

        # Total this week
        week_start = today - timedelta(days=today.weekday())
        activities = query.filter(Activity.scheduled_at >= week_start).all()
        total = len(activities)

        completed_today = len([
            a for a in activities
            if a.status == ActivityStatus.COMPLETED
            and a.completed_at
            and a.completed_at.date() == today
        ])

        pending_today = len([
            a for a in activities
            if a.status == ActivityStatus.PLANNED
            and a.scheduled_at
            and a.scheduled_at.date() == today
        ])

        now = utc_now()
        overdue = len([
            a for a in activities
            if a.status == ActivityStatus.PLANNED
            and a.scheduled_at
            and a.scheduled_at < now
        ])

        # By type
        by_type: Dict[str, int] = defaultdict(int)
        for a in activities:
            type_str = a.activity_type.value if hasattr(a.activity_type, 'value') else str(a.activity_type)
            by_type[type_str] += 1

        completed = len([a for a in activities if a.status == ActivityStatus.COMPLETED])
        rate = (completed / total * 100) if total > 0 else 0.0

        return TeamActivitySummary(
            total_activities=total,
            completed_today=completed_today,
            pending_today=pending_today,
            overdue=overdue,
            by_type=dict(by_type),
            by_rep=[],
            completion_rate=rate,
        )

    def get_upcoming_tasks(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[UpcomingTask]:
        """Get upcoming tasks for a user.

        Args:
            user_id: User/employee ID.
            limit: Maximum tasks to return.

        Returns:
            List of UpcomingTask.
        """
        now = utc_now()
        week_ahead = now + timedelta(days=7)

        activities = (
            self.db.query(Activity)
            .filter(
                Activity.status == ActivityStatus.PLANNED,
                Activity.scheduled_at >= now,
                Activity.scheduled_at <= week_ahead,
                Activity.owner_id == user_id,
            )
            .order_by(Activity.scheduled_at)
            .limit(limit)
            .all()
        )

        results = []
        for a in activities:
            results.append(UpcomingTask(
                id=a.id,
                type=a.activity_type.value if hasattr(a.activity_type, 'value') else str(a.activity_type),
                subject=a.subject,
                due_date=a.scheduled_at,
                due_time=a.scheduled_at.strftime("%H:%M") if a.scheduled_at else None,
                party_id=a.party_id,
                party_name=None,  # Would need join
                opportunity_id=a.opportunity_id,
                opportunity_name=None,  # Would need join
                priority=a.priority or "medium",
                is_overdue=a.scheduled_at < now if a.scheduled_at else False,
            ))

        return results

    def get_overdue_items(
        self,
        filters: Optional[DashboardFilters] = None,
    ) -> OverdueItems:
        """Get overdue items summary.

        Args:
            filters: Optional filter criteria.

        Returns:
            OverdueItems summary.
        """
        now = utc_now()
        today = date.today()

        # Overdue activities
        overdue_activities = (
            scoped_query(self.db.query(Activity), self.principal)
            .filter(
                Activity.status == ActivityStatus.PLANNED,
                Activity.scheduled_at < now,
            )
            .count()
        )

        # Overdue opportunities (past expected close)
        overdue_opps = (
            scoped_query(self.db.query(Opportunity), self.principal)
            .filter(
                Opportunity.status == OpportunityStatus.OPEN,
                Opportunity.expected_close_date < today,
            )
            .all()
        )
        overdue_opp_count = len(overdue_opps)
        overdue_opp_value = sum(o.deal_value or Decimal("0") for o in overdue_opps)

        return OverdueItems(
            overdue_activities=overdue_activities,
            overdue_opportunities=overdue_opp_count,
            overdue_quotes=0,  # Would need quotation service
            overdue_tasks=overdue_activities,
            total_overdue_value=overdue_opp_value,
            items=[],
        )

    # -------------------------------------------------------------------------
    # Leaderboard
    # -------------------------------------------------------------------------

    def get_sales_leaderboard(
        self,
        filters: Optional[DashboardFilters] = None,
        limit: int = 10,
    ) -> List[SalesRepRanking]:
        """Get sales leaderboard.

        Args:
            filters: Optional filter criteria.
            limit: Maximum reps to return.

        Returns:
            List of SalesRepRanking sorted by won value.
        """
        period_start = self._get_period_start(
            filters.period if filters else "month",
            date.today()
        )

        # Get won opportunities in period
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.WON)

        if period_start:
            query = query.filter(Opportunity.closed_at >= period_start)

        if filters and filters.owner_id:
            query = query.filter(Opportunity.owner_id == filters.owner_id)

        won_opps = query.all()

        # Group by owner
        by_owner: Dict[int, Dict[str, Any]] = {}
        for opp in won_opps:
            if opp.owner_id:
                if opp.owner_id not in by_owner:
                    by_owner[opp.owner_id] = {
                        "won_deals": 0,
                        "won_value": Decimal("0"),
                        "total_closed": 0,
                    }
                by_owner[opp.owner_id]["won_deals"] += 1
                by_owner[opp.owner_id]["won_value"] += opp.deal_value or Decimal("0")

        # Get activity counts
        for owner_id in by_owner:
            activity_count = (
                self.db.query(func.count(Activity.id))
                .filter(Activity.owner_id == owner_id)
                .scalar() or 0
            )
            by_owner[owner_id]["activities"] = activity_count

        # Get lost deals for win rate
        lost_query = scoped_query(self.db.query(Opportunity), self.principal)
        lost_query = lost_query.filter(Opportunity.status == OpportunityStatus.LOST)
        if period_start:
            lost_query = lost_query.filter(Opportunity.closed_at >= period_start)

        for opp in lost_query.all():
            if opp.owner_id and opp.owner_id in by_owner:
                by_owner[opp.owner_id]["total_closed"] += 1

        # Build results
        results = []
        for owner_id, data in by_owner.items():
            total_closed = data["won_deals"] + data.get("total_closed", 0)
            win_rate = (data["won_deals"] / total_closed * 100) if total_closed > 0 else 0.0

            results.append(SalesRepRanking(
                rank=0,  # Will be set after sorting
                rep_id=owner_id,
                rep_name=f"Rep {owner_id}",  # Would need user lookup
                avatar_url=None,
                won_deals=data["won_deals"],
                won_value=data["won_value"],
                activities=data.get("activities", 0),
                win_rate=win_rate,
                trend=None,
            ))

        # Sort and rank
        results.sort(key=lambda x: x.won_value, reverse=True)
        for i, rep in enumerate(results[:limit], 1):
            rep.rank = i

        return results[:limit]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_period_start(self, period: str, reference_date: date) -> Optional[date]:
        """Get start date for a period."""
        if period == "day":
            return reference_date
        elif period == "week":
            return reference_date - timedelta(days=reference_date.weekday())
        elif period == "month":
            return date(reference_date.year, reference_date.month, 1)
        elif period == "quarter":
            quarter = (reference_date.month - 1) // 3
            return date(reference_date.year, quarter * 3 + 1, 1)
        elif period == "year":
            return date(reference_date.year, 1, 1)
        return None
