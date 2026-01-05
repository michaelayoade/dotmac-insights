"""Support Analytics Service - Comprehensive reporting and insights.

This service provides all analytics, metrics, and reporting capabilities
for the support module including:
- Overview and dashboard statistics
- Volume trends and forecasting
- Resolution and response time analytics
- Agent and team performance
- SLA performance tracking
- Channel and category breakdowns
- Backlog aging analysis
- Pattern insights
- Automation effectiveness
- Knowledge base deflection metrics
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from collections import defaultdict

import sqlalchemy
from sqlalchemy import func, case, extract, and_, or_, distinct
from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketStatus as LegacyTicketStatus, TicketPriority
from app.models.unified_ticket import UnifiedTicket, TicketStatus
from app.models.party import Party, PartyRole
from app.models.agent import Team, TeamMember
from app.models.support_automation import AutomationRule, AutomationLog
from app.models.support_kb import KBArticle, KBArticleFeedback
from app.models.support_csat import CSATSurvey, CSATResponse
from app.models.support_tags import TicketTag

from .types import (
    AnalyticsFilters,
    OverviewStats,
    VolumeDataPoint,
    VolumeTrend,
    ResolutionTimeStats,
    FirstResponseStats,
    AgentPerformance,
    TeamPerformance,
    ChannelStats,
    CategoryStats,
    SLAPerformance,
    BacklogAging,
    ReopenAnalysis,
    PatternInsights,
    AutomationEffectiveness,
    KBDeflection,
    E2EReport,
    TagStats,
    TagTrend,
    AgentSLAStats,
    TeamSLAStats,
    NearMissTicket,
    SLATrendPoint,
    CategorySLAStats,
    PrioritySLAStats,
    SLAAnalyticsSummary,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["SupportAnalyticsService"]


# Priority numeric mapping for averaging
PRIORITY_VALUES = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Status groupings (using UnifiedTicket statuses - no REPLIED in unified model)
OPEN_STATUSES = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING, TicketStatus.ON_HOLD]
CLOSED_STATUSES = [TicketStatus.RESOLVED, TicketStatus.CLOSED]


class SupportAnalyticsService:
    """Service for support analytics and reporting.

    All methods are read-only and do not modify data.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
    ):
        self.db = db
        self.principal = principal

    # =========================================================================
    # OVERVIEW & DASHBOARD
    # =========================================================================

    def get_overview(self, filters: Optional[AnalyticsFilters] = None) -> OverviewStats:
        """Get high-level support overview statistics."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Base query with date filter
        base_q = self.db.query(Ticket).filter(Ticket.created_at >= start_dt)
        if end_dt:
            base_q = base_q.filter(Ticket.created_at <= end_dt)

        # Apply additional filters
        base_q = self._apply_filters(base_q, filters)

        # Counts
        total = base_q.count()
        open_count = base_q.filter(Ticket.status.in_(OPEN_STATUSES)).count()
        resolved = base_q.filter(Ticket.status == TicketStatus.RESOLVED).count()
        closed = base_q.filter(Ticket.status == TicketStatus.CLOSED).count()
        pending = base_q.filter(Ticket.status == TicketStatus.ON_HOLD).count()

        # Resolution time
        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600
        avg_resolution = (
            base_q.filter(
                Ticket.resolution_date.isnot(None),
                Ticket.opening_date.isnot(None),
            )
            .with_entities(func.avg(resolution_hours))
            .scalar()
            or 0
        )

        # First response time
        first_response_hours = func.extract(
            "epoch", Ticket.first_responded_on - Ticket.created_at
        ) / 3600
        avg_first_response = (
            base_q.filter(Ticket.first_responded_on.isnot(None))
            .with_entities(func.avg(first_response_hours))
            .scalar()
            or 0
        )

        # SLA attainment
        sla_met = base_q.filter(
            Ticket.resolution_by.isnot(None),
            Ticket.resolution_date.isnot(None),
            Ticket.resolution_date <= Ticket.resolution_by,
        ).count()
        sla_total = base_q.filter(
            Ticket.resolution_by.isnot(None),
            Ticket.resolution_date.isnot(None),
        ).count()
        sla_pct = (sla_met / sla_total * 100) if sla_total > 0 else 0

        # CSAT score
        csat_score = self._get_avg_csat(start_dt, end_dt, filters)

        return OverviewStats(
            total_tickets=total,
            open_tickets=open_count,
            resolved_tickets=resolved,
            closed_tickets=closed,
            pending_tickets=pending,
            avg_resolution_hours=round(float(avg_resolution), 2),
            avg_first_response_hours=round(float(avg_first_response), 2),
            sla_attainment_pct=round(sla_pct, 1),
            csat_score=csat_score,
            period_days=filters.days,
        )

    # =========================================================================
    # VOLUME TRENDS
    # =========================================================================

    def get_volume_trend(
        self,
        filters: Optional[AnalyticsFilters] = None,
        granularity: str = "month",  # day, week, month
    ) -> VolumeTrend:
        """Get ticket volume trend over time."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        if granularity == "day":
            group_by = [
                extract("year", Ticket.created_at),
                extract("month", Ticket.created_at),
                extract("day", Ticket.created_at),
            ]
        elif granularity == "week":
            group_by = [
                extract("year", Ticket.created_at),
                extract("week", Ticket.created_at),
            ]
        else:  # month
            group_by = [
                extract("year", Ticket.created_at),
                extract("month", Ticket.created_at),
            ]

        query = (
            self.db.query(
                extract("year", Ticket.created_at).label("year"),
                extract("month", Ticket.created_at).label("month"),
                extract("day", Ticket.created_at).label("day") if granularity == "day" else func.lit(None).label("day"),
                func.count(Ticket.id).label("total"),
                func.sum(
                    case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)
                ).label("resolved"),
                func.sum(
                    case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)
                ).label("closed"),
            )
            .filter(Ticket.created_at >= start_dt)
        )
        if end_dt:
            query = query.filter(Ticket.created_at <= end_dt)

        query = self._apply_filters(query, filters)
        results = query.group_by(*group_by).order_by(*group_by).all()

        data_points = []
        total_opened = 0
        peak_volume = 0
        peak_day = None

        for row in results:
            year = int(row.year)
            month = int(row.month)
            day = int(row.day) if row.day else None

            if granularity == "day" and day:
                period = f"{year}-{month:02d}-{day:02d}"
            else:
                period = f"{year}-{month:02d}"

            point = VolumeDataPoint(
                period=period,
                year=year,
                month=month,
                day=day,
                total=row.total,
                opened=row.total,
                resolved=row.resolved or 0,
                closed=row.closed or 0,
            )
            data_points.append(point)
            total_opened += row.total

            if row.total > peak_volume:
                peak_volume = row.total
                peak_day = period

        total_resolved = sum(p.resolved + p.closed for p in data_points)
        days_in_range = (end_dt - start_dt).days if end_dt else filters.days
        avg_daily = total_opened / max(days_in_range, 1)

        return VolumeTrend(
            data=data_points,
            total_opened=total_opened,
            total_resolved=total_resolved,
            avg_daily_volume=round(avg_daily, 2),
            peak_day=peak_day,
            peak_volume=peak_volume,
        )

    # =========================================================================
    # RESOLUTION & RESPONSE TIME
    # =========================================================================

    def get_resolution_stats(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> ResolutionTimeStats:
        """Get detailed resolution time statistics."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600

        query = (
            self.db.query(resolution_hours.label("hours"))
            .filter(
                Ticket.resolution_date.isnot(None),
                Ticket.opening_date.isnot(None),
                Ticket.resolution_date >= start_dt,
            )
        )
        if end_dt:
            query = query.filter(Ticket.resolution_date <= end_dt)

        query = self._apply_filters(query, filters)
        hours_list = [r.hours for r in query.all() if r.hours is not None and r.hours >= 0]

        if not hours_list:
            return ResolutionTimeStats(
                avg_hours=0, median_hours=0, p90_hours=0, p95_hours=0,
                min_hours=0, max_hours=0, sample_size=0
            )

        hours_list.sort()
        n = len(hours_list)

        return ResolutionTimeStats(
            avg_hours=round(sum(hours_list) / n, 2),
            median_hours=round(hours_list[n // 2], 2),
            p90_hours=round(hours_list[int(n * 0.9)], 2),
            p95_hours=round(hours_list[int(n * 0.95)], 2),
            min_hours=round(min(hours_list), 2),
            max_hours=round(max(hours_list), 2),
            sample_size=n,
        )

    def get_first_response_stats(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> FirstResponseStats:
        """Get first response time statistics."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        response_hours = func.extract(
            "epoch", Ticket.first_responded_on - Ticket.created_at
        ) / 3600

        query = (
            self.db.query(
                response_hours.label("hours"),
                Ticket.response_by,
                Ticket.first_responded_on,
            )
            .filter(
                Ticket.first_responded_on.isnot(None),
                Ticket.created_at >= start_dt,
            )
        )
        if end_dt:
            query = query.filter(Ticket.created_at <= end_dt)

        query = self._apply_filters(query, filters)
        results = query.all()

        hours_list = [r.hours for r in results if r.hours is not None and r.hours >= 0]
        within_sla = sum(
            1 for r in results
            if r.response_by and r.first_responded_on and r.first_responded_on <= r.response_by
        )

        if not hours_list:
            return FirstResponseStats(
                avg_hours=0, median_hours=0, p90_hours=0, within_sla_pct=0, sample_size=0
            )

        hours_list.sort()
        n = len(hours_list)

        return FirstResponseStats(
            avg_hours=round(sum(hours_list) / n, 2),
            median_hours=round(hours_list[n // 2], 2),
            p90_hours=round(hours_list[int(n * 0.9)], 2),
            within_sla_pct=round(within_sla / n * 100, 1) if n > 0 else 0,
            sample_size=n,
        )

    # =========================================================================
    # AGENT PERFORMANCE
    # =========================================================================

    def get_agent_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
        limit: int = 50,
    ) -> List[AgentPerformance]:
        """Get performance metrics for all agents."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600
        first_response_hours = func.extract(
            "epoch", Ticket.first_responded_on - Ticket.created_at
        ) / 3600

        # Main agent stats query (Party-based after Agent → Party unification)
        # Agents are now Parties with PartyRole(role="support_agent")
        # Capacity is stored in PartyRole.metadata_->>'capacity'
        capacity_expr = func.coalesce(
            func.cast(PartyRole.metadata_["capacity"].astext, sqlalchemy.Integer),
            10
        )

        query = (
            self.db.query(
                Party.id.label("agent_id"),
                Party.name.label("agent_name"),
                func.count(UnifiedTicket.id).label("total_tickets"),
                func.sum(
                    case((UnifiedTicket.status.in_([s.value for s in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]), 1), else_=0)
                ).label("resolved_tickets"),
                func.avg(resolution_hours).label("avg_resolution_hours"),
                func.avg(first_response_hours).label("avg_first_response_hours"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_tracked"),
                func.sum(
                    case((UnifiedTicket.status.in_([s.value for s in OPEN_STATUSES]), 1), else_=0)
                ).label("current_open"),
                capacity_expr.label("capacity"),
            )
            .select_from(Party)
            .join(PartyRole, and_(
                PartyRole.party_id == Party.id,
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            ))
            .outerjoin(
                UnifiedTicket,
                and_(
                    UnifiedTicket.assigned_to_party_id == Party.id,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.created_at <= end_dt if end_dt else True,
                    UnifiedTicket.is_deleted == False,
                ),
            )
            .filter(Party.status == "active")
        )

        if filters.team_id:
            # Filter by team via TeamMember join table
            query = query.join(TeamMember, TeamMember.party_id == Party.id).filter(TeamMember.team_id == filters.team_id)
        if filters.agent_id:
            query = query.filter(Party.id == filters.agent_id)

        results = (
            query.group_by(Party.id, Party.name, capacity_expr)
            .order_by(func.count(UnifiedTicket.id).desc())
            .limit(limit)
            .all()
        )

        # Get CSAT scores per agent
        csat_by_agent = self._get_csat_by_agent(start_dt, end_dt)

        performances = []
        for row in results:
            total = row.total_tickets or 0
            resolved = row.resolved_tickets or 0
            sla_met = row.sla_met or 0
            sla_tracked = row.sla_tracked or 0
            capacity = row.capacity or 10
            current_open = row.current_open or 0

            csat_data = csat_by_agent.get(row.agent_id, {})

            performances.append(
                AgentPerformance(
                    agent_id=row.agent_id,
                    agent_name=row.agent_name or f"Agent {row.agent_id}",
                    team_id=None,  # Agents can belong to multiple teams
                    team_name=None,
                    total_tickets=total,
                    resolved_tickets=resolved,
                    resolution_rate=round(resolved / total * 100, 1) if total > 0 else 0,
                    avg_resolution_hours=round(float(row.avg_resolution_hours or 0), 2),
                    avg_first_response_hours=round(float(row.avg_first_response_hours or 0), 2),
                    sla_attainment_pct=round(sla_met / sla_tracked * 100, 1) if sla_tracked > 0 else 0,
                    csat_score=csat_data.get("score"),
                    csat_responses=csat_data.get("count", 0),
                    current_open=current_open,
                    capacity=capacity,
                    utilization_pct=round(current_open / capacity * 100, 1) if capacity > 0 else 0,
                )
            )

        return performances

    # =========================================================================
    # TEAM PERFORMANCE
    # =========================================================================

    def get_team_performance(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> List[TeamPerformance]:
        """Get performance metrics for all teams."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600
        first_response_hours = func.extract(
            "epoch", Ticket.first_responded_on - Ticket.created_at
        ) / 3600

        # After Agent → Party unification, agents are Parties with support_agent role
        capacity_expr = func.coalesce(
            func.cast(PartyRole.metadata_["capacity"].astext, sqlalchemy.Integer),
            10
        )

        query = (
            self.db.query(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                func.count(distinct(Party.id)).label("total_agents"),
                func.sum(
                    case((and_(Party.status == "active", PartyRole.status == "active"), 1), else_=0)
                ).label("active_agents"),
                func.count(UnifiedTicket.id).label("total_tickets"),
                func.sum(
                    case((UnifiedTicket.status.in_([s.value for s in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]), 1), else_=0)
                ).label("resolved_tickets"),
                func.avg(resolution_hours).label("avg_resolution_hours"),
                func.avg(first_response_hours).label("avg_first_response_hours"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_tracked"),
                func.sum(
                    case((UnifiedTicket.status.in_([s.value for s in OPEN_STATUSES]), 1), else_=0)
                ).label("current_open"),
                func.sum(capacity_expr).label("total_capacity"),
            )
            .select_from(Team)
            .outerjoin(TeamMember, TeamMember.team_id == Team.id)
            .outerjoin(Party, Party.id == TeamMember.party_id)
            .outerjoin(PartyRole, and_(
                PartyRole.party_id == Party.id,
                PartyRole.role == "support_agent",
                PartyRole.until.is_(None),
            ))
            .outerjoin(
                UnifiedTicket,
                and_(
                    UnifiedTicket.assigned_to_party_id == Party.id,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.created_at <= end_dt if end_dt else True,
                    UnifiedTicket.is_deleted == False,
                ),
            )
            .filter(Team.is_active == True)
        )

        if filters.team_id:
            query = query.filter(Team.id == filters.team_id)

        results = (
            query.group_by(Team.id, Team.name)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        # Get CSAT and top performers per team
        csat_by_team = self._get_csat_by_team(start_dt, end_dt)
        top_performers = self._get_top_performers_by_team(start_dt, end_dt)

        performances = []
        for row in results:
            total = row.total_tickets or 0
            resolved = row.resolved_tickets or 0
            sla_met = row.sla_met or 0
            sla_tracked = row.sla_tracked or 0
            capacity = row.total_capacity or 0
            current_open = row.current_open or 0

            csat_data = csat_by_team.get(row.team_id, {})

            performances.append(
                TeamPerformance(
                    team_id=row.team_id,
                    team_name=row.team_name,
                    total_agents=row.total_agents or 0,
                    active_agents=row.active_agents or 0,
                    total_tickets=total,
                    resolved_tickets=resolved,
                    resolution_rate=round(resolved / total * 100, 1) if total > 0 else 0,
                    avg_resolution_hours=round(float(row.avg_resolution_hours or 0), 2),
                    avg_first_response_hours=round(float(row.avg_first_response_hours or 0), 2),
                    sla_attainment_pct=round(sla_met / sla_tracked * 100, 1) if sla_tracked > 0 else 0,
                    csat_score=csat_data.get("score"),
                    current_open=current_open,
                    total_capacity=capacity,
                    utilization_pct=round(current_open / capacity * 100, 1) if capacity > 0 else 0,
                    top_performers=top_performers.get(row.team_id, []),
                )
            )

        return performances

    # =========================================================================
    # CHANNEL & CATEGORY BREAKDOWN
    # =========================================================================

    def get_channel_breakdown(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> List[ChannelStats]:
        """Get statistics broken down by support channel."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600
        first_response_hours = func.extract(
            "epoch", Ticket.first_responded_on - Ticket.created_at
        ) / 3600

        query = (
            self.db.query(
                Ticket.channel,
                func.count(Ticket.id).label("total"),
                func.sum(
                    case((Ticket.status.in_(CLOSED_STATUSES), 1), else_=0)
                ).label("resolved"),
                func.avg(resolution_hours).label("avg_resolution"),
                func.avg(first_response_hours).label("avg_first_response"),
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.resolution_by.isnot(None),
                                Ticket.resolution_date.isnot(None),
                                Ticket.resolution_date <= Ticket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_met"),
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.resolution_by.isnot(None),
                                Ticket.resolution_date.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("sla_tracked"),
            )
            .filter(
                Ticket.created_at >= start_dt,
                Ticket.channel.isnot(None),
            )
        )
        if end_dt:
            query = query.filter(Ticket.created_at <= end_dt)

        query = self._apply_filters(query, filters)
        results = query.group_by(Ticket.channel).order_by(func.count(Ticket.id).desc()).all()

        grand_total = sum(r.total for r in results)

        return [
            ChannelStats(
                channel=row.channel or "unknown",
                total_tickets=row.total,
                resolved_tickets=row.resolved or 0,
                resolution_rate=round((row.resolved or 0) / row.total * 100, 1) if row.total > 0 else 0,
                avg_resolution_hours=round(float(row.avg_resolution or 0), 2),
                avg_first_response_hours=round(float(row.avg_first_response or 0), 2),
                sla_attainment_pct=round((row.sla_met or 0) / (row.sla_tracked or 1) * 100, 1),
                pct_of_total=round(row.total / grand_total * 100, 1) if grand_total > 0 else 0,
            )
            for row in results
        ]

    def get_category_breakdown(
        self,
        filters: Optional[AnalyticsFilters] = None,
        category_field: str = "ticket_type",  # ticket_type, issue_type, priority
    ) -> List[CategoryStats]:
        """Get statistics broken down by category."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Map field name to column
        field_map = {
            "ticket_type": Ticket.ticket_type,
            "issue_type": Ticket.issue_type,
            "priority": Ticket.priority,
        }
        category_col = field_map.get(category_field, Ticket.ticket_type)

        resolution_hours = func.extract(
            "epoch", Ticket.resolution_date - Ticket.opening_date
        ) / 3600

        query = (
            self.db.query(
                category_col.label("category"),
                func.count(Ticket.id).label("total"),
                func.sum(
                    case((Ticket.status.in_(CLOSED_STATUSES), 1), else_=0)
                ).label("resolved"),
                func.avg(resolution_hours).label("avg_resolution"),
            )
            .filter(
                Ticket.created_at >= start_dt,
                category_col.isnot(None),
            )
        )
        if end_dt:
            query = query.filter(Ticket.created_at <= end_dt)

        query = self._apply_filters(query, filters)
        results = query.group_by(category_col).order_by(func.count(Ticket.id).desc()).all()

        grand_total = sum(r.total for r in results)

        return [
            CategoryStats(
                category=str(row.category.value if hasattr(row.category, "value") else row.category),
                category_type=category_field,
                total_tickets=row.total,
                resolved_tickets=row.resolved or 0,
                resolution_rate=round((row.resolved or 0) / row.total * 100, 1) if row.total > 0 else 0,
                avg_resolution_hours=round(float(row.avg_resolution or 0), 2),
                pct_of_total=round(row.total / grand_total * 100, 1) if grand_total > 0 else 0,
            )
            for row in results
        ]

    # =========================================================================
    # TAG ANALYTICS
    # =========================================================================

    def get_tag_breakdown(
        self,
        filters: Optional[AnalyticsFilters] = None,
        limit: int = 10,
    ) -> List[TagStats]:
        """Get tag usage breakdown with growth indicators.

        Returns top tags by ticket count with comparison to prior period.

        Args:
            filters: Date range and other filters.
            limit: Maximum tags to return.

        Returns:
            List of TagStats with usage counts and growth percentages.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Calculate prior period for growth comparison
        period_days = filters.days or 30
        prior_start = start_dt - timedelta(days=period_days)
        prior_end = start_dt

        # Get all active tags
        tags = (
            self.db.query(TicketTag)
            .filter(TicketTag.is_active == True)
            .order_by(TicketTag.usage_count.desc())
            .limit(limit * 2)  # Get more to ensure we have enough after filtering
            .all()
        )

        if not tags:
            return []

        # Count current period usage per tag
        current_counts: Dict[str, int] = {}
        prior_counts: Dict[str, int] = {}

        for tag in tags:
            # Current period count
            current_count = (
                self.db.query(func.count(UnifiedTicket.id))
                .filter(
                    UnifiedTicket.is_deleted == False,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.tags.contains([tag.name]),
                )
            )
            if end_dt:
                current_count = current_count.filter(UnifiedTicket.created_at <= end_dt)
            current_counts[tag.name] = current_count.scalar() or 0

            # Prior period count
            prior_count = (
                self.db.query(func.count(UnifiedTicket.id))
                .filter(
                    UnifiedTicket.is_deleted == False,
                    UnifiedTicket.created_at >= prior_start,
                    UnifiedTicket.created_at < prior_end,
                    UnifiedTicket.tags.contains([tag.name]),
                )
                .scalar() or 0
            )
            prior_counts[tag.name] = prior_count

        # Calculate total tickets in period for percentage
        total_tickets = (
            self.db.query(func.count(UnifiedTicket.id))
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
            )
        )
        if end_dt:
            total_tickets = total_tickets.filter(UnifiedTicket.created_at <= end_dt)
        total_tickets = total_tickets.scalar() or 1  # Avoid division by zero

        # Build results sorted by current count
        results = []
        for tag in tags:
            current = current_counts.get(tag.name, 0)
            prior = prior_counts.get(tag.name, 0)

            # Calculate growth percentage
            if prior > 0:
                growth_pct = round((current - prior) / prior * 100, 1)
            elif current > 0:
                growth_pct = 100.0  # New tag with usage
            else:
                growth_pct = 0.0

            results.append(TagStats(
                tag_id=tag.id,
                tag_name=tag.name,
                color=tag.color or "#6B7280",  # Default gray
                ticket_count=current,
                pct_of_total=round(current / total_tickets * 100, 1) if total_tickets > 0 else 0,
                growth_pct=growth_pct,
                prior_period_count=prior,
            ))

        # Sort by ticket count descending and limit
        results.sort(key=lambda x: x.ticket_count, reverse=True)
        return results[:limit]

    def get_tag_trends(
        self,
        filters: Optional[AnalyticsFilters] = None,
        top_n: int = 5,
    ) -> List[TagTrend]:
        """Get daily tag usage trends for top tags.

        Returns daily counts for sparkline visualization.

        Args:
            filters: Date range filters.
            top_n: Number of top tags to return trends for.

        Returns:
            List of TagTrend with daily counts.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Get top tags first
        top_tags = self.get_tag_breakdown(filters, limit=top_n)
        if not top_tags:
            return []

        results = []
        for tag_stat in top_tags:
            # Get daily counts for this tag
            daily_query = (
                self.db.query(
                    func.date(UnifiedTicket.created_at).label("date"),
                    func.count(UnifiedTicket.id).label("count"),
                )
                .filter(
                    UnifiedTicket.is_deleted == False,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.tags.contains([tag_stat.tag_name]),
                )
            )
            if end_dt:
                daily_query = daily_query.filter(UnifiedTicket.created_at <= end_dt)

            daily_data = (
                daily_query
                .group_by(func.date(UnifiedTicket.created_at))
                .order_by(func.date(UnifiedTicket.created_at))
                .all()
            )

            daily_counts = [
                {"date": str(row.date), "count": row.count}
                for row in daily_data
            ]

            # Get tag details
            tag = self.db.query(TicketTag).filter(TicketTag.id == tag_stat.tag_id).first()

            results.append(TagTrend(
                tag_id=tag_stat.tag_id,
                tag_name=tag_stat.tag_name,
                color=tag.color if tag else "#6B7280",
                daily_counts=daily_counts,
            ))

        return results

    # =========================================================================
    # SLA PERFORMANCE
    # =========================================================================

    def get_sla_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
        granularity: str = "month",
    ) -> List[SLAPerformance]:
        """Get SLA performance trend over time."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        query = (
            self.db.query(
                extract("year", Ticket.resolution_date).label("year"),
                extract("month", Ticket.resolution_date).label("month"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.response_by.isnot(None),
                                Ticket.first_responded_on.isnot(None),
                                Ticket.first_responded_on <= Ticket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.response_by.isnot(None),
                                Ticket.first_responded_on.isnot(None),
                                Ticket.first_responded_on > Ticket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.resolution_by.isnot(None),
                                Ticket.resolution_date.isnot(None),
                                Ticket.resolution_date <= Ticket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                Ticket.resolution_by.isnot(None),
                                Ticket.resolution_date.isnot(None),
                                Ticket.resolution_date > Ticket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
                func.count(Ticket.id).label("total"),
            )
            .filter(
                Ticket.resolution_date.isnot(None),
                Ticket.resolution_date >= start_dt,
            )
        )
        if end_dt:
            query = query.filter(Ticket.resolution_date <= end_dt)

        query = self._apply_filters(query, filters)
        results = (
            query.group_by(
                extract("year", Ticket.resolution_date),
                extract("month", Ticket.resolution_date),
            )
            .order_by(
                extract("year", Ticket.resolution_date),
                extract("month", Ticket.resolution_date),
            )
            .all()
        )

        return [
            SLAPerformance(
                period=f"{int(row.year)}-{int(row.month):02d}",
                response_met=row.response_met or 0,
                response_breached=row.response_breached or 0,
                response_attainment_pct=round(
                    (row.response_met or 0) / max((row.response_met or 0) + (row.response_breached or 0), 1) * 100, 1
                ),
                resolution_met=row.resolution_met or 0,
                resolution_breached=row.resolution_breached or 0,
                resolution_attainment_pct=round(
                    (row.resolution_met or 0) / max((row.resolution_met or 0) + (row.resolution_breached or 0), 1) * 100, 1
                ),
                total_tracked=row.total,
            )
            for row in results
        ]

    def get_sla_analytics_summary(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> SLAAnalyticsSummary:
        """Get overall SLA analytics summary stats.

        Provides key metrics for the SLA dashboard header cards.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Query tickets with SLA tracking
        query = (
            self.db.query(
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at > UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at > UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
                func.count(UnifiedTicket.id).label("total"),
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
            )
        )
        if end_dt:
            query = query.filter(UnifiedTicket.created_at <= end_dt)

        row = query.first()

        response_met = row.response_met or 0
        response_breached = row.response_breached or 0
        resolution_met = row.resolution_met or 0
        resolution_breached = row.resolution_breached or 0

        response_total = response_met + response_breached
        resolution_total = resolution_met + resolution_breached
        overall_met = response_met + resolution_met
        overall_total = response_total + resolution_total

        return SLAAnalyticsSummary(
            overall_attainment_pct=round(overall_met / max(overall_total, 1) * 100, 1),
            response_attainment_pct=round(response_met / max(response_total, 1) * 100, 1),
            resolution_attainment_pct=round(resolution_met / max(resolution_total, 1) * 100, 1),
            total_breaches=response_breached + resolution_breached,
            response_breaches=response_breached,
            resolution_breaches=resolution_breached,
            total_tracked=overall_total,
            period_days=filters.days,
        )

    def get_sla_attainment_by_agent(
        self,
        filters: Optional[AnalyticsFilters] = None,
        limit: int = 50,
    ) -> List[AgentSLAStats]:
        """Get SLA attainment broken down by agent.

        Returns per-agent metrics including response/resolution attainment.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Calculate response and resolution time expressions
        response_hours = func.extract(
            "epoch", UnifiedTicket.first_responded_at - UnifiedTicket.created_at
        ) / 3600
        resolution_hours = func.extract(
            "epoch", UnifiedTicket.resolved_at - UnifiedTicket.created_at
        ) / 3600

        query = (
            self.db.query(
                Party.id.label("agent_id"),
                Party.name.label("agent_name"),
                func.count(UnifiedTicket.id).label("total_tickets"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at > UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at > UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
                func.avg(response_hours).label("avg_response_hours"),
                func.avg(resolution_hours).label("avg_resolution_hours"),
            )
            .select_from(Party)
            .join(PartyRole, and_(
                PartyRole.party_id == Party.id,
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            ))
            .outerjoin(
                UnifiedTicket,
                and_(
                    UnifiedTicket.assigned_to_party_id == Party.id,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.created_at <= end_dt if end_dt else True,
                    UnifiedTicket.is_deleted == False,
                ),
            )
            .filter(Party.status == "active")
        )

        if filters.team_id:
            query = query.join(TeamMember, TeamMember.party_id == Party.id).filter(
                TeamMember.team_id == filters.team_id
            )

        results = (
            query.group_by(Party.id, Party.name)
            .order_by(func.count(UnifiedTicket.id).desc())
            .limit(limit)
            .all()
        )

        # Get team names for agents
        agent_teams = self._get_agent_teams([r.agent_id for r in results])

        stats = []
        for row in results:
            total = row.total_tickets or 0
            response_met = row.response_met or 0
            response_breached = row.response_breached or 0
            resolution_met = row.resolution_met or 0
            resolution_breached = row.resolution_breached or 0

            response_total = response_met + response_breached
            resolution_total = resolution_met + resolution_breached
            overall_met = response_met + resolution_met
            overall_total = response_total + resolution_total

            stats.append(AgentSLAStats(
                agent_id=row.agent_id,
                agent_name=row.agent_name or f"Agent {row.agent_id}",
                team_name=agent_teams.get(row.agent_id),
                total_tickets=total,
                response_met=response_met,
                response_breached=response_breached,
                response_attainment_pct=round(response_met / max(response_total, 1) * 100, 1),
                resolution_met=resolution_met,
                resolution_breached=resolution_breached,
                resolution_attainment_pct=round(resolution_met / max(resolution_total, 1) * 100, 1),
                overall_attainment_pct=round(overall_met / max(overall_total, 1) * 100, 1),
                avg_response_hours=round(float(row.avg_response_hours), 2) if row.avg_response_hours else None,
                avg_resolution_hours=round(float(row.avg_resolution_hours), 2) if row.avg_resolution_hours else None,
            ))

        return stats

    def get_sla_attainment_by_team(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[TeamSLAStats]:
        """Get SLA attainment broken down by team.

        Returns per-team metrics including response/resolution attainment.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        query = (
            self.db.query(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                func.count(distinct(UnifiedTicket.id)).label("total_tickets"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at > UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at > UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
            )
            .select_from(Team)
            .outerjoin(TeamMember, TeamMember.team_id == Team.id)
            .outerjoin(Party, Party.id == TeamMember.party_id)
            .outerjoin(
                UnifiedTicket,
                and_(
                    UnifiedTicket.assigned_to_party_id == Party.id,
                    UnifiedTicket.created_at >= start_dt,
                    UnifiedTicket.created_at <= end_dt if end_dt else True,
                    UnifiedTicket.is_deleted == False,
                ),
            )
            .filter(Team.is_active == True)
        )

        if filters.team_id:
            query = query.filter(Team.id == filters.team_id)

        results = (
            query.group_by(Team.id, Team.name)
            .order_by(func.count(distinct(UnifiedTicket.id)).desc())
            .all()
        )

        stats = []
        for row in results:
            total = row.total_tickets or 0
            response_met = row.response_met or 0
            response_breached = row.response_breached or 0
            resolution_met = row.resolution_met or 0
            resolution_breached = row.resolution_breached or 0

            response_total = response_met + response_breached
            resolution_total = resolution_met + resolution_breached
            overall_met = response_met + resolution_met
            overall_total = response_total + resolution_total

            stats.append(TeamSLAStats(
                team_id=row.team_id,
                team_name=row.team_name,
                total_tickets=total,
                response_met=response_met,
                response_breached=response_breached,
                response_attainment_pct=round(response_met / max(response_total, 1) * 100, 1),
                resolution_met=resolution_met,
                resolution_breached=resolution_breached,
                resolution_attainment_pct=round(resolution_met / max(resolution_total, 1) * 100, 1),
                overall_attainment_pct=round(overall_met / max(overall_total, 1) * 100, 1),
            ))

        return stats

    def get_sla_near_misses(
        self,
        filters: Optional[AnalyticsFilters] = None,
        threshold_pct: float = 0.9,
        limit: int = 20,
    ) -> List[NearMissTicket]:
        """Get tickets that came close to breaching SLA.

        Near misses are tickets where actual time was within threshold_pct
        of the SLA target (e.g., 0.9 = within 90% of target).
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        results = []

        # Check response SLA near misses
        response_query = (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
                UnifiedTicket.response_by.isnot(None),
                UnifiedTicket.first_responded_at.isnot(None),
                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,  # Met SLA
            )
        )
        if end_dt:
            response_query = response_query.filter(UnifiedTicket.created_at <= end_dt)

        for ticket in response_query.all():
            # Calculate what % of the SLA target was used
            target_duration = (ticket.response_by - ticket.created_at).total_seconds()
            actual_duration = (ticket.first_responded_at - ticket.created_at).total_seconds()

            if target_duration > 0:
                margin_pct = actual_duration / target_duration
                if margin_pct >= threshold_pct:
                    results.append(NearMissTicket(
                        ticket_id=ticket.id,
                        ticket_number=ticket.ticket_number,
                        subject=ticket.subject,
                        sla_type="response",
                        target_time=ticket.response_by,
                        actual_time=ticket.first_responded_at,
                        margin_pct=round(margin_pct, 3),
                    ))

        # Check resolution SLA near misses
        resolution_query = (
            self.db.query(UnifiedTicket)
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
                UnifiedTicket.resolution_by.isnot(None),
                UnifiedTicket.resolved_at.isnot(None),
                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,  # Met SLA
            )
        )
        if end_dt:
            resolution_query = resolution_query.filter(UnifiedTicket.created_at <= end_dt)

        for ticket in resolution_query.all():
            target_duration = (ticket.resolution_by - ticket.created_at).total_seconds()
            actual_duration = (ticket.resolved_at - ticket.created_at).total_seconds()

            if target_duration > 0:
                margin_pct = actual_duration / target_duration
                if margin_pct >= threshold_pct:
                    results.append(NearMissTicket(
                        ticket_id=ticket.id,
                        ticket_number=ticket.ticket_number,
                        subject=ticket.subject,
                        sla_type="resolution",
                        target_time=ticket.resolution_by,
                        actual_time=ticket.resolved_at,
                        margin_pct=round(margin_pct, 3),
                    ))

        # Sort by margin (closest to breach first) and limit
        results.sort(key=lambda x: x.margin_pct, reverse=True)
        return results[:limit]

    def get_sla_trends(
        self,
        filters: Optional[AnalyticsFilters] = None,
        periods: int = 6,
    ) -> List[SLATrendPoint]:
        """Get SLA attainment trend over time periods.

        Returns monthly data points for trend visualization.
        """
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        query = (
            self.db.query(
                extract("year", UnifiedTicket.created_at).label("year"),
                extract("month", UnifiedTicket.created_at).label("month"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_total"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_total"),
                func.count(UnifiedTicket.id).label("total_tickets"),
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
            )
        )
        if end_dt:
            query = query.filter(UnifiedTicket.created_at <= end_dt)

        results = (
            query.group_by(
                extract("year", UnifiedTicket.created_at),
                extract("month", UnifiedTicket.created_at),
            )
            .order_by(
                extract("year", UnifiedTicket.created_at).desc(),
                extract("month", UnifiedTicket.created_at).desc(),
            )
            .limit(periods)
            .all()
        )

        # Reverse to chronological order
        results = list(reversed(results))

        return [
            SLATrendPoint(
                period=f"{int(row.year)}-{int(row.month):02d}",
                response_attainment_pct=round(
                    (row.response_met or 0) / max(row.response_total or 1, 1) * 100, 1
                ),
                resolution_attainment_pct=round(
                    (row.resolution_met or 0) / max(row.resolution_total or 1, 1) * 100, 1
                ),
                overall_attainment_pct=round(
                    ((row.response_met or 0) + (row.resolution_met or 0)) /
                    max((row.response_total or 0) + (row.resolution_total or 0), 1) * 100, 1
                ),
                total_tickets=row.total_tickets or 0,
            )
            for row in results
        ]

    def get_sla_by_category(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[CategorySLAStats]:
        """Get SLA performance broken down by ticket category/type."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        query = (
            self.db.query(
                UnifiedTicket.ticket_type.label("category"),
                func.count(UnifiedTicket.id).label("total_tickets"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at > UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at > UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
                UnifiedTicket.ticket_type.isnot(None),
            )
        )
        if end_dt:
            query = query.filter(UnifiedTicket.created_at <= end_dt)

        results = (
            query.group_by(UnifiedTicket.ticket_type)
            .order_by(func.count(UnifiedTicket.id).desc())
            .all()
        )

        stats = []
        for row in results:
            response_met = row.response_met or 0
            response_breached = row.response_breached or 0
            resolution_met = row.resolution_met or 0
            resolution_breached = row.resolution_breached or 0

            response_total = response_met + response_breached
            resolution_total = resolution_met + resolution_breached

            category_name = row.category.value if hasattr(row.category, "value") else str(row.category)

            stats.append(CategorySLAStats(
                category=category_name,
                total_tickets=row.total_tickets or 0,
                response_attainment_pct=round(response_met / max(response_total, 1) * 100, 1),
                resolution_attainment_pct=round(resolution_met / max(resolution_total, 1) * 100, 1),
                total_breaches=response_breached + resolution_breached,
            ))

        return stats

    def get_sla_by_priority(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[PrioritySLAStats]:
        """Get SLA performance broken down by priority level."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        query = (
            self.db.query(
                UnifiedTicket.priority.label("priority"),
                func.count(UnifiedTicket.id).label("total_tickets"),
                # Response SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at <= UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.response_by.isnot(None),
                                UnifiedTicket.first_responded_at.isnot(None),
                                UnifiedTicket.first_responded_at > UnifiedTicket.response_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("response_breached"),
                # Resolution SLA
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at <= UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_met"),
                func.sum(
                    case(
                        (
                            and_(
                                UnifiedTicket.resolution_by.isnot(None),
                                UnifiedTicket.resolved_at.isnot(None),
                                UnifiedTicket.resolved_at > UnifiedTicket.resolution_by,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolution_breached"),
            )
            .filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.created_at >= start_dt,
                UnifiedTicket.priority.isnot(None),
            )
        )
        if end_dt:
            query = query.filter(UnifiedTicket.created_at <= end_dt)

        results = (
            query.group_by(UnifiedTicket.priority)
            .order_by(func.count(UnifiedTicket.id).desc())
            .all()
        )

        # Priority order for sorting
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        stats = []
        for row in results:
            response_met = row.response_met or 0
            response_breached = row.response_breached or 0
            resolution_met = row.resolution_met or 0
            resolution_breached = row.resolution_breached or 0

            response_total = response_met + response_breached
            resolution_total = resolution_met + resolution_breached

            priority_name = row.priority.value if hasattr(row.priority, "value") else str(row.priority)

            stats.append(PrioritySLAStats(
                priority=priority_name,
                total_tickets=row.total_tickets or 0,
                response_attainment_pct=round(response_met / max(response_total, 1) * 100, 1),
                resolution_attainment_pct=round(resolution_met / max(resolution_total, 1) * 100, 1),
                total_breaches=response_breached + resolution_breached,
            ))

        # Sort by priority order
        stats.sort(key=lambda x: priority_order.get(x.priority.lower(), 99))
        return stats

    def _get_agent_teams(self, agent_ids: List[int]) -> Dict[int, str]:
        """Get team names for a list of agent party IDs."""
        if not agent_ids:
            return {}

        try:
            results = (
                self.db.query(TeamMember.party_id, Team.name)
                .join(Team, Team.id == TeamMember.team_id)
                .filter(
                    TeamMember.party_id.in_(agent_ids),
                    TeamMember.is_active == True,
                )
                .all()
            )
            return {r.party_id: r.name for r in results}
        except Exception:
            return {}

    # =========================================================================
    # BACKLOG AGING
    # =========================================================================

    def get_backlog_aging(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> List[BacklogAging]:
        """Analyze open ticket backlog by age."""
        filters = filters or AnalyticsFilters()
        now = datetime.now(timezone.utc)

        # Define age buckets
        buckets = [
            ("0-24h", timedelta(hours=24)),
            ("1-3d", timedelta(days=3)),
            ("3-7d", timedelta(days=7)),
            ("1-2w", timedelta(weeks=2)),
            ("2-4w", timedelta(weeks=4)),
            (">1m", timedelta(days=365)),  # catch-all
        ]

        query = self.db.query(Ticket).filter(Ticket.status.in_(OPEN_STATUSES))
        query = self._apply_filters(query, filters)
        open_tickets = query.all()

        total_backlog = len(open_tickets)
        aging_data = []
        prev_threshold = timedelta(0)

        for bucket_name, threshold in buckets:
            bucket_tickets = [
                t for t in open_tickets
                if prev_threshold < (now - (t.created_at or now)) <= threshold
            ]

            count = len(bucket_tickets)
            priorities = [
                PRIORITY_VALUES.get(
                    t.priority.value if hasattr(t.priority, "value") else str(t.priority), 2
                )
                for t in bucket_tickets
            ]
            avg_priority = sum(priorities) / len(priorities) if priorities else 0

            # SLA at risk: tickets with resolution_by in the past or within 24h
            sla_at_risk = sum(
                1 for t in bucket_tickets
                if t.resolution_by and t.resolution_by <= now + timedelta(hours=24)
            )

            aging_data.append(
                BacklogAging(
                    age_bucket=bucket_name,
                    count=count,
                    pct_of_backlog=round(count / total_backlog * 100, 1) if total_backlog > 0 else 0,
                    avg_priority=round(avg_priority, 2),
                    sla_at_risk=sla_at_risk,
                )
            )
            prev_threshold = threshold

        return aging_data

    # =========================================================================
    # REOPEN ANALYSIS
    # =========================================================================

    def get_reopen_analysis(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> ReopenAnalysis:
        """Analyze ticket reopens and rework."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Count tickets with reopens
        query = (
            self.db.query(
                Ticket.id,
                Ticket.reopen_count,
                Ticket.assigned_to_id,
                Ticket.ticket_type,
            )
            .filter(
                Ticket.created_at >= start_dt,
                Ticket.reopen_count.isnot(None),
                Ticket.reopen_count > 0,
            )
        )
        if end_dt:
            query = query.filter(Ticket.created_at <= end_dt)

        query = self._apply_filters(query, filters)
        reopened_tickets = query.all()

        total_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.created_at >= start_dt)
            .scalar() or 0
        )

        total_reopened = len(reopened_tickets)
        total_reopens = sum(t.reopen_count or 0 for t in reopened_tickets)
        avg_reopens = total_reopens / total_reopened if total_reopened > 0 else 0

        # By agent (Party-based after Agent → Party unification)
        # Note: For legacy Ticket model, assigned_to_id points to employees
        # For UnifiedTicket, use assigned_to_party_id
        by_agent_dict: Dict[int, int] = defaultdict(int)
        for t in reopened_tickets:
            # Try UnifiedTicket's party-based assignment first
            agent_id = getattr(t, "assigned_to_party_id", None) or getattr(t, "assigned_to_id", None)
            if agent_id:
                by_agent_dict[agent_id] += 1

        # Get party names (agents are now Parties)
        party_ids = list(by_agent_dict.keys())
        parties = {
            p.id: p.name
            for p in self.db.query(Party.id, Party.name).filter(Party.id.in_(party_ids)).all()
        } if party_ids else {}

        by_agent = [
            {"agent_id": pid, "agent_name": parties.get(pid, f"Agent {pid}"), "reopen_count": count}
            for pid, count in sorted(by_agent_dict.items(), key=lambda x: -x[1])[:10]
        ]

        # By category
        by_category_dict: Dict[str, int] = defaultdict(int)
        for t in reopened_tickets:
            cat = t.ticket_type.value if hasattr(t.ticket_type, "value") else str(t.ticket_type or "unknown")
            by_category_dict[cat] += 1

        by_category = [
            {"category": cat, "reopen_count": count}
            for cat, count in sorted(by_category_dict.items(), key=lambda x: -x[1])[:10]
        ]

        return ReopenAnalysis(
            total_reopened=total_reopened,
            reopen_rate=round(total_reopened / total_tickets * 100, 2) if total_tickets > 0 else 0,
            avg_reopens_per_ticket=round(avg_reopens, 2),
            top_reopen_reasons=[],  # Would require activity log analysis
            by_agent=by_agent,
            by_category=by_category,
        )

    # =========================================================================
    # PATTERN INSIGHTS
    # =========================================================================

    def get_pattern_insights(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> PatternInsights:
        """Analyze support patterns - peak times, busy periods, etc."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        base_filter = [Ticket.created_at >= start_dt]
        if end_dt:
            base_filter.append(Ticket.created_at <= end_dt)

        # By hour
        by_hour = (
            self.db.query(
                extract("hour", Ticket.created_at).label("hour"),
                func.count(Ticket.id).label("count"),
            )
            .filter(*base_filter)
            .group_by(extract("hour", Ticket.created_at))
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        # By day of week
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        by_dow = (
            self.db.query(
                extract("dow", Ticket.created_at).label("dow"),
                func.count(Ticket.id).label("count"),
            )
            .filter(*base_filter)
            .group_by(extract("dow", Ticket.created_at))
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        # By region
        by_region = (
            self.db.query(
                Ticket.region,
                func.count(Ticket.id).label("count"),
            )
            .filter(*base_filter, Ticket.region.isnot(None))
            .group_by(Ticket.region)
            .order_by(func.count(Ticket.id).desc())
            .limit(10)
            .all()
        )

        peak_hours = [{"hour": int(h.hour), "count": h.count} for h in by_hour[:5]]
        peak_days = [
            {"day": day_names[int(d.dow)], "day_num": int(d.dow), "count": d.count}
            for d in by_dow
        ]

        # Determine busiest/quietest periods
        busiest = peak_hours[0] if peak_hours else {"hour": 0, "count": 0}
        quietest = min(by_hour, key=lambda x: x.count) if by_hour else None

        return PatternInsights(
            peak_hours=peak_hours,
            peak_days=peak_days,
            busiest_period=f"{busiest['hour']:02d}:00" if busiest else "N/A",
            quietest_period=f"{int(quietest.hour):02d}:00" if quietest else "N/A",
            by_region=[{"region": r.region, "count": r.count} for r in by_region],
            seasonal_factors=[],  # Would require year-over-year data
        )

    # =========================================================================
    # AUTOMATION EFFECTIVENESS
    # =========================================================================

    def get_automation_effectiveness(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> AutomationEffectiveness:
        """Analyze automation rule effectiveness."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Get automation logs
        log_query = self.db.query(AutomationLog).filter(
            AutomationLog.created_at >= start_dt
        )
        if end_dt:
            log_query = log_query.filter(AutomationLog.created_at <= end_dt)

        logs = log_query.all()

        total = len(logs)
        successful = sum(1 for log in logs if log.success)

        # Count by action type (would need to analyze log data)
        auto_assigned = sum(
            1 for log in logs
            if log.success and log.actions_executed and "assign" in str(log.actions_executed).lower()
        )
        auto_categorized = sum(
            1 for log in logs
            if log.success and log.actions_executed and "categor" in str(log.actions_executed).lower()
        )
        auto_responded = sum(
            1 for log in logs
            if log.success and log.actions_executed and "reply" in str(log.actions_executed).lower()
        )

        # Top rules
        rule_counts: Dict[int, Tuple[str, int]] = {}
        for log in logs:
            if log.rule_id:
                if log.rule_id not in rule_counts:
                    rule_name = log.rule.name if log.rule else f"Rule {log.rule_id}"
                    rule_counts[log.rule_id] = (rule_name, 0)
                rule_counts[log.rule_id] = (rule_counts[log.rule_id][0], rule_counts[log.rule_id][1] + 1)

        top_rules = [
            {"rule_id": rid, "rule_name": name, "execution_count": count}
            for rid, (name, count) in sorted(rule_counts.items(), key=lambda x: -x[1][1])[:10]
        ]

        return AutomationEffectiveness(
            total_executions=total,
            successful_executions=successful,
            success_rate=round(successful / total * 100, 1) if total > 0 else 0,
            tickets_auto_assigned=auto_assigned,
            tickets_auto_categorized=auto_categorized,
            tickets_auto_responded=auto_responded,
            avg_time_saved_hours=0.5,  # Estimated based on manual handling time
            top_rules=top_rules,
        )

    # =========================================================================
    # KB DEFLECTION
    # =========================================================================

    def get_kb_deflection(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> KBDeflection:
        """Analyze knowledge base article effectiveness and deflection."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        # Article views and feedback
        articles = (
            self.db.query(
                KBArticle.id,
                KBArticle.title,
                KBArticle.view_count,
                KBArticle.helpful_count,
                KBArticle.not_helpful_count,
            )
            .filter(KBArticle.is_published == True)
            .all()
        )

        total_views = sum(a.view_count or 0 for a in articles)
        helpful = sum(a.helpful_count or 0 for a in articles)
        not_helpful = sum(a.not_helpful_count or 0 for a in articles)
        total_votes = helpful + not_helpful

        # Estimate deflection (views that didn't result in tickets)
        # This is a rough estimate - would need session tracking for accuracy
        ticket_count = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.created_at >= start_dt)
            .scalar() or 0
        )
        estimated_deflections = max(0, total_views - ticket_count)

        # Top articles by helpfulness
        top_articles = [
            {
                "article_id": a.id,
                "title": a.title,
                "views": a.view_count or 0,
                "helpful": a.helpful_count or 0,
                "helpfulness_rate": round(
                    (a.helpful_count or 0) / max((a.helpful_count or 0) + (a.not_helpful_count or 0), 1) * 100, 1
                ),
            }
            for a in sorted(articles, key=lambda x: x.helpful_count or 0, reverse=True)[:10]
        ]

        return KBDeflection(
            total_article_views=total_views,
            helpful_votes=helpful,
            not_helpful_votes=not_helpful,
            helpfulness_rate=round(helpful / total_votes * 100, 1) if total_votes > 0 else 0,
            estimated_deflections=estimated_deflections,
            deflection_rate=round(estimated_deflections / max(total_views, 1) * 100, 1),
            top_articles=top_articles,
            search_no_results=0,  # Would need search log integration
        )

    # =========================================================================
    # END-TO-END REPORT
    # =========================================================================

    def generate_e2e_report(
        self, filters: Optional[AnalyticsFilters] = None
    ) -> E2EReport:
        """Generate a comprehensive end-to-end support report."""
        filters = filters or AnalyticsFilters()
        start_dt, end_dt = self._get_date_range(filters)

        period_str = f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d') if end_dt else 'now'}"

        return E2EReport(
            report_period=period_str,
            generated_at=datetime.now(timezone.utc),
            overview=self.get_overview(filters),
            volume_trend=self.get_volume_trend(filters),
            resolution_stats=self.get_resolution_stats(filters),
            first_response_stats=self.get_first_response_stats(filters),
            sla_performance=self.get_sla_performance(filters),
            agent_performance=self.get_agent_performance(filters),
            team_performance=self.get_team_performance(filters),
            channel_breakdown=self.get_channel_breakdown(filters),
            category_breakdown=self.get_category_breakdown(filters),
            backlog_aging=self.get_backlog_aging(filters),
            reopen_analysis=self.get_reopen_analysis(filters),
            patterns=self.get_pattern_insights(filters),
            automation=self.get_automation_effectiveness(filters),
            kb_deflection=self.get_kb_deflection(filters),
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_date_range(
        self, filters: AnalyticsFilters
    ) -> Tuple[datetime, Optional[datetime]]:
        """Calculate date range from filters."""
        end_dt = filters.end_date or datetime.now(timezone.utc)
        if filters.start_date:
            start_dt = filters.start_date
        else:
            start_dt = end_dt - timedelta(days=filters.days)
        return start_dt, end_dt

    def _apply_filters(self, query, filters: AnalyticsFilters):
        """Apply common filters to a query."""
        if filters.team_id:
            query = query.filter(Ticket.assigned_team == str(filters.team_id))
        if filters.agent_id:
            query = query.filter(Ticket.assigned_to_id == filters.agent_id)
        if filters.channel:
            query = query.filter(Ticket.channel == filters.channel)
        if filters.priority:
            query = query.filter(Ticket.priority == filters.priority)
        if filters.ticket_type:
            query = query.filter(Ticket.ticket_type == filters.ticket_type)
        return query

    def _get_avg_csat(
        self,
        start_dt: datetime,
        end_dt: Optional[datetime],
        filters: AnalyticsFilters,
    ) -> Optional[float]:
        """Get average CSAT score for the period."""
        try:
            query = self.db.query(func.avg(CSATResponse.rating)).filter(
                CSATResponse.created_at >= start_dt,
                CSATResponse.rating.isnot(None),
            )
            if end_dt:
                query = query.filter(CSATResponse.created_at <= end_dt)

            avg = query.scalar()
            return round(float(avg), 2) if avg else None
        except Exception:
            return None

    def _get_csat_by_agent(
        self, start_dt: datetime, end_dt: Optional[datetime]
    ) -> Dict[int, Dict[str, Any]]:
        """Get CSAT scores grouped by agent."""
        try:
            query = (
                self.db.query(
                    CSATResponse.agent_party_id,
                    func.avg(CSATResponse.rating).label("avg_rating"),
                    func.count(CSATResponse.id).label("count"),
                )
                .filter(
                    CSATResponse.created_at >= start_dt,
                    CSATResponse.agent_party_id.isnot(None),
                    CSATResponse.rating.isnot(None),
                )
                .group_by(CSATResponse.agent_party_id)
            )
            if end_dt:
                query = query.filter(CSATResponse.created_at <= end_dt)

            return {
                row.agent_id: {"score": round(float(row.avg_rating), 2), "count": row.count}
                for row in query.all()
            }
        except Exception:
            return {}

    def _get_csat_by_team(
        self, start_dt: datetime, end_dt: Optional[datetime]
    ) -> Dict[int, Dict[str, Any]]:
        """Get CSAT scores grouped by team.

        After Agent → Party unification, agents connect to teams through TeamMember.
        """
        try:
            query = (
                self.db.query(
                    TeamMember.team_id,
                    func.avg(CSATResponse.rating).label("avg_rating"),
                    func.count(CSATResponse.id).label("count"),
                )
                .join(Party, Party.id == CSATResponse.agent_party_id)
                .join(TeamMember, TeamMember.party_id == Party.id)
                .filter(
                    CSATResponse.created_at >= start_dt,
                    TeamMember.is_active == True,
                    CSATResponse.rating.isnot(None),
                )
                .group_by(TeamMember.team_id)
            )
            if end_dt:
                query = query.filter(CSATResponse.created_at <= end_dt)

            return {
                row.team_id: {"score": round(float(row.avg_rating), 2), "count": row.count}
                for row in query.all()
            }
        except Exception:
            return {}

    def _get_top_performers_by_team(
        self, start_dt: datetime, end_dt: Optional[datetime]
    ) -> Dict[int, List[str]]:
        """Get top performing agents per team.

        After Agent → Party unification, agents are Parties with support_agent role.
        """
        try:
            query = (
                self.db.query(
                    TeamMember.team_id,
                    Party.name,
                    func.count(UnifiedTicket.id).label("resolved_count"),
                )
                .join(Party, Party.id == TeamMember.party_id)
                .join(UnifiedTicket, UnifiedTicket.assigned_to_party_id == Party.id)
                .filter(
                    UnifiedTicket.status.in_([TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]),
                    UnifiedTicket.resolved_at >= start_dt,
                    TeamMember.is_active == True,
                    UnifiedTicket.is_deleted == False,
                )
                .group_by(TeamMember.team_id, Party.id, Party.name)
                .order_by(TeamMember.team_id, func.count(UnifiedTicket.id).desc())
            )
            if end_dt:
                query = query.filter(UnifiedTicket.resolved_at <= end_dt)

            result: Dict[int, List[str]] = defaultdict(list)
            for row in query.all():
                if len(result[row.team_id]) < 3:  # Top 3 per team
                    result[row.team_id].append(row.name)

            return dict(result)
        except Exception:
            return {}
