"""
Operations Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.api.dashboards.common import resolve_currency_or_raise, parse_date_param

from app.models.field_service import ServiceOrder, ServiceOrderStatus
from app.models.inventory import Warehouse
from app.models.asset import Asset, AssetStatus, AssetCategory
from app.models import Project, ProjectStatus, Milestone

router = APIRouter(tags=["dashboards"])

# =============================================================================
# FIELD SERVICE DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/field-service", dependencies=[Depends(Require("field-service:read"))])
@cached("dashboard-field-service", ttl=CACHE_TTL["short"])
async def get_field_service_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Field Service Dashboard endpoint.

    Combines data from:
    - Dashboard summary (today's orders, completion, etc.)
    - Today's orders list
    """
    from app.models.field_service import ServiceOrder, ServiceOrderStatus

    now = datetime.now(timezone.utc)
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # =========== SUMMARY METRICS ===========
    today_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
    ).scalar() or 0

    completed_today = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).scalar() or 0

    unassigned = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.DISPATCHED]),
        ServiceOrder.assigned_technician_id.is_(None),
    ).scalar() or 0

    overdue = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.DISPATCHED, ServiceOrderStatus.IN_PROGRESS]),
        ServiceOrder.scheduled_date < today_start,
    ).scalar() or 0

    # Week completion rate
    week_total = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= datetime.combine(week_start, datetime.min.time()),
        ServiceOrder.scheduled_date <= datetime.combine(week_end, datetime.max.time()),
    ).scalar() or 0

    week_completed = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= datetime.combine(week_start, datetime.min.time()),
        ServiceOrder.scheduled_date <= datetime.combine(week_end, datetime.max.time()),
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
    ).scalar() or 0

    week_completion_rate = round(week_completed / week_total * 100, 1) if week_total > 0 else 0

    # Avg customer rating
    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.customer_rating.isnot(None),
    ).scalar()
    avg_customer_rating = round(float(avg_rating or 0), 1)

    # By status
    by_status = {
        row.status.value if row.status else "unknown": row.count
        for row in db.query(
            ServiceOrder.status,
            func.count(ServiceOrder.id).label("count"),
        ).group_by(ServiceOrder.status).all()
    }

    # By type
    by_type = {
        row.order_type.value if row.order_type else "unknown": row.count
        for row in db.query(
            ServiceOrder.order_type,
            func.count(ServiceOrder.id).label("count"),
        ).group_by(ServiceOrder.order_type).all()
    }

    # =========== TODAY'S ORDERS ===========
    today_orders_list = []
    for order in db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= today_start,
        ServiceOrder.scheduled_date <= today_end,
    ).order_by(ServiceOrder.scheduled_date.asc()).limit(10).all():
        # Use the technician relationship from ServiceOrder
        technician_name = order.technician.name if order.technician else None

        today_orders_list.append({
            "id": order.id,
            "order_number": order.order_number,
            "order_type": order.order_type.value if order.order_type else None,
            "status": order.status.value if order.status else None,
            "customer_name": order.customer.name if order.customer else None,
            "customer_address": order.service_address,
            "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
            "technician_name": technician_name,
            "priority": order.priority.value if order.priority else None,
        })

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "today_orders": today_orders,
            "completed_today": completed_today,
            "unassigned": unassigned,
            "overdue": overdue,
            "week_completion_rate": week_completion_rate,
            "avg_customer_rating": avg_customer_rating,
        },

        "by_status": by_status,
        "by_type": by_type,

        "today_schedule": today_orders_list,
    }


# =============================================================================
# FIELD SERVICE SCHEDULE - Calendar/Dispatch View (3 calls → 1)
# =============================================================================

@router.get("/field-service-schedule", dependencies=[Depends(Require("field_service:read"))])
@cached("dashboard-fs-schedule", ttl=CACHE_TTL["short"])
async def get_field_service_schedule_dashboard(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    team_id: Optional[int] = Query(default=None, description="Filter by team ID"),
    technician_id: Optional[int] = Query(default=None, description="Filter by technician ID"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Field Service Schedule endpoint for calendar and dispatch views.

    Combines data from:
    - Teams list with members
    - Calendar events (service orders in date range)
    - Dispatch board (technician assignments and workload)
    - Summary metrics
    """
    from app.models.field_service import (
        ServiceOrder,
        ServiceOrderStatus,
        ServiceOrderPriority,
        FieldTeam,
        FieldTeamMember,
    )
    from app.models.employee import Employee, EmploymentStatus

    now = datetime.now(timezone.utc)

    # Parse dates
    start = parse_date_param(start_date, "start_date")
    end = parse_date_param(end_date, "end_date")
    if not start or not end:
        raise HTTPException(status_code=400, detail="start_date and end_date are required")

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    # =========== TEAMS DATA ===========
    # Use eager loading to avoid N+1 queries (reduces O(T*M) queries to 2-3)
    teams_query = db.query(FieldTeam).options(
        selectinload(FieldTeam.members).joinedload(FieldTeamMember.employee)
    ).filter(FieldTeam.is_active == True)
    if team_id:
        teams_query = teams_query.filter(FieldTeam.id == team_id)

    teams_list = []
    for team in teams_query.all():
        members = []
        for membership in team.members:
            if membership.is_active and membership.employee:
                members.append({
                    "id": membership.employee.id,
                    "name": membership.employee.name,
                    "role": membership.role,
                    "avatar_url": None,  # Add if available
                })

        teams_list.append({
            "id": team.id,
            "name": team.name,
            "max_daily_orders": team.max_daily_orders,
            "members": members,
            "member_count": len(members),
        })

    # =========== CALENDAR EVENTS ===========
    orders_query = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
    )
    if team_id:
        orders_query = orders_query.filter(ServiceOrder.assigned_team_id == team_id)
    if technician_id:
        orders_query = orders_query.filter(ServiceOrder.assigned_technician_id == technician_id)

    calendar_events: list[dict[str, Any]] = []
    for order in orders_query.order_by(ServiceOrder.scheduled_date.asc(), ServiceOrder.scheduled_start_time.asc()).all():
        # Calculate start/end datetimes
        order_start = datetime.combine(order.scheduled_date, order.scheduled_start_time or datetime.min.time())
        if order.scheduled_end_time:
            order_end = datetime.combine(order.scheduled_date, order.scheduled_end_time)
        else:
            # Default to estimated duration
            order_end = order_start + timedelta(hours=float(order.estimated_duration_hours or 1))

        # Get technician name
        technician_name = order.technician.name if order.technician else None

        # Determine color based on status/priority
        color_map = {
            ServiceOrderStatus.COMPLETED: "success",
            ServiceOrderStatus.CANCELLED: "default",
            ServiceOrderStatus.FAILED: "danger",
            ServiceOrderStatus.IN_PROGRESS: "info",
            ServiceOrderStatus.ON_SITE: "info",
            ServiceOrderStatus.EN_ROUTE: "warning",
            ServiceOrderStatus.PENDING_PARTS: "warning",
        }
        color = color_map.get(order.status, "default")
        if order.priority in [ServiceOrderPriority.URGENT, ServiceOrderPriority.EMERGENCY]:
            color = "danger"

        calendar_events.append({
            "id": str(order.id),
            "title": order.title or order.order_number,
            "start": order_start.isoformat(),
            "end": order_end.isoformat(),
            "allDay": False,
            "color": color,
            "resourceId": str(order.assigned_technician_id) if order.assigned_technician_id else None,
            "metadata": {
                "order_number": order.order_number,
                "order_type": order.order_type.value if order.order_type else None,
                "status": order.status.value if order.status else None,
                "priority": order.priority.value if order.priority else None,
                "customer_name": order.customer.name if order.customer else None,
                "customer_address": order.service_address,
                "technician_id": order.assigned_technician_id,
                "technician_name": technician_name,
                "team_id": order.assigned_team_id,
                "city": order.city,
            },
        })

    # =========== DISPATCH BOARD (Today's view) ===========
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Get all technicians with today's assignments
    technicians_with_orders = db.query(
        Employee.id,
        Employee.name,
        func.count(ServiceOrder.id).label("order_count"),
    ).outerjoin(
        ServiceOrder,
        and_(
            ServiceOrder.assigned_technician_id == Employee.id,
            ServiceOrder.scheduled_date == today,
        )
    ).filter(
        Employee.status == EmploymentStatus.ACTIVE,
        Employee.id.in_(
            db.query(FieldTeamMember.employee_id).filter(FieldTeamMember.is_active == True)
        )
    ).group_by(Employee.id, Employee.name).all()

    resources: list[dict[str, Any]] = []
    dispatch_board = {
        "date": today.isoformat(),
        "resources": resources,
    }

    for tech in technicians_with_orders:
        # Get today's orders for this technician
        tech_orders = db.query(ServiceOrder).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.scheduled_date == today,
        ).order_by(ServiceOrder.scheduled_start_time.asc()).all()

        orders_summary = []
        for o in tech_orders:
            orders_summary.append({
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status.value if o.status else None,
                "priority": o.priority.value if o.priority else None,
                "scheduled_time": o.scheduled_start_time.isoformat() if o.scheduled_start_time else None,
                "customer_name": o.customer.name if o.customer else None,
                "city": o.city,
            })

        # Determine availability status
        in_progress = any(o.status in [ServiceOrderStatus.IN_PROGRESS, ServiceOrderStatus.ON_SITE, ServiceOrderStatus.EN_ROUTE] for o in tech_orders)
        completed_count = sum(1 for o in tech_orders if o.status == ServiceOrderStatus.COMPLETED)
        pending_count = sum(1 for o in tech_orders if o.status in [ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.DISPATCHED])

        if in_progress:
            availability = "busy"
        elif pending_count > 0:
            availability = "scheduled"
        elif completed_count == len(tech_orders) and len(tech_orders) > 0:
            availability = "done"
        else:
            availability = "available"

        resources.append({
            "id": str(tech.id),
            "name": tech.name,
            "order_count": tech.order_count,
            "orders": orders_summary,
            "completed": completed_count,
            "pending": pending_count,
            "availability": availability,
        })

    # =========== SUMMARY ===========
    total_in_range = len(calendar_events)
    by_status: dict[str, int] = {}
    for event in calendar_events:
        status = event["metadata"]["status"] or "unknown"
        by_status[status] = by_status.get(status, 0) + 1

    unassigned_count = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date >= start,
        ServiceOrder.scheduled_date <= end,
        ServiceOrder.assigned_technician_id.is_(None),
        ServiceOrder.status.notin_([ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]),
    ).scalar() or 0

    overdue_count = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date < today,
        ServiceOrder.status.notin_([ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]),
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_orders": total_in_range,
            "unassigned": unassigned_count,
            "overdue": overdue_count,
            "by_status": by_status,
        },

        "teams": teams_list,
        "calendar_events": calendar_events,
        "dispatch_board": dispatch_board,
    }


# =============================================================================
# INVENTORY DASHBOARD - Consolidated (3 calls → 1)
# =============================================================================

@router.get("/inventory", dependencies=[Depends(Require("inventory:read"))])
@cached("dashboard-inventory", ttl=CACHE_TTL["short"])
async def get_inventory_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Inventory Dashboard endpoint.

    Combines data from:
    - Stock summary (total value, item count)
    - Warehouse breakdown
    - Recent stock entries
    - Items with stock
    - Low stock alerts (coming soon)
    """
    from app.models.inventory import (
        Warehouse, StockEntry, StockLedgerEntry
    )
    from app.models.sales import Item

    now = datetime.now(timezone.utc)

    # =========== STOCK SUMMARY ===========
    # Get total stock value from stock ledger (latest entry per item/warehouse)
    stock_value_query = db.query(
        func.sum(StockLedgerEntry.stock_value)
    ).filter(
        StockLedgerEntry.is_cancelled == False
    )
    # This is a simplification - ideally we'd get the latest balance per item/warehouse
    total_stock_value = float(stock_value_query.scalar() or 0)

    # Total items with stock
    items_with_stock = db.query(
        func.count(distinct(StockLedgerEntry.item_code))
    ).filter(
        StockLedgerEntry.qty_after_transaction > 0,
        StockLedgerEntry.is_cancelled == False
    ).scalar() or 0

    # Total warehouses
    total_warehouses = db.query(func.count(Warehouse.id)).filter(
        Warehouse.disabled == False,
        Warehouse.is_group == False
    ).scalar() or 0

    # =========== WAREHOUSE BREAKDOWN ===========
    warehouse_summary = db.query(
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.stock_value).label("value"),
        func.count(distinct(StockLedgerEntry.item_code)).label("items")
    ).filter(
        StockLedgerEntry.is_cancelled == False
    ).group_by(
        StockLedgerEntry.warehouse
    ).order_by(
        func.sum(StockLedgerEntry.stock_value).desc()
    ).limit(10).all()

    stock_by_warehouse = [
        {
            "warehouse": row.warehouse,
            "value": float(row.value or 0),
            "items": row.items
        }
        for row in warehouse_summary
    ]

    # =========== RECENT STOCK ENTRIES ===========
    recent_entries = [
        {
            "id": e.id,
            "stock_entry_type": e.stock_entry_type,
            "posting_date": e.posting_date.isoformat() if e.posting_date else None,
            "total_amount": float(e.total_amount or 0),
            "from_warehouse": e.from_warehouse,
            "to_warehouse": e.to_warehouse,
            "docstatus": e.docstatus,
        }
        for e in db.query(StockEntry).filter(
            StockEntry.is_deleted == False
        ).order_by(
            StockEntry.posting_date.desc()
        ).limit(5).all()
    ]

    # =========== RECENT ITEMS ===========
    # Get items with actual stock
    recent_items = [
        {
            "id": i.id,
            "item_code": i.item_code,
            "item_name": i.item_name,
            "stock_uom": i.stock_uom,
            "total_stock_qty": 0,  # Would need aggregation from SLE
        }
        for i in db.query(Item).filter(
            Item.is_stock_item == True,
            Item.disabled == False
        ).order_by(
            Item.updated_at.desc()
        ).limit(5).all()
    ]

    # =========== ENTRY COUNTS ===========
    total_entries = db.query(func.count(StockEntry.id)).filter(
        StockEntry.is_deleted == False
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_value": total_stock_value,
            "total_items": items_with_stock,
            "total_warehouses": total_warehouses,
            "low_stock_alerts": 0,  # TODO: Implement reorder level check
        },

        "stock_by_warehouse": stock_by_warehouse,

        "recent": {
            "entries": recent_entries,
            "items": recent_items,
        },

        "counts": {
            "total_entries": total_entries,
        },
    }


# =============================================================================
# ASSETS DASHBOARD - Consolidated (5 calls → 1)
# =============================================================================

@router.get("/assets", dependencies=[Depends(Require("assets:read"))])
@cached("dashboard-assets", ttl=CACHE_TTL["short"])
async def get_assets_dashboard(
    days_ahead: int = 30,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Assets Dashboard endpoint.

    Combines data from:
    - Asset totals (count, purchase value, book value, depreciation)
    - Assets by status
    - Pending depreciation entries
    - Maintenance due
    - Warranty expiring
    - Insurance expiring
    """
    from app.models.asset import Asset, AssetStatus, AssetDepreciationSchedule

    now = datetime.now(timezone.utc)
    today = date.today()
    future_date = today + timedelta(days=days_ahead)

    # =========== TOTALS ===========
    totals = db.query(
        func.count(Asset.id).label("asset_count"),
        func.sum(Asset.gross_purchase_amount).label("purchase_value"),
        func.sum(Asset.asset_value).label("book_value"),
        func.sum(Asset.opening_accumulated_depreciation).label("accumulated_depreciation"),
    ).filter(
        Asset.status != AssetStatus.SCRAPPED
    ).first()

    totals_data = {
        "count": int(totals.asset_count) if totals and totals.asset_count is not None else 0,
        "purchase_value": float(totals.purchase_value or 0) if totals else 0,
        "book_value": float(totals.book_value or 0) if totals else 0,
        "accumulated_depreciation": float(totals.accumulated_depreciation or 0) if totals else 0,
    }

    # =========== BY STATUS ===========
    by_status = [
        {"status": row.status.value if row.status else "unknown", "count": int(row.status_count or 0)}
        for row in db.query(
            Asset.status,
            func.count(Asset.id).label("status_count")
        ).group_by(Asset.status).all()
    ]

    # =========== PENDING DEPRECIATION ===========
    pending_depreciation = db.query(AssetDepreciationSchedule).join(Asset).filter(
        AssetDepreciationSchedule.depreciation_booked == False,
        AssetDepreciationSchedule.schedule_date <= today,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(AssetDepreciationSchedule.schedule_date.asc()).limit(10).all()

    pending_dep_entries = [
        {
            "asset_id": d.asset_id,
            "asset_name": d.asset.asset_name if d.asset else None,
            "schedule_date": d.schedule_date.isoformat() if d.schedule_date else None,
            "depreciation_amount": float(d.depreciation_amount or 0),
        }
        for d in pending_depreciation
    ]

    pending_dep_total = db.query(
        func.count(AssetDepreciationSchedule.id),
        func.sum(AssetDepreciationSchedule.depreciation_amount)
    ).join(Asset).filter(
        AssetDepreciationSchedule.depreciation_booked == False,
        AssetDepreciationSchedule.schedule_date <= today,
        Asset.status == AssetStatus.SUBMITTED,
    ).first()

    # =========== MAINTENANCE DUE ===========
    maintenance_due = db.query(Asset).filter(
        Asset.maintenance_required == True,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.asset_name).limit(10).all()

    maintenance_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "location": a.location,
            "last_maintenance": None,  # Would need maintenance log
        }
        for a in maintenance_due
    ]

    # =========== WARRANTY EXPIRING ===========
    warranty_expiring = db.query(Asset).filter(
        Asset.warranty_expiry_date.isnot(None),
        Asset.warranty_expiry_date >= today,
        Asset.warranty_expiry_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.warranty_expiry_date.asc()).limit(10).all()

    warranty_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "warranty_expiry_date": a.warranty_expiry_date.isoformat() if a.warranty_expiry_date else None,
            "days_remaining": (a.warranty_expiry_date - today).days if a.warranty_expiry_date else 0,
        }
        for a in warranty_expiring
    ]

    warranty_count = db.query(func.count(Asset.id)).filter(
        Asset.warranty_expiry_date.isnot(None),
        Asset.warranty_expiry_date >= today,
        Asset.warranty_expiry_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).scalar() or 0

    # =========== INSURANCE EXPIRING ===========
    insurance_expiring = db.query(Asset).filter(
        Asset.insurance_end_date.isnot(None),
        Asset.insurance_end_date >= today,
        Asset.insurance_end_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).order_by(Asset.insurance_end_date.asc()).limit(10).all()

    insurance_assets = [
        {
            "id": a.id,
            "asset_name": a.asset_name,
            "insurance_end_date": a.insurance_end_date.isoformat() if a.insurance_end_date else None,
            "days_remaining": (a.insurance_end_date - today).days if a.insurance_end_date else 0,
        }
        for a in insurance_expiring
    ]

    insurance_count = db.query(func.count(Asset.id)).filter(
        Asset.insurance_end_date.isnot(None),
        Asset.insurance_end_date >= today,
        Asset.insurance_end_date <= future_date,
        Asset.status == AssetStatus.SUBMITTED,
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),

        "totals": totals_data,
        "by_status": by_status,

        "depreciation": {
            "pending_count": pending_dep_total[0] if pending_dep_total else 0,
            "pending_amount": float(pending_dep_total[1] or 0) if pending_dep_total else 0,
            "entries": pending_dep_entries,
        },

        "maintenance": {
            "due_count": len(maintenance_due),
            "assets": maintenance_assets,
        },

        "expiring": {
            "warranty": {
                "count": warranty_count,
                "assets": warranty_assets,
            },
            "insurance": {
                "count": insurance_count,
                "assets": insurance_assets,
            },
        },
    }


# =============================================================================
# PROJECTS DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/projects", dependencies=[Depends(Require("projects:read"))])
@cached("dashboard-projects", ttl=CACHE_TTL["short"])
async def get_projects_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Projects Dashboard endpoint.

    Combines data from:
    - Project summary (by status, totals)
    - Task metrics
    - Financial summary
    - Recent projects
    """
    from app.models.project import Project, ProjectStatus
    from app.models.task import Task

    now = datetime.now(timezone.utc)
    today = date.today()
    week_end = today + timedelta(days=7)

    # =========== PROJECT COUNTS ===========
    total_projects = db.query(func.count(Project.id)).filter(
        Project.is_deleted == False
    ).scalar() or 0

    active_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar() or 0

    completed_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.is_deleted == False
    ).scalar() or 0

    on_hold_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.ON_HOLD,
        Project.is_deleted == False
    ).scalar() or 0

    cancelled_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.CANCELLED,
        Project.is_deleted == False
    ).scalar() or 0

    # =========== TASK METRICS ===========
    total_tasks = db.query(func.count(Task.id)).scalar() or 0
    open_tasks = db.query(func.count(Task.id)).filter(
        Task.status.in_(["Open", "Working", "Pending Review", "open", "working"])
    ).scalar() or 0
    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.status.in_(["Open", "Working", "open", "working"]),
        Task.exp_end_date < today
    ).scalar() or 0

    # =========== COMPLETION METRICS ===========
    avg_completion = db.query(
        func.avg(Project.percent_complete)
    ).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar()
    avg_completion_percent = float(avg_completion or 0)

    # Due this week
    due_this_week = db.query(func.count(Project.id)).filter(
        Project.expected_end_date >= today,
        Project.expected_end_date <= week_end,
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False
    ).scalar() or 0

    # =========== FINANCIALS ===========
    financials = db.query(
        func.sum(Project.total_billed_amount).label("billed"),
        func.sum(Project.total_costing_amount).label("cost"),
        func.sum(Project.gross_margin).label("margin")
    ).filter(
        Project.is_deleted == False
    ).first()

    financials_data = {
        "total_billed": float(financials.billed or 0) if financials else 0,
        "total_cost": float(financials.cost or 0) if financials else 0,
        "total_margin": float(financials.margin or 0) if financials else 0,
    }

    # =========== RECENT PROJECTS ===========
    recent_projects = [
        {
            "id": p.id,
            "project_name": p.project_name,
            "status": p.status.value if p.status else None,
            "percent_complete": float(p.percent_complete or 0),
            "expected_end_date": p.expected_end_date.isoformat() if p.expected_end_date else None,
            "department": p.department,
        }
        for p in db.query(Project).filter(
            Project.is_deleted == False
        ).order_by(
            Project.updated_at.desc()
        ).limit(5).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": completed_projects,
            "on_hold": on_hold_projects,
            "cancelled": cancelled_projects,
        },

        "tasks": {
            "total": total_tasks,
            "open": open_tasks,
            "overdue": overdue_tasks,
        },

        "metrics": {
            "avg_completion_percent": round(avg_completion_percent, 1),
            "due_this_week": due_this_week,
        },

        "financials": financials_data,

        "recent": recent_projects,
    }

