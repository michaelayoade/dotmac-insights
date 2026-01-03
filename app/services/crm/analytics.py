"""CRM analytics service - business logic for CRM reporting and analytics.

This service encapsulates CRM analytics operations:
- Lead funnel and conversion metrics
- Pipeline forecasting
- Activity analytics
- Sales rep performance
- Territory performance

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import func, case, and_, or_, extract
from sqlalchemy.orm import Session

from app.models.crm import (
    Opportunity,
    OpportunityStatus,
    OpportunityStage,
    Activity,
    ActivityStatus,
    Campaign,
)
from app.models.party import Party, PartyRole
from app.services.base import scoped_query
from app.utils.datetime_utils import utc_now

from .analytics_types import (
    AnalyticsFilters,
    LeadFunnel,
    SourceBreakdown,
    ConversionMetrics,
    PipelineForecast,
    VelocityMetrics,
    AgingAnalysis,
    ActivityMetrics,
    RepPerformance,
    TerritoryPerformance,
    TrendPoint,
)

if TYPE_CHECKING:
    from app.auth import Principal


# Lead role code
LEAD_ROLE = "lead"


class CRMAnalyticsService:
    """Service for CRM analytics and reporting.

    All methods are read-only queries. No commits needed.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Lead Analytics
    # -------------------------------------------------------------------------

    def get_lead_funnel(self, filters: Optional[AnalyticsFilters] = None) -> LeadFunnel:
        """Get lead funnel breakdown.

        Args:
            filters: Optional filter criteria.

        Returns:
            LeadFunnel with breakdown by qualification/status/source.
        """
        # Query leads (Party + PartyRole where role='lead')
        query = (
            self.db.query(PartyRole)
            .join(Party, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))  # Active leads only
        )

        if filters:
            if filters.start_date:
                query = query.filter(PartyRole.since >= filters.start_date)
            if filters.end_date:
                query = query.filter(PartyRole.since <= filters.end_date)
            if filters.owner_id:
                query = query.filter(PartyRole.owner_party_id == filters.owner_id)
            if filters.sources:
                query = query.filter(PartyRole.source.in_(filters.sources))
            elif filters.source:
                query = query.filter(PartyRole.source == filters.source)

        leads = query.all()
        total = len(leads)

        # Group by qualification
        by_qualification: Dict[str, int] = defaultdict(int)
        for lead in leads:
            qual = lead.qualification or "Unqualified"
            by_qualification[qual] += 1

        # Group by status
        by_status: Dict[str, int] = defaultdict(int)
        for lead in leads:
            by_status[lead.status] += 1

        # Group by source
        by_source: Dict[str, int] = defaultdict(int)
        for lead in leads:
            src = lead.source or "Unknown"
            by_source[src] += 1

        # Calculate conversion rate (leads that became opportunities)
        # Leads that converted have an opportunity with same party_id
        lead_party_ids = [lead.party_id for lead in leads]
        if lead_party_ids:
            converted_count = (
                self.db.query(func.count(func.distinct(Opportunity.party_id)))
                .filter(Opportunity.party_id.in_(lead_party_ids))
                .scalar() or 0
            )
            conversion_rate = (converted_count / total * 100) if total > 0 else 0.0
        else:
            conversion_rate = 0.0

        return LeadFunnel(
            total_leads=total,
            by_qualification=dict(by_qualification),
            by_status=dict(by_status),
            by_source=dict(by_source),
            conversion_to_opportunity=conversion_rate,
            avg_time_to_convert_days=None,  # Would need opportunity creation date tracking
        )

    def get_lead_sources_breakdown(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[SourceBreakdown]:
        """Get lead performance breakdown by source.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of SourceBreakdown for each source.
        """
        # Get all leads grouped by source
        query = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
        )

        if filters:
            if filters.start_date:
                query = query.filter(PartyRole.since >= filters.start_date)
            if filters.end_date:
                query = query.filter(PartyRole.since <= filters.end_date)

        leads = query.all()

        # Group leads by source
        leads_by_source: Dict[str, List[PartyRole]] = defaultdict(list)
        for lead in leads:
            src = lead.source or "Unknown"
            leads_by_source[src].append(lead)

        results = []
        for source, source_leads in leads_by_source.items():
            lead_count = len(source_leads)
            party_ids = [lead.party_id for lead in source_leads]

            # Get opportunities for these parties
            opportunities = (
                self.db.query(Opportunity)
                .filter(Opportunity.party_id.in_(party_ids))
                .all()
            ) if party_ids else []

            opp_count = len(opportunities)
            won_opps = [o for o in opportunities if o.status == OpportunityStatus.WON]
            won_count = len(won_opps)
            total_value = sum(o.deal_value or Decimal("0") for o in won_opps)

            conversion_rate = (opp_count / lead_count * 100) if lead_count > 0 else 0.0
            win_rate = (won_count / opp_count * 100) if opp_count > 0 else 0.0
            avg_deal_size = (total_value / won_count) if won_count > 0 else Decimal("0")

            results.append(SourceBreakdown(
                source=source,
                lead_count=lead_count,
                opportunity_count=opp_count,
                won_count=won_count,
                conversion_rate=conversion_rate,
                win_rate=win_rate,
                total_value=total_value,
                avg_deal_size=avg_deal_size,
            ))

        # Sort by lead count descending
        results.sort(key=lambda x: x.lead_count, reverse=True)
        return results

    def get_lead_conversion_rate(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> ConversionMetrics:
        """Get lead-to-opportunity conversion metrics.

        Args:
            filters: Optional filter criteria.

        Returns:
            ConversionMetrics with conversion data.
        """
        funnel = self.get_lead_funnel(filters)
        sources = self.get_lead_sources_breakdown(filters)

        by_source = {s.source: s.conversion_rate for s in sources}

        # Get total leads that converted
        query = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
        )
        leads = query.all()
        lead_party_ids = [lead.party_id for lead in leads]

        if lead_party_ids:
            converted = (
                self.db.query(func.count(func.distinct(Opportunity.party_id)))
                .filter(Opportunity.party_id.in_(lead_party_ids))
                .scalar() or 0
            )
        else:
            converted = 0

        return ConversionMetrics(
            total_leads=funnel.total_leads,
            converted_leads=converted,
            conversion_rate=funnel.conversion_to_opportunity,
            avg_conversion_time_days=funnel.avg_time_to_convert_days,
            by_period=[],  # Would need time-series analysis
            by_source=by_source,
        )

    # -------------------------------------------------------------------------
    # Pipeline Analytics
    # -------------------------------------------------------------------------

    def get_pipeline_forecast(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> PipelineForecast:
        """Get sales pipeline forecast.

        Args:
            filters: Optional filter criteria.

        Returns:
            PipelineForecast with pipeline metrics.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.OPEN)

        if filters:
            if filters.start_date:
                query = query.filter(Opportunity.expected_close_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(Opportunity.expected_close_date <= filters.end_date)
            if filters.owner_id:
                query = query.filter(Opportunity.owner_id == filters.owner_id)
            if filters.stage_id:
                query = query.filter(Opportunity.stage_id == filters.stage_id)

        opportunities = query.all()

        total_value = sum(o.deal_value or Decimal("0") for o in opportunities)

        # Calculate weighted value based on stage probability
        # Get stages with their probabilities
        stages = self.db.query(OpportunityStage).all()
        stage_probs = {s.id: s.probability / 100 if s.probability else 0.5 for s in stages}
        stage_names = {s.id: s.name for s in stages}

        weighted_value = Decimal("0")
        by_stage: Dict[int, Dict[str, Any]] = {}

        for opp in opportunities:
            prob = stage_probs.get(opp.stage_id, 0.5)
            deal_val = opp.deal_value or Decimal("0")
            weighted_value += deal_val * Decimal(str(prob))

            if opp.stage_id not in by_stage:
                by_stage[opp.stage_id] = {
                    "stage_id": opp.stage_id,
                    "name": stage_names.get(opp.stage_id, "Unknown"),
                    "value": Decimal("0"),
                    "count": 0,
                    "probability": prob * 100,
                }
            by_stage[opp.stage_id]["value"] += deal_val
            by_stage[opp.stage_id]["count"] += 1

        # Expected revenue this month
        today = date.today()
        month_end = date(today.year, today.month + 1 if today.month < 12 else 1,
                        1 if today.month < 12 else 1) - timedelta(days=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)

        expected_this_month = sum(
            o.deal_value or Decimal("0")
            for o in opportunities
            if o.expected_close_date and o.expected_close_date <= month_end
        )

        # At-risk (no expected close date or overdue)
        at_risk = sum(
            o.deal_value or Decimal("0")
            for o in opportunities
            if not o.expected_close_date or (o.expected_close_date and o.expected_close_date < today)
        )

        return PipelineForecast(
            total_pipeline_value=total_value,
            weighted_pipeline_value=weighted_value,
            expected_revenue=expected_this_month,
            by_stage=list(by_stage.values()),
            by_month=[],  # Would need monthly grouping
            at_risk_value=at_risk,
        )

    def get_pipeline_velocity(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> VelocityMetrics:
        """Get pipeline velocity metrics.

        Args:
            filters: Optional filter criteria.

        Returns:
            VelocityMetrics with deal speed data.
        """
        # Get won opportunities to calculate cycle time
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

        cycle_times = []
        for opp in won_opps:
            if opp.created_at and opp.closed_at:
                delta = opp.closed_at - opp.created_at
                cycle_times.append(delta.days)

        avg_cycle = sum(cycle_times) / len(cycle_times) if cycle_times else 0.0
        sorted_times = sorted(cycle_times)
        median_cycle = sorted_times[len(sorted_times) // 2] if sorted_times else 0.0

        # Find stuck deals (open with no recent activity)
        today = utc_now()
        stale_threshold = today - timedelta(days=14)

        open_opps = (
            scoped_query(self.db.query(Opportunity), self.principal)
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .all()
        )

        stuck_count = 0
        for opp in open_opps:
            # Check for recent activity
            recent_activity = (
                self.db.query(Activity)
                .filter(Activity.opportunity_id == opp.id)
                .filter(Activity.created_at >= stale_threshold)
                .first()
            )
            if not recent_activity:
                if not opp.updated_at or opp.updated_at < stale_threshold:
                    stuck_count += 1

        return VelocityMetrics(
            avg_deal_cycle_days=avg_cycle,
            median_deal_cycle_days=float(median_cycle),
            avg_stage_time_days={},  # Would need stage transition tracking
            deals_stuck=stuck_count,
            velocity_trend=[],  # Would need time-series analysis
        )

    def get_pipeline_aging(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> AgingAnalysis:
        """Get opportunity aging analysis.

        Args:
            filters: Optional filter criteria.

        Returns:
            AgingAnalysis with aging buckets.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)
        query = query.filter(Opportunity.status == OpportunityStatus.OPEN)

        if filters and filters.owner_id:
            query = query.filter(Opportunity.owner_id == filters.owner_id)

        opportunities = query.all()
        today = date.today()

        # Define aging buckets
        buckets = [
            {"label": "0-30 days", "min_days": 0, "max_days": 30, "count": 0, "value": Decimal("0")},
            {"label": "31-60 days", "min_days": 31, "max_days": 60, "count": 0, "value": Decimal("0")},
            {"label": "61-90 days", "min_days": 61, "max_days": 90, "count": 0, "value": Decimal("0")},
            {"label": "90+ days", "min_days": 91, "max_days": 9999, "count": 0, "value": Decimal("0")},
        ]

        total_value = Decimal("0")
        overdue_count = 0
        overdue_value = Decimal("0")

        for opp in opportunities:
            if opp.created_at:
                age_days = (today - opp.created_at.date()).days
                deal_val = opp.deal_value or Decimal("0")
                total_value += deal_val

                for bucket in buckets:
                    if bucket["min_days"] <= age_days <= bucket["max_days"]:
                        bucket["count"] += 1
                        bucket["value"] += deal_val
                        break

                # Check if overdue (past expected close date)
                if opp.expected_close_date and opp.expected_close_date < today:
                    overdue_count += 1
                    overdue_value += deal_val

        return AgingAnalysis(
            entity_type="opportunity",
            total_count=len(opportunities),
            total_value=total_value,
            buckets=buckets,
            overdue_count=overdue_count,
            overdue_value=overdue_value,
        )

    # -------------------------------------------------------------------------
    # Activity Analytics
    # -------------------------------------------------------------------------

    def get_activity_metrics(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> ActivityMetrics:
        """Get activity analytics for CRM.

        Args:
            filters: Optional filter criteria.

        Returns:
            ActivityMetrics with activity data.
        """
        query = scoped_query(self.db.query(Activity), self.principal)

        if filters:
            if filters.start_date:
                query = query.filter(Activity.scheduled_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Activity.scheduled_at <= filters.end_date)
            if filters.owner_id:
                query = query.filter(Activity.owner_id == filters.owner_id)

        activities = query.all()
        total = len(activities)

        completed = [a for a in activities if a.status == ActivityStatus.COMPLETED]
        completed_count = len(completed)
        completion_rate = (completed_count / total * 100) if total > 0 else 0.0

        # By type
        by_type: Dict[str, int] = defaultdict(int)
        for act in activities:
            type_str = act.activity_type.value if hasattr(act.activity_type, 'value') else str(act.activity_type)
            by_type[type_str] += 1

        # By owner
        owner_stats: Dict[int, Dict[str, Any]] = {}
        for act in activities:
            if act.owner_id not in owner_stats:
                owner_stats[act.owner_id] = {
                    "owner_id": act.owner_id,
                    "name": f"User {act.owner_id}",  # Would need user lookup
                    "count": 0,
                    "completed": 0,
                }
            owner_stats[act.owner_id]["count"] += 1
            if act.status == ActivityStatus.COMPLETED:
                owner_stats[act.owner_id]["completed"] += 1

        # Average activities per deal
        opp_ids = set(a.opportunity_id for a in activities if a.opportunity_id)
        avg_per_deal = (total / len(opp_ids)) if opp_ids else 0.0

        return ActivityMetrics(
            total_activities=total,
            completed_activities=completed_count,
            completion_rate=completion_rate,
            by_type=dict(by_type),
            by_owner=list(owner_stats.values()),
            avg_activities_per_deal=avg_per_deal,
            activities_trend=[],  # Would need time-series analysis
        )

    # -------------------------------------------------------------------------
    # Sales Rep Performance
    # -------------------------------------------------------------------------

    def get_rep_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
        limit: int = 20,
    ) -> List[RepPerformance]:
        """Get sales representative performance metrics.

        Args:
            filters: Optional filter criteria.
            limit: Maximum number of reps to return.

        Returns:
            List of RepPerformance sorted by won value.
        """
        # Get all opportunities grouped by owner
        query = scoped_query(self.db.query(Opportunity), self.principal)

        if filters:
            if filters.start_date:
                query = query.filter(Opportunity.created_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Opportunity.created_at <= filters.end_date)
            if filters.owner_ids:
                query = query.filter(Opportunity.owner_id.in_(filters.owner_ids))

        opportunities = query.all()

        # Group by owner
        by_owner: Dict[int, List[Opportunity]] = defaultdict(list)
        for opp in opportunities:
            if opp.owner_id:
                by_owner[opp.owner_id].append(opp)

        results = []
        for owner_id, opps in by_owner.items():
            won_opps = [o for o in opps if o.status == OpportunityStatus.WON]
            won_value = sum(o.deal_value or Decimal("0") for o in won_opps)
            total_value = sum(o.deal_value or Decimal("0") for o in opps)

            # Get leads assigned to this owner
            leads_query = (
                self.db.query(PartyRole)
                .filter(PartyRole.role == LEAD_ROLE)
                .filter(PartyRole.owner_party_id == owner_id)
            )
            if filters and filters.start_date:
                leads_query = leads_query.filter(PartyRole.since >= filters.start_date)
            leads = leads_query.all()

            # Leads that converted (have opportunities)
            lead_party_ids = [l.party_id for l in leads]
            converted_leads = 0
            if lead_party_ids:
                converted_leads = (
                    self.db.query(func.count(func.distinct(Opportunity.party_id)))
                    .filter(Opportunity.party_id.in_(lead_party_ids))
                    .scalar() or 0
                )

            # Calculate cycle time for won deals
            cycle_times = []
            for opp in won_opps:
                if opp.created_at and opp.closed_at:
                    cycle_times.append((opp.closed_at - opp.created_at).days)
            avg_cycle = sum(cycle_times) / len(cycle_times) if cycle_times else 0.0

            # Get activity count
            activities_count = (
                self.db.query(func.count(Activity.id))
                .filter(Activity.owner_id == owner_id)
                .scalar() or 0
            )

            results.append(RepPerformance(
                rep_id=owner_id,
                rep_name=f"Rep {owner_id}",  # Would need user lookup
                leads_assigned=len(leads),
                leads_converted=converted_leads,
                conversion_rate=(converted_leads / len(leads) * 100) if leads else 0.0,
                opportunities_count=len(opps),
                opportunities_value=total_value,
                won_count=len(won_opps),
                won_value=won_value,
                win_rate=(len(won_opps) / len(opps) * 100) if opps else 0.0,
                avg_deal_size=(won_value / len(won_opps)) if won_opps else Decimal("0"),
                avg_cycle_days=avg_cycle,
                activities_count=activities_count,
            ))

        # Sort by won value and assign ranks
        results.sort(key=lambda x: x.won_value, reverse=True)
        for i, rep in enumerate(results[:limit], 1):
            rep.rank = i

        return results[:limit]

    def get_territory_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[TerritoryPerformance]:
        """Get territory-level performance metrics.

        Args:
            filters: Optional filter criteria.

        Returns:
            List of TerritoryPerformance.
        """
        # This would require opportunities to have territory field
        # For now, return empty list - would need model update
        return []
