"""
Field Service Analytics API

Performance metrics, completion rates, and utilization reports.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_
from typing import Dict, Any, Optional, List, cast
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.field_service import (
    ServiceOrder,
    ServiceOrderType,
    ServiceOrderStatus,
    ServiceOrderPriority,
    ServiceTimeEntry,
    FieldTeam,
    FieldTeamMember,
    TimeEntryType,
)
from app.models.employee import Employee

router = APIRouter()


def get_period_dates(period: str) -> tuple[date, date]:
    """Get start and end dates for a given period."""
    end = date.today()
    if period == "week":
        start = end - timedelta(days=7)
    elif period == "month":
        start = end - timedelta(days=30)
    elif period == "quarter":
        start = end - timedelta(days=90)
    elif period == "year":
        start = end - timedelta(days=365)
    else:
        start = end - timedelta(days=30)
    return start, end


# =============================================================================
# DASHBOARD (FRONTEND)
# =============================================================================

@router.get("/analytics/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("field-service-dashboard", ttl=CACHE_TTL["short"])
async def get_analytics_dashboard(
    period: str = "month",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get dashboard metrics for field service analytics page."""
    start, end = get_period_dates(period)

    # Base query
    base_query = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    )

    total_orders = base_query.count()
    completed_orders = base_query.filter(ServiceOrder.status == ServiceOrderStatus.COMPLETED).count()
    cancelled_orders = base_query.filter(ServiceOrder.status == ServiceOrderStatus.CANCELLED).count()

    completion_rate = round(completed_orders / total_orders * 100, 1) if total_orders > 0 else 0
    cancellation_rate = round(cancelled_orders / total_orders * 100, 1) if total_orders > 0 else 0

    # Average rating
    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.customer_rating.isnot(None),
    ).scalar()

    total_ratings = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.customer_rating.isnot(None),
    ).scalar() or 0

    # Average response time (time from creation to arrival on site)
    avg_response = db.query(
        func.avg(
            func.extract('epoch', ServiceOrder.arrival_time) -
            func.extract('epoch', ServiceOrder.created_at)
        )
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.arrival_time.isnot(None),
    ).scalar()

    avg_response_minutes = round(float(avg_response) / 60, 0) if avg_response else None

    # Average service duration
    avg_service = db.query(
        func.avg(
            func.extract('epoch', ServiceOrder.actual_end_time) -
            func.extract('epoch', ServiceOrder.actual_start_time)
        )
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.actual_start_time.isnot(None),
        ServiceOrder.actual_end_time.isnot(None),
    ).scalar()

    avg_service_minutes = round(float(avg_service) / 60, 0) if avg_service else None

    # Average travel time
    avg_travel = db.query(
        func.avg(
            func.extract('epoch', ServiceOrder.arrival_time) -
            func.extract('epoch', ServiceOrder.travel_start_time)
        )
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.travel_start_time.isnot(None),
        ServiceOrder.arrival_time.isnot(None),
    ).scalar()

    avg_travel_minutes = round(float(avg_travel) / 60, 0) if avg_travel else None

    # Total revenue
    total_revenue = db.query(func.sum(ServiceOrder.billable_amount)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).scalar() or 0

    # Status distribution
    status_counts = db.query(
        ServiceOrder.status,
        func.count(ServiceOrder.id)
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).group_by(ServiceOrder.status).all()

    status_distribution = {str(s.value): c for s, c in status_counts}

    # Daily trend (last 14 days)
    daily_trend = []
    for i in range(14, -1, -1):
        day = end - timedelta(days=i)
        day_completed = db.query(func.count(ServiceOrder.id)).filter(
            ServiceOrder.scheduled_date == day,
            ServiceOrder.status == ServiceOrderStatus.COMPLETED,
        ).scalar() or 0
        daily_trend.append({
            "date": day.isoformat(),
            "completed": day_completed,
        })

    # Previous period comparison
    prev_start = start - (end - start)
    prev_end = start - timedelta(days=1)
    prev_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= prev_start,
        ServiceOrder.scheduled_date <= prev_end,
    ).scalar() or 0

    orders_trend = round((total_orders - prev_orders) / prev_orders * 100, 1) if prev_orders > 0 else 0

    return {
        "period": {
            "name": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "completion_rate": completion_rate,
            "cancellation_rate": cancellation_rate,
            "avg_rating": round(float(avg_rating), 1) if avg_rating else None,
            "total_ratings": total_ratings,
            "avg_response_time": avg_response_minutes,
            "avg_service_duration": avg_service_minutes,
            "avg_travel_time": avg_travel_minutes,
            "total_revenue": float(total_revenue),
            "orders_trend": orders_trend,
        },
        "status_distribution": status_distribution,
        "daily_trend": daily_trend,
    }


@router.get("/analytics/order-type-breakdown", dependencies=[Depends(Require("analytics:read"))])
async def get_order_type_breakdown(
    period: str = "month",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get breakdown of orders by type."""
    start, end = get_period_dates(period)

    type_counts = db.query(
        ServiceOrder.order_type,
        func.count(ServiceOrder.id).label("count"),
        func.sum(case((ServiceOrder.status == ServiceOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
        func.avg(ServiceOrder.customer_rating).label("avg_rating"),
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).group_by(ServiceOrder.order_type).all()

    data = []
    for row in type_counts:
        data.append({
            "order_type": row.order_type.value if row.order_type else "unknown",
            "count": row.count,
            "completed": row.completed or 0,
            "completion_rate": round((row.completed or 0) / row.count * 100, 1) if row.count > 0 else 0,
            "avg_rating": round(float(row.avg_rating), 1) if row.avg_rating else None,
        })

    return {
        "period": period,
        "data": sorted(data, key=lambda x: x["count"], reverse=True),
    }


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================

@router.get("/analytics/performance", dependencies=[Depends(Require("analytics:read"))])
@cached("field-service-performance", ttl=CACHE_TTL["medium"])
async def get_performance_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get overall field service performance metrics."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    # Base query for the period
    base_query = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    )

    total_orders = base_query.count()

    # Completion metrics
    completed = base_query.filter(ServiceOrder.status == ServiceOrderStatus.COMPLETED).count()
    cancelled = base_query.filter(ServiceOrder.status == ServiceOrderStatus.CANCELLED).count()

    completion_rate = round(completed / total_orders * 100, 1) if total_orders > 0 else 0

    # First-time fix rate (orders completed without rescheduling)
    # No reschedule history available on ServiceOrder; fallback to completed count.
    first_time_fix = completed

    ftf_rate = round(first_time_fix / completed * 100, 1) if completed > 0 else 0

    # Average response time (from scheduled to completed)
    avg_duration = db.query(
        func.avg(
            func.extract('epoch', ServiceOrder.actual_end_time) -
            func.extract('epoch', ServiceOrder.actual_start_time)
        )
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
        ServiceOrder.actual_start_time.isnot(None),
        ServiceOrder.actual_end_time.isnot(None),
    ).scalar()

    avg_duration_hours = round(float(avg_duration) / 3600, 1) if avg_duration else 0

    # Customer satisfaction
    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.customer_rating.isnot(None),
    ).scalar()

    rating_count = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.customer_rating.isnot(None),
    ).scalar() or 0

    # By priority
    by_priority = db.query(
        ServiceOrder.priority,
        func.count(ServiceOrder.id).label("total"),
        func.sum(case((ServiceOrder.status == ServiceOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).group_by(ServiceOrder.priority).all()

    # By type
    by_type = db.query(
        ServiceOrder.order_type,
        func.count(ServiceOrder.id).label("total"),
        func.sum(case((ServiceOrder.status == ServiceOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).group_by(ServiceOrder.order_type).all()

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": total_orders,
            "completed": completed,
            "cancelled": cancelled,
            "completion_rate": completion_rate,
            "first_time_fix_rate": ftf_rate,
            "avg_duration_hours": avg_duration_hours,
        },
        "customer_satisfaction": {
            "avg_rating": round(float(avg_rating), 1) if avg_rating else 0,
            "total_ratings": rating_count,
            "response_rate": round(rating_count / completed * 100, 1) if completed > 0 else 0,
        },
        "by_priority": [
            {
                "priority": p.priority.value,
                "total": p.total,
                "completed": p.completed or 0,
                "completion_rate": round((p.completed or 0) / p.total * 100, 1) if p.total > 0 else 0,
            }
            for p in by_priority
        ],
        "by_type": [
            {
                "order_type": t.order_type.value,
                "total": t.total,
                "completed": t.completed or 0,
                "completion_rate": round((t.completed or 0) / t.total * 100, 1) if t.total > 0 else 0,
            }
            for t in by_type
        ],
    }


@router.get("/analytics/technician-performance", dependencies=[Depends(Require("analytics:read"))])
async def get_technician_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    team_id: Optional[int] = None,
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get performance metrics by technician."""
    # Support both period and explicit dates
    if period:
        start, end = get_period_dates(period)
    elif end_date:
        end = date.fromisoformat(end_date)
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=30)
    else:
        end = date.today()
        start = end - timedelta(days=30)

    # Get technicians
    tech_query = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    )

    if team_id:
        tech_query = tech_query.filter(FieldTeamMember.team_id == team_id)

    technicians = tech_query.distinct().limit(limit).all()

    performance = []
    for tech in technicians:
        # Get orders for this technician
        orders = db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.scheduled_date >= start,
            ServiceOrder.scheduled_date <= end,
        ).all()

        total = len(orders)
        completed = sum(1 for o in orders if o.status == ServiceOrderStatus.COMPLETED)

        # Average rating
        ratings = [o.customer_rating for o in orders if o.customer_rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # Average duration
        durations = []
        for o in orders:
            if o.actual_start_time and o.actual_end_time and o.status == ServiceOrderStatus.COMPLETED:
                delta = o.actual_end_time - o.actual_start_time
                durations.append(delta.total_seconds() / 3600)

        avg_duration = sum(durations) / len(durations) if durations else 0

        # Total billable hours
        time_entries = db.query(ServiceTimeEntry).filter(
            ServiceTimeEntry.employee_id == tech.id,
            ServiceTimeEntry.start_time >= datetime.combine(start, datetime.min.time()),
            ServiceTimeEntry.start_time <= datetime.combine(end, datetime.max.time()),
            ServiceTimeEntry.is_billable == True,
        ).all()

        billable_hours = sum(
            float(e.duration_hours) for e in time_entries
            if e.duration_hours is not None
        )

        # Get team name
        team_membership = db.query(FieldTeamMember).filter(
            FieldTeamMember.employee_id == tech.id,
            FieldTeamMember.is_active == True
        ).first()
        team_name = None
        if team_membership:
            team = db.query(FieldTeam).filter(FieldTeam.id == team_membership.team_id).first()
            team_name = team.name if team else None

        performance.append({
            "id": tech.id,
            "technician_id": tech.id,
            "name": tech.name,
            "technician_name": tech.name,
            "team_name": team_name,
            "total_orders": total,
            "completed_orders": completed,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "avg_rating": round(avg_rating, 1),
            "rating_count": len(ratings),
            "avg_duration_hours": round(avg_duration, 1),
            "billable_hours": round(billable_hours, 1),
        })

    # Sort by completion rate
    performance.sort(key=lambda x: float(cast(float | int, x.get("completion_rate", 0.0))), reverse=True)

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "data": performance,
        "technicians": performance,
    }


@router.get("/analytics/team-performance", dependencies=[Depends(Require("analytics:read"))])
async def get_team_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get performance metrics by team."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()

    performance = []
    for team in teams:
        # Get orders for this team
        orders = db.query(ServiceOrder).filter(
            ServiceOrder.assigned_team_id == team.id,
            ServiceOrder.scheduled_date >= start,
            ServiceOrder.scheduled_date <= end,
        ).all()

        total = len(orders)
        completed = sum(1 for o in orders if o.status == ServiceOrderStatus.COMPLETED)

        # Average rating
        ratings = [o.customer_rating for o in orders if o.customer_rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # Total revenue
        total_billed = sum(float(o.billable_amount) for o in orders if o.status == ServiceOrderStatus.COMPLETED)
        total_cost = sum(float(o.total_cost) for o in orders if o.status == ServiceOrderStatus.COMPLETED)

        performance.append({
            "team_id": team.id,
            "team_name": team.name,
            "member_count": len([m for m in team.members if m.is_active]),
            "total_orders": total,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "avg_rating": round(avg_rating, 1),
            "total_billed": round(total_billed, 2),
            "total_cost": round(total_cost, 2),
            "profit": round(total_billed - total_cost, 2),
        })

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "teams": performance,
    }


# =============================================================================
# TRENDS
# =============================================================================

@router.get("/analytics/trends", dependencies=[Depends(Require("analytics:read"))])
async def get_trends(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get monthly trends for service orders."""
    end = date.today()
    start = end - timedelta(days=months * 30)

    # Monthly aggregation
    monthly_data = db.query(
        extract("year", ServiceOrder.scheduled_date).label("year"),
        extract("month", ServiceOrder.scheduled_date).label("month"),
        func.count(ServiceOrder.id).label("total"),
        func.sum(case((ServiceOrder.status == ServiceOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
        func.sum(case((ServiceOrder.status == ServiceOrderStatus.CANCELLED, 1), else_=0)).label("cancelled"),
        func.avg(ServiceOrder.customer_rating).label("avg_rating"),
    ).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).group_by(
        extract("year", ServiceOrder.scheduled_date),
        extract("month", ServiceOrder.scheduled_date),
    ).order_by(
        extract("year", ServiceOrder.scheduled_date),
        extract("month", ServiceOrder.scheduled_date),
    ).all()

    trends = []
    for row in monthly_data:
        period = f"{int(row.year)}-{int(row.month):02d}"
        trends.append({
            "period": period,
            "total": row.total,
            "completed": row.completed or 0,
            "cancelled": row.cancelled or 0,
            "completion_rate": round((row.completed or 0) / row.total * 100, 1) if row.total > 0 else 0,
            "avg_rating": round(float(row.avg_rating), 1) if row.avg_rating else 0,
        })

    return {
        "months": months,
        "trends": trends,
    }


# =============================================================================
# COST ANALYSIS
# =============================================================================

@router.get("/analytics/costs", dependencies=[Depends(Require("analytics:read"))])
async def get_cost_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost analysis for field service operations."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    # Get completed orders in period
    orders = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).all()

    total_labor = sum(float(o.labor_cost) for o in orders)
    total_parts = sum(float(o.parts_cost) for o in orders)
    total_travel = sum(float(o.travel_cost) for o in orders)
    total_cost = sum(float(o.total_cost) for o in orders)
    total_billed = sum(float(o.billable_amount) for o in orders)

    # By order type
    by_type: Dict[str, Dict] = {}
    for order in orders:
        type_key = order.order_type.value
        if type_key not in by_type:
            by_type[type_key] = {
                "order_type": type_key,
                "count": 0,
                "total_cost": 0,
                "total_billed": 0,
                "labor_cost": 0,
                "parts_cost": 0,
                "travel_cost": 0,
            }

        by_type[type_key]["count"] += 1
        by_type[type_key]["total_cost"] += float(order.total_cost)
        by_type[type_key]["total_billed"] += float(order.billable_amount)
        by_type[type_key]["labor_cost"] += float(order.labor_cost)
        by_type[type_key]["parts_cost"] += float(order.parts_cost)
        by_type[type_key]["travel_cost"] += float(order.travel_cost)

    # Calculate averages
    order_count = len(orders)
    avg_cost_per_order = total_cost / order_count if order_count > 0 else 0
    avg_billed_per_order = total_billed / order_count if order_count > 0 else 0

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "total_orders": order_count,
            "total_cost": round(total_cost, 2),
            "total_billed": round(total_billed, 2),
            "gross_profit": round(total_billed - total_cost, 2),
            "profit_margin": round((total_billed - total_cost) / total_billed * 100, 1) if total_billed > 0 else 0,
            "avg_cost_per_order": round(avg_cost_per_order, 2),
            "avg_billed_per_order": round(avg_billed_per_order, 2),
        },
        "cost_breakdown": {
            "labor": round(total_labor, 2),
            "parts": round(total_parts, 2),
            "travel": round(total_travel, 2),
            "labor_pct": round(total_labor / total_cost * 100, 1) if total_cost > 0 else 0,
            "parts_pct": round(total_parts / total_cost * 100, 1) if total_cost > 0 else 0,
            "travel_pct": round(total_travel / total_cost * 100, 1) if total_cost > 0 else 0,
        },
        "by_type": list(by_type.values()),
    }


# =============================================================================
# UTILIZATION
# =============================================================================

@router.get("/analytics/utilization", dependencies=[Depends(Require("analytics:read"))])
async def get_utilization(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get resource utilization metrics."""
    # Default to last 30 days
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()

    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    # Get all technicians
    technicians = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    ).distinct().all()

    # Calculate working days in period
    working_days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday to Friday
            working_days += 1
        current += timedelta(days=1)

    # Available hours (8 hours per day per technician)
    total_available_hours = len(technicians) * working_days * 8

    # Get time entries
    time_entries = db.query(ServiceTimeEntry).filter(
        ServiceTimeEntry.start_time >= datetime.combine(start, datetime.min.time()),
        ServiceTimeEntry.start_time <= datetime.combine(end, datetime.max.time()),
    ).all()

    total_work_hours = sum(
        float(e.duration_hours) for e in time_entries
        if e.duration_hours and e.entry_type == TimeEntryType.WORK
    )

    total_travel_hours = sum(
        float(e.duration_hours) for e in time_entries
        if e.duration_hours and e.entry_type == TimeEntryType.TRAVEL
    )

    total_billable_hours = sum(
        float(e.duration_hours) for e in time_entries
        if e.duration_hours and e.is_billable
    )

    utilization_rate = round(
        (total_work_hours + total_travel_hours) / total_available_hours * 100, 1
    ) if total_available_hours > 0 else 0

    billable_rate = round(
        total_billable_hours / (total_work_hours + total_travel_hours) * 100, 1
    ) if (total_work_hours + total_travel_hours) > 0 else 0

    # Orders per technician per day
    total_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    ).scalar() or 0

    orders_per_tech_per_day = round(
        total_orders / (len(technicians) * working_days), 1
    ) if (len(technicians) * working_days) > 0 else 0

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "working_days": working_days,
        },
        "capacity": {
            "technician_count": len(technicians),
            "total_available_hours": total_available_hours,
        },
        "utilization": {
            "work_hours": round(total_work_hours, 1),
            "travel_hours": round(total_travel_hours, 1),
            "total_logged_hours": round(total_work_hours + total_travel_hours, 1),
            "utilization_rate": utilization_rate,
            "billable_hours": round(total_billable_hours, 1),
            "billable_rate": billable_rate,
        },
        "productivity": {
            "total_orders": total_orders,
            "orders_per_tech_per_day": orders_per_tech_per_day,
            "avg_hours_per_order": round(
                total_work_hours / total_orders, 1
            ) if total_orders > 0 else 0,
        },
    }
