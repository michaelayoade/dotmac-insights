"""
Field Service Calendar Routes - Calendar, Dispatch, and Map Views.

Permission Requirements:
- field_service:read - View calendar and dispatch board
- field_service:write - Update service order scheduling
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from ._deps import (
    # Dependencies
    SessionUser, CSRFToken, DB,
    RequireFieldServiceRead, RequireFieldServiceWrite,
    # Helpers
    templates, get_base_context, get_navigation_context, build_breadcrumbs,
    is_htmx_request, htmx_toast, set_flash, _form_date, _form_int,
    # Options
    get_technician_options, get_team_options, get_zone_options,
    # Service
    FieldServiceWebService,
)

router = APIRouter(prefix="/field-service", tags=["field_service_calendar"])


# =============================================================================
# CALENDAR VIEW
# =============================================================================

@router.get("/calendar", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def calendar_view(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    technician_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
):
    """Calendar view of service orders."""
    service = FieldServiceWebService(db, user.id)

    # Parse dates
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()

    # Get start of week (Monday)
    start_date = start_date - timedelta(days=start_date.weekday())
    end_date = start_date + timedelta(days=6)

    # Get calendar data
    calendar_data = service.get_calendar_data(
        start_date=start_date,
        end_date=end_date,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
    )

    # Build date range for template
    date_range = []
    current = start_date
    while current <= end_date:
        date_range.append({
            "date": current,
            "date_iso": current.isoformat(),
            "day_name": current.strftime("%a"),
            "day_number": current.day,
            "is_today": current == date.today(),
            "orders": calendar_data["calendar"].get(current.isoformat(), []),
            "summary": calendar_data["daily_summary"].get(current.isoformat(), {}),
        })
        current += timedelta(days=1)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Service Calendar"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Field Service", "url": "/field-service"},
        {"label": "Calendar", "url": None},
    ])

    # Calendar data
    context["date_range"] = date_range
    context["start_date"] = start_date
    context["end_date"] = end_date
    context["prev_week"] = (start_date - timedelta(days=7)).isoformat()
    context["next_week"] = (start_date + timedelta(days=7)).isoformat()
    context["today"] = date.today().isoformat()
    context["total_orders"] = calendar_data["total_orders"]

    # Filter state
    context["technician_id"] = technician_id
    context["team_id"] = team_id
    context["zone_id"] = zone_id

    # Filter options
    context["technician_options"] = get_technician_options(db)
    context["team_options"] = get_team_options(db)
    context["zone_options"] = get_zone_options(db)

    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/calendar_grid.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/field_service/templates/pages/calendar.html")
    return HTMLResponse(template.render(context))


@router.get("/calendar/data", dependencies=[RequireFieldServiceRead])
async def calendar_data(
    request: Request,
    db: DB,
    user: SessionUser,
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    technician_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
):
    """Get calendar data as JSON for dynamic updates."""
    service = FieldServiceWebService(db, user.id)

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return JSONResponse({"error": "Invalid date format"}, status_code=400)

    calendar_data = service.get_calendar_data(
        start_date=start_date,
        end_date=end_date,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
    )

    return JSONResponse(calendar_data)


# =============================================================================
# DISPATCH BOARD
# =============================================================================

@router.get("/dispatch", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def dispatch_board(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    dispatch_date: Optional[str] = Query(None, alias="date"),
):
    """Dispatch board - Kanban-style view for daily dispatching."""
    service = FieldServiceWebService(db, user.id)

    # Parse date
    if dispatch_date:
        try:
            check_date = date.fromisoformat(dispatch_date)
        except ValueError:
            check_date = date.today()
    else:
        check_date = date.today()

    # Get dispatch board data
    board_data = service.get_dispatch_board(check_date)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Dispatch Board - {check_date.strftime('%B %d, %Y')}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Field Service", "url": "/field-service"},
        {"label": "Dispatch Board", "url": None},
    ])

    # Board data
    context["dispatch_date"] = check_date
    context["orders"] = board_data["orders"]
    context["all_orders"] = board_data["all_orders"]
    context["summary"] = board_data["summary"]
    context["technician_workload"] = board_data["technician_workload"]

    # Navigation
    context["prev_date"] = (check_date - timedelta(days=1)).isoformat()
    context["next_date"] = (check_date + timedelta(days=1)).isoformat()
    context["today"] = date.today().isoformat()

    # Technician options for assignment
    context["technician_options"] = get_technician_options(db)

    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/dispatch_board.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/field_service/templates/pages/dispatch.html")
    return HTMLResponse(template.render(context))


@router.get("/dispatch/data", dependencies=[RequireFieldServiceRead])
async def dispatch_data(
    request: Request,
    db: DB,
    user: SessionUser,
    dispatch_date: str = Query(..., alias="date"),
):
    """Get dispatch board data as JSON."""
    service = FieldServiceWebService(db, user.id)

    try:
        check_date = date.fromisoformat(dispatch_date)
    except ValueError:
        return JSONResponse({"error": "Invalid date format"}, status_code=400)

    board_data = service.get_dispatch_board(check_date)
    return JSONResponse(board_data)


# =============================================================================
# MAP VIEW
# =============================================================================

@router.get("/map", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def map_dispatch(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    map_date: Optional[str] = Query(None, alias="date"),
    technician_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
):
    """Map view for service order locations and route planning."""
    service = FieldServiceWebService(db, user.id)

    # Parse date
    if map_date:
        try:
            check_date = date.fromisoformat(map_date)
        except ValueError:
            check_date = date.today()
    else:
        check_date = date.today()

    # Get calendar data for the day (includes lat/lng)
    calendar_data = service.get_calendar_data(
        start_date=check_date,
        end_date=check_date,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
    )

    # Extract orders for map markers
    orders_for_map = calendar_data["calendar"].get(check_date.isoformat(), [])

    # Filter only orders with coordinates
    orders_with_coords = [o for o in orders_for_map if o.get("latitude") and o.get("longitude")]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Map Dispatch - {check_date.strftime('%B %d, %Y')}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Field Service", "url": "/field-service"},
        {"label": "Map View", "url": None},
    ])

    # Map data
    context["map_date"] = check_date
    context["orders"] = orders_for_map
    context["orders_with_coords"] = orders_with_coords
    context["summary"] = calendar_data["daily_summary"].get(check_date.isoformat(), {})

    # Navigation
    context["prev_date"] = (check_date - timedelta(days=1)).isoformat()
    context["next_date"] = (check_date + timedelta(days=1)).isoformat()
    context["today"] = date.today().isoformat()

    # Filter state
    context["technician_id"] = technician_id
    context["team_id"] = team_id
    context["zone_id"] = zone_id

    # Filter options
    context["technician_options"] = get_technician_options(db)
    context["team_options"] = get_team_options(db)
    context["zone_options"] = get_zone_options(db)

    template = templates.get_template("modules/field_service/templates/pages/map_dispatch.html")
    return HTMLResponse(template.render(context))


@router.get("/map/orders", dependencies=[RequireFieldServiceRead])
async def map_orders_data(
    request: Request,
    db: DB,
    user: SessionUser,
    map_date: str = Query(..., alias="date"),
    technician_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
):
    """Get map order data as JSON for dynamic updates."""
    service = FieldServiceWebService(db, user.id)

    try:
        check_date = date.fromisoformat(map_date)
    except ValueError:
        return JSONResponse({"error": "Invalid date format"}, status_code=400)

    calendar_data = service.get_calendar_data(
        start_date=check_date,
        end_date=check_date,
        technician_id=technician_id,
        team_id=team_id,
        zone_id=zone_id,
    )

    orders = calendar_data["calendar"].get(check_date.isoformat(), [])

    return JSONResponse({
        "date": check_date.isoformat(),
        "orders": orders,
        "summary": calendar_data["daily_summary"].get(check_date.isoformat(), {}),
    })


# =============================================================================
# TECHNICIAN SCHEDULE
# =============================================================================

@router.get("/technicians/{technician_id}/schedule", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def technician_schedule(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    technician_id: int,
    start: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=14),
):
    """View a technician's schedule."""
    service = FieldServiceWebService(db, user.id)

    # Parse start date
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()

    schedule_data = service.get_technician_schedule(technician_id, start_date, days)

    if not schedule_data:
        set_flash(response, "Technician not found.", "error")
        return RedirectResponse(url="/field-service", status_code=303)

    # Build date range
    date_range = []
    current = start_date
    end_date = start_date + timedelta(days=days - 1)
    while current <= end_date:
        date_range.append({
            "date": current,
            "date_iso": current.isoformat(),
            "day_name": current.strftime("%a"),
            "day_number": current.day,
            "is_today": current == date.today(),
            "orders": schedule_data["schedule"].get(current.isoformat(), []),
        })
        current += timedelta(days=1)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Schedule - {schedule_data['technician']['name']}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Field Service", "url": "/field-service"},
        {"label": "Technicians", "url": "/field-service/technicians"},
        {"label": schedule_data["technician"]["name"], "url": f"/field-service/technicians/{technician_id}"},
        {"label": "Schedule", "url": None},
    ])

    context["technician"] = schedule_data["technician"]
    context["date_range"] = date_range
    context["summary"] = schedule_data["summary"]
    context["start_date"] = start_date
    context["days"] = days

    # Navigation
    context["prev_week"] = (start_date - timedelta(days=7)).isoformat()
    context["next_week"] = (start_date + timedelta(days=7)).isoformat()

    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/technician_schedule.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/field_service/templates/pages/technician_schedule.html")
    return HTMLResponse(template.render(context))
