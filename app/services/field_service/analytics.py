"""Field Service Analytics service.

This service handles:
- Dashboard metrics
- Performance analytics
- Technician and team performance
- Cost analysis
- Utilization metrics
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderType,
    ServiceOrderItem,
    TimeEntry,
    FieldTeam,
    FieldTeamMember,
)
from app.models.employee import Employee

from .analytics_types import (
    AnalyticsFilters,
    DashboardMetrics,
    OrderTypeBreakdown,
    PerformanceMetrics,
    TechnicianPerformance,
    TeamPerformance,
    MonthlyTrend,
    CostAnalysis,
    UtilizationMetrics,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["FieldServiceAnalyticsService"]


class FieldServiceAnalyticsService:
    """Service for field service analytics.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for scoping if needed).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Dashboard Metrics
    # -------------------------------------------------------------------------

    def get_dashboard_metrics(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> DashboardMetrics:
        """Get dashboard summary metrics.

        Args:
            filters: Optional analytics filters

        Returns:
            DashboardMetrics with summary stats
        """
        if filters is None:
            filters = AnalyticsFilters()

        query = self.db.query(ServiceOrder)
        query = self._apply_filters(query, filters)

        # Get counts by status
        total_orders = query.count()
        completed_orders = query.filter(
            ServiceOrder.status == ServiceOrderStatus.COMPLETED
        ).count()
        cancelled_orders = query.filter(
            ServiceOrder.status == ServiceOrderStatus.CANCELLED
        ).count()
        pending_orders = query.filter(
            ServiceOrder.status.in_([
                ServiceOrderStatus.DRAFT,
                ServiceOrderStatus.SCHEDULED,
                ServiceOrderStatus.DISPATCHED,
                ServiceOrderStatus.EN_ROUTE,
                ServiceOrderStatus.ON_SITE,
                ServiceOrderStatus.IN_PROGRESS,
            ])
        ).count()

        # Completion rate
        completion_rate = 0.0
        if total_orders > 0:
            completion_rate = round((completed_orders / total_orders) * 100, 1)

        # Average completion time (for completed orders)
        avg_completion_time = 0.0
        completed_with_times = (
            query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED,
                ServiceOrder.actual_start_time.isnot(None),
                ServiceOrder.actual_end_time.isnot(None),
            )
            .all()
        )
        if completed_with_times:
            total_hours = sum(
                (o.actual_end_time - o.actual_start_time).total_seconds() / 3600
                for o in completed_with_times
            )
            avg_completion_time = round(total_hours / len(completed_with_times), 1)

        # Average customer rating
        rated_orders = query.filter(ServiceOrder.customer_rating.isnot(None)).all()
        avg_rating = 0.0
        if rated_orders:
            avg_rating = round(
                sum(o.customer_rating for o in rated_orders) / len(rated_orders), 1
            )

        # Revenue and cost
        completed_query = query.filter(ServiceOrder.status == ServiceOrderStatus.COMPLETED)
        total_revenue = Decimal("0")
        total_cost = Decimal("0")
        for order in completed_query.all():
            if order.total_amount:
                total_revenue += order.total_amount
            if order.total_cost:
                total_cost += order.total_cost

        profit_margin = 0.0
        if total_revenue > 0:
            profit_margin = round(
                float((total_revenue - total_cost) / total_revenue * 100), 1
            )

        return DashboardMetrics(
            total_orders=total_orders,
            completed_orders=completed_orders,
            pending_orders=pending_orders,
            cancelled_orders=cancelled_orders,
            completion_rate=completion_rate,
            avg_completion_time_hours=avg_completion_time,
            avg_customer_rating=avg_rating,
            total_revenue=total_revenue,
            total_cost=total_cost,
            profit_margin=profit_margin,
        )

    # -------------------------------------------------------------------------
    # Order Type Breakdown
    # -------------------------------------------------------------------------

    def get_order_type_breakdown(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[OrderTypeBreakdown]:
        """Get order breakdown by type.

        Args:
            filters: Optional analytics filters

        Returns:
            List of OrderTypeBreakdown
        """
        if filters is None:
            filters = AnalyticsFilters()

        query = self.db.query(ServiceOrder)
        query = self._apply_filters(query, filters)

        total = query.count()
        if total == 0:
            return []

        # Group by order type
        breakdown = []
        for order_type in ServiceOrderType:
            type_query = query.filter(ServiceOrder.order_type == order_type)
            count = type_query.count()
            if count == 0:
                continue

            # Calculate revenue for this type
            revenue = Decimal("0")
            for order in type_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED
            ).all():
                if order.total_amount:
                    revenue += order.total_amount

            breakdown.append(
                OrderTypeBreakdown(
                    order_type=order_type.value,
                    count=count,
                    percentage=round((count / total) * 100, 1),
                    revenue=revenue,
                )
            )

        # Sort by count descending
        breakdown.sort(key=lambda x: x.count, reverse=True)
        return breakdown

    # -------------------------------------------------------------------------
    # Performance Metrics
    # -------------------------------------------------------------------------

    def get_performance_metrics(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> PerformanceMetrics:
        """Get performance metrics.

        Args:
            filters: Optional analytics filters

        Returns:
            PerformanceMetrics
        """
        if filters is None:
            filters = AnalyticsFilters()

        query = self.db.query(ServiceOrder)
        query = self._apply_filters(query, filters)

        completed = query.filter(
            ServiceOrder.status == ServiceOrderStatus.COMPLETED
        ).all()

        if not completed:
            return PerformanceMetrics()

        # First time fix rate (orders completed without follow-up)
        first_time_fixes = sum(
            1 for o in completed if not o.requires_followup
        )
        first_time_fix_rate = round((first_time_fixes / len(completed)) * 100, 1)

        # Average response time (time from creation to dispatch)
        response_times = []
        for order in completed:
            if order.dispatched_at and order.created_at:
                hours = (order.dispatched_at - order.created_at).total_seconds() / 3600
                response_times.append(hours)
        avg_response_time = 0.0
        if response_times:
            avg_response_time = round(sum(response_times) / len(response_times), 1)

        # Average travel time
        travel_times = []
        for order in completed:
            if order.arrived_at and order.travel_started_at:
                hours = (order.arrived_at - order.travel_started_at).total_seconds() / 3600
                travel_times.append(hours)
        avg_travel_time = 0.0
        if travel_times:
            avg_travel_time = round(sum(travel_times) / len(travel_times), 1)

        # Average work time
        work_times = []
        for order in completed:
            if order.actual_end_time and order.actual_start_time:
                hours = (order.actual_end_time - order.actual_start_time).total_seconds() / 3600
                work_times.append(hours)
        avg_work_time = 0.0
        if work_times:
            avg_work_time = round(sum(work_times) / len(work_times), 1)

        # On-time completion rate
        on_time = sum(
            1 for o in completed
            if o.scheduled_end_time and o.actual_end_time
            and o.actual_end_time <= o.scheduled_end_time
        )
        on_time_rate = round((on_time / len(completed)) * 100, 1) if completed else 0.0

        # SLA compliance rate
        sla_compliant = sum(1 for o in completed if o.sla_met)
        sla_rate = round((sla_compliant / len(completed)) * 100, 1) if completed else 0.0

        return PerformanceMetrics(
            first_time_fix_rate=first_time_fix_rate,
            avg_response_time_hours=avg_response_time,
            avg_travel_time_hours=avg_travel_time,
            avg_work_time_hours=avg_work_time,
            on_time_completion_rate=on_time_rate,
            sla_compliance_rate=sla_rate,
        )

    # -------------------------------------------------------------------------
    # Technician Performance
    # -------------------------------------------------------------------------

    def get_technician_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
        team_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[TechnicianPerformance]:
        """Get performance metrics by technician.

        Args:
            filters: Optional analytics filters
            team_id: Optional team filter
            limit: Max results to return

        Returns:
            List of TechnicianPerformance
        """
        if filters is None:
            filters = AnalyticsFilters()

        # Get technicians
        tech_query = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True,
            ),
        )
        if team_id:
            tech_query = tech_query.filter(FieldTeamMember.team_id == team_id)
        if filters.company:
            tech_query = tech_query.filter(Employee.company == filters.company)

        technicians = tech_query.distinct().all()

        results = []
        for tech in technicians:
            # Get orders for this technician
            order_query = self.db.query(ServiceOrder).filter(
                ServiceOrder.assigned_technician_id == tech.id
            )
            order_query = self._apply_filters(order_query, filters)

            total_orders = order_query.count()
            if total_orders == 0:
                continue

            completed = order_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED
            ).all()
            completed_count = len(completed)

            # Calculate metrics
            completion_rate = round((completed_count / total_orders) * 100, 1)

            avg_rating = 0.0
            rated = [o for o in completed if o.customer_rating]
            if rated:
                avg_rating = round(sum(o.customer_rating for o in rated) / len(rated), 1)

            avg_completion_time = 0.0
            with_times = [
                o for o in completed
                if o.actual_start_time and o.actual_end_time
            ]
            if with_times:
                total_hours = sum(
                    (o.actual_end_time - o.actual_start_time).total_seconds() / 3600
                    for o in with_times
                )
                avg_completion_time = round(total_hours / len(with_times), 1)

            total_revenue = Decimal("0")
            for order in completed:
                if order.total_amount:
                    total_revenue += order.total_amount

            first_time_fixes = sum(1 for o in completed if not o.requires_followup)
            ftf_rate = round((first_time_fixes / completed_count) * 100, 1) if completed_count else 0.0

            results.append(
                TechnicianPerformance(
                    technician_id=tech.id,
                    technician_name=tech.name,
                    total_orders=total_orders,
                    completed_orders=completed_count,
                    completion_rate=completion_rate,
                    avg_rating=avg_rating,
                    avg_completion_time_hours=avg_completion_time,
                    total_revenue=total_revenue,
                    first_time_fix_rate=ftf_rate,
                )
            )

        # Sort by completed orders descending
        results.sort(key=lambda x: x.completed_orders, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # Team Performance
    # -------------------------------------------------------------------------

    def get_team_performance(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> List[TeamPerformance]:
        """Get performance metrics by team.

        Args:
            filters: Optional analytics filters

        Returns:
            List of TeamPerformance
        """
        if filters is None:
            filters = AnalyticsFilters()

        team_query = self.db.query(FieldTeam).filter(FieldTeam.is_active == True)
        if filters.company:
            team_query = team_query.filter(FieldTeam.company == filters.company)

        teams = team_query.all()

        results = []
        for team in teams:
            # Count members
            member_count = (
                self.db.query(func.count(FieldTeamMember.id))
                .filter(
                    FieldTeamMember.team_id == team.id,
                    FieldTeamMember.is_active == True,
                )
                .scalar()
                or 0
            )

            # Get orders for this team
            order_query = self.db.query(ServiceOrder).filter(
                ServiceOrder.assigned_team_id == team.id
            )
            order_query = self._apply_filters(order_query, filters)

            total_orders = order_query.count()
            completed = order_query.filter(
                ServiceOrder.status == ServiceOrderStatus.COMPLETED
            ).all()
            completed_count = len(completed)

            completion_rate = 0.0
            if total_orders > 0:
                completion_rate = round((completed_count / total_orders) * 100, 1)

            avg_rating = 0.0
            rated = [o for o in completed if o.customer_rating]
            if rated:
                avg_rating = round(sum(o.customer_rating for o in rated) / len(rated), 1)

            total_revenue = Decimal("0")
            for order in completed:
                if order.total_amount:
                    total_revenue += order.total_amount

            results.append(
                TeamPerformance(
                    team_id=team.id,
                    team_name=team.name,
                    member_count=member_count,
                    total_orders=total_orders,
                    completed_orders=completed_count,
                    completion_rate=completion_rate,
                    avg_rating=avg_rating,
                    total_revenue=total_revenue,
                )
            )

        # Sort by total orders descending
        results.sort(key=lambda x: x.total_orders, reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Monthly Trends
    # -------------------------------------------------------------------------

    def get_monthly_trends(
        self,
        months: int = 12,
        company: Optional[str] = None,
    ) -> List[MonthlyTrend]:
        """Get monthly trend data.

        Args:
            months: Number of months to include
            company: Optional company filter

        Returns:
            List of MonthlyTrend
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)

        query = self.db.query(ServiceOrder).filter(
            ServiceOrder.created_at >= start_date,
            ServiceOrder.created_at <= end_date,
        )
        if company:
            query = query.filter(ServiceOrder.company == company)

        orders = query.all()

        # Group by month
        trends_dict = {}
        for order in orders:
            period = order.created_at.strftime("%Y-%m")
            if period not in trends_dict:
                trends_dict[period] = {
                    "year": order.created_at.year,
                    "month": order.created_at.month,
                    "total": 0,
                    "completed": 0,
                    "revenue": Decimal("0"),
                }

            trends_dict[period]["total"] += 1
            if order.status == ServiceOrderStatus.COMPLETED:
                trends_dict[period]["completed"] += 1
                if order.total_amount:
                    trends_dict[period]["revenue"] += order.total_amount

        # Convert to list and sort
        trends = [
            MonthlyTrend(
                period=period,
                year=data["year"],
                month=data["month"],
                total_orders=data["total"],
                completed_orders=data["completed"],
                revenue=data["revenue"],
            )
            for period, data in trends_dict.items()
        ]
        trends.sort(key=lambda x: x.period)
        return trends

    # -------------------------------------------------------------------------
    # Cost Analysis
    # -------------------------------------------------------------------------

    def get_cost_analysis(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> CostAnalysis:
        """Get cost analysis metrics.

        Args:
            filters: Optional analytics filters

        Returns:
            CostAnalysis
        """
        if filters is None:
            filters = AnalyticsFilters()

        query = self.db.query(ServiceOrder).filter(
            ServiceOrder.status == ServiceOrderStatus.COMPLETED
        )
        query = self._apply_filters(query, filters)

        orders = query.all()
        if not orders:
            return CostAnalysis()

        # Calculate costs from items
        total_labor_cost = Decimal("0")
        total_parts_cost = Decimal("0")
        total_travel_cost = Decimal("0")
        total_overhead = Decimal("0")
        total_revenue = Decimal("0")

        for order in orders:
            if order.total_amount:
                total_revenue += order.total_amount

            # Get items for cost breakdown
            items = (
                self.db.query(ServiceOrderItem)
                .filter(ServiceOrderItem.order_id == order.id)
                .all()
            )
            for item in items:
                if item.item_type == "labor" and item.total_cost:
                    total_labor_cost += item.total_cost
                elif item.item_type == "part" and item.total_cost:
                    total_parts_cost += item.total_cost
                elif item.item_type == "travel" and item.total_cost:
                    total_travel_cost += item.total_cost

            # Get time entries for additional labor cost
            time_entries = (
                self.db.query(TimeEntry)
                .filter(TimeEntry.service_order_id == order.id)
                .all()
            )
            for entry in time_entries:
                # Calculate labor cost from duration if labor_cost not set
                labor_cost = getattr(entry, 'labor_cost', None)
                if labor_cost:
                    total_labor_cost += labor_cost
                elif entry.duration_hours and entry.is_billable:
                    # Estimate based on duration (default rate)
                    total_labor_cost += entry.duration_hours * Decimal("50")

        order_count = len(orders)
        avg_cost = (total_labor_cost + total_parts_cost + total_travel_cost) / order_count
        avg_revenue = total_revenue / order_count if order_count > 0 else Decimal("0")
        profit_per_order = avg_revenue - avg_cost

        return CostAnalysis(
            total_labor_cost=total_labor_cost,
            total_parts_cost=total_parts_cost,
            total_travel_cost=total_travel_cost,
            total_overhead=total_overhead,
            avg_cost_per_order=avg_cost.quantize(Decimal("0.01")),
            avg_revenue_per_order=avg_revenue.quantize(Decimal("0.01")),
            profit_per_order=profit_per_order.quantize(Decimal("0.01")),
        )

    # -------------------------------------------------------------------------
    # Utilization Metrics
    # -------------------------------------------------------------------------

    def get_utilization(
        self,
        filters: Optional[AnalyticsFilters] = None,
    ) -> UtilizationMetrics:
        """Get utilization metrics for technicians.

        Args:
            filters: Optional analytics filters

        Returns:
            UtilizationMetrics
        """
        if filters is None:
            filters = AnalyticsFilters()

        # Get technicians
        tech_query = self.db.query(Employee).join(
            FieldTeamMember,
            and_(
                FieldTeamMember.party_id == Employee.party_id,
                FieldTeamMember.is_active == True,
            ),
        )
        if filters.company:
            tech_query = tech_query.filter(Employee.company == filters.company)
        if filters.team_id:
            tech_query = tech_query.filter(FieldTeamMember.team_id == filters.team_id)

        technicians = tech_query.distinct().all()

        # Calculate date range
        if filters.start_date and filters.end_date:
            days = (filters.end_date - filters.start_date).days + 1
        else:
            days = 30  # Default to last 30 days

        total_available_hours = 0.0
        total_scheduled_hours = 0.0
        total_worked_hours = 0.0
        overtime_hours = 0.0
        by_technician = []

        for tech in technicians:
            # Available hours: 8 hours per workday
            available = days * 8.0
            total_available_hours += available

            # Get orders for this technician
            order_query = self.db.query(ServiceOrder).filter(
                ServiceOrder.assigned_technician_id == tech.id,
            )
            order_query = self._apply_filters(order_query, filters)

            orders = order_query.all()

            # Scheduled hours
            scheduled = sum(float(o.estimated_duration_hours) for o in orders)
            total_scheduled_hours += scheduled

            # Worked hours (from completed orders)
            worked = 0.0
            for order in orders:
                if (
                    order.status == ServiceOrderStatus.COMPLETED
                    and order.actual_start_time
                    and order.actual_end_time
                ):
                    worked += (order.actual_end_time - order.actual_start_time).total_seconds() / 3600
            total_worked_hours += worked

            # Overtime (anything over 8 hours per day)
            daily_overtime = max(0.0, (worked / days) - 8.0) * days if days > 0 else 0.0
            overtime_hours += daily_overtime

            utilization = round((worked / available) * 100, 1) if available > 0 else 0.0

            by_technician.append({
                "technician_id": tech.id,
                "technician_name": tech.name,
                "available_hours": round(available, 1),
                "scheduled_hours": round(scheduled, 1),
                "worked_hours": round(worked, 1),
                "utilization_rate": utilization,
            })

        # Calculate overall utilization
        utilization_rate = 0.0
        if total_available_hours > 0:
            utilization_rate = round(
                (total_worked_hours / total_available_hours) * 100, 1
            )

        idle_time = max(0.0, total_available_hours - total_worked_hours)

        return UtilizationMetrics(
            total_available_hours=round(total_available_hours, 1),
            total_scheduled_hours=round(total_scheduled_hours, 1),
            total_worked_hours=round(total_worked_hours, 1),
            utilization_rate=utilization_rate,
            idle_time_hours=round(idle_time, 1),
            overtime_hours=round(overtime_hours, 1),
            by_technician=by_technician,
        )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _apply_filters(self, query, filters: AnalyticsFilters):
        """Apply common filters to a query."""
        if filters.start_date:
            query = query.filter(ServiceOrder.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(ServiceOrder.created_at <= filters.end_date)
        if filters.team_id:
            query = query.filter(ServiceOrder.assigned_team_id == filters.team_id)
        if filters.zone_id:
            query = query.filter(ServiceOrder.zone_id == filters.zone_id)
        if filters.company:
            query = query.filter(ServiceOrder.company == filters.company)
        return query
