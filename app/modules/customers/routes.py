"""
Customers Routes - Customer Account Management with SSR + HTMX.

Permission Requirements:
- customers:read - View customer accounts
- customers:write - Create, update customers
"""
from __future__ import annotations

from typing import Optional, Any
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.customer import Customer, CustomerStatus, CustomerType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.payment import Payment
from app.models.pop import Pop
from app.models.project import Project, ProjectStatus
from app.models.ipv4_address import IPv4Address
from app.models.router import Router
from app.models.customer_note import CustomerNote
from app.core.security import is_htmx_request, htmx_toast, set_flash
from datetime import datetime, date, timedelta
from sqlalchemy import case
from sqlalchemy.orm import selectinload

# Permission dependencies
RequireCustomersRead = Depends(require_scope("customers:read"))
RequireCustomersWrite = Depends(require_scope("customers:write"))

router = APIRouter(prefix="/customers", tags=["customers"])
templates = get_template_env()


def get_status_options():
    """Get status options for filter dropdown."""
    return [
        {"value": s.value, "label": s.value.title()}
        for s in CustomerStatus
    ]


def get_type_options():
    """Get type options for filter dropdown."""
    return [
        {"value": t.value, "label": t.value.title()}
        for t in CustomerType
    ]


def get_customer_stats(db) -> dict:
    """Calculate customer statistics."""
    # Total count
    total_count = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False
    ).scalar() or 0

    # Active count
    active_count = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    # Total MRR
    total_mrr = db.query(func.sum(Customer.mrr)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or Decimal("0")

    # Suspended count
    suspended_count = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.SUSPENDED
    ).scalar() or 0

    return {
        "total_count": total_count,
        "active_count": active_count,
        "total_mrr": total_mrr,
        "suspended_count": suspended_count,
    }


@router.get("", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Customers list page."""
    # Build query
    query = db.query(Customer).filter(Customer.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            Customer.name.ilike(f"%{q}%"),
            Customer.email.ilike(f"%{q}%"),
            Customer.phone.ilike(f"%{q}%"),
            Customer.account_number.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Customer.status == status)
    if type:
        query = query.filter(Customer.customer_type == type)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Customer, sort, Customer.name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    customers = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_customer_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["customers"] = customers
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_type"] = type
    context["status_options"] = get_status_options()
    context["type_options"] = get_type_options()
    context["stats"] = stats
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/customers/templates/partials/customers_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Customers"},
    ])

    template = templates.get_template("modules/customers/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customers_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name"),
    dir: str = Query("asc"),
):
    """Customers table partial for HTMX updates."""
    return await customers_list(
        request, response, user, csrf_token, db,
        q, status, type, page, per_page, sort, dir
    )


@router.get("/dashboard", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customers_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Customer dashboard - aggregate metrics and insights."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    # Overview stats
    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False
    ).scalar() or 0

    active_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    suspended_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.SUSPENDED
    ).scalar() or 0

    # New customers last 30 days
    new_last_30 = db.query(func.count(Customer.id)).filter(
        Customer.signup_date.isnot(None),
        Customer.signup_date >= thirty_days_ago
    ).scalar() or 0

    # Total MRR
    total_mrr = db.query(func.sum(Customer.mrr)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or Decimal("0")

    # Churn rate (inactive customers with cancellation date in last 30 days)
    churned_last_30 = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date.isnot(None),
        Customer.cancellation_date >= thirty_days_ago
    ).scalar() or 0

    # Calculate churn rate
    churn_rate: float = 0.0
    if active_customers > 0:
        churn_rate = round((churned_last_30 / active_customers) * 100, 1)

    # Distribution by type
    type_distribution = db.query(
        Customer.customer_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.is_deleted == False
    ).group_by(Customer.customer_type).all()

    # Distribution by status
    status_distribution = db.query(
        Customer.status,
        func.count(Customer.id).label("count"),
    ).filter(
        Customer.is_deleted == False
    ).group_by(Customer.status).all()

    # Recent signups
    recent_signups = db.query(Customer).filter(
        Customer.is_deleted == False,
        Customer.signup_date.isnot(None),
    ).order_by(Customer.signup_date.desc()).limit(10).all()

    # Blocked customers requiring attention
    blocked_customers = db.query(Customer).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.SUSPENDED
    ).order_by(Customer.updated_at.desc()).limit(5).all()

    # Customers at risk (blocking soon)
    at_risk_customers = db.query(Customer).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE,
        Customer.days_until_blocking.isnot(None),
        Customer.days_until_blocking >= 0,
        Customer.days_until_blocking <= 7
    ).order_by(Customer.days_until_blocking.asc()).limit(10).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Customers", "href": "/customers"},
        {"label": "Dashboard"},
    ])

    context["stats"] = {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "suspended_customers": suspended_customers,
        "new_last_30": new_last_30,
        "total_mrr": total_mrr,
        "churned_last_30": churned_last_30,
        "churn_rate": churn_rate,
        "net_growth": new_last_30 - churned_last_30,
    }

    context["type_distribution"] = [
        {
            "type": t.customer_type.value if t.customer_type else "unknown",
            "count": t.count,
            "mrr": float(t.mrr or 0),
        }
        for t in type_distribution
    ]

    context["status_distribution"] = [
        {"status": s.status.value if s.status else "unknown", "count": s.count}
        for s in status_distribution
    ]

    context["recent_signups"] = recent_signups
    context["blocked_customers"] = blocked_customers
    context["at_risk_customers"] = at_risk_customers

    template = templates.get_template("modules/customers/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/360/{customer_id}", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customer_360_view(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    customer_id: int,
):
    """Customer 360 view - comprehensive customer data across all domains."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False,
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    today = date.today()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Get POP info
    pop_info = None
    if customer.pop_id:
        pop = db.query(Pop).filter(Pop.id == customer.pop_id).first()
        if pop:
            pop_info = {"id": pop.id, "name": pop.name, "city": pop.city}

    # Finance: Invoices
    invoice_stats = db.query(
        func.count(Invoice.id).label("total_count"),
        func.sum(Invoice.total_amount).label("total_amount"),
        func.sum(Invoice.amount_paid).label("total_paid"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, Invoice.balance), else_=Decimal("0"))).label("overdue_amount"),
    ).filter(Invoice.customer_id == customer_id).first()

    recent_invoices = db.query(Invoice).filter(
        Invoice.customer_id == customer_id
    ).order_by(Invoice.invoice_date.desc()).limit(10).all()

    # Finance: Payments
    payment_stats = db.query(
        func.count(Payment.id).label("total_count"),
        func.sum(Payment.amount).label("total_amount"),
        func.max(Payment.payment_date).label("last_payment_date"),
    ).filter(Payment.customer_id == customer_id).first()

    recent_payments = db.query(Payment).filter(
        Payment.customer_id == customer_id
    ).order_by(Payment.payment_date.desc()).limit(10).all()

    # Services: Subscriptions
    subscriptions = db.query(Subscription).filter(
        Subscription.customer_id == customer_id
    ).order_by(Subscription.start_date.desc()).all()

    active_subs = [s for s in subscriptions if s.status == SubscriptionStatus.ACTIVE]

    # Support: Tickets
    tickets = db.query(Ticket).filter(
        Ticket.customer_id == customer_id
    ).order_by(Ticket.created_at.desc()).limit(20).all()

    ticket_stats = db.query(
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label("open"),
        func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
    ).filter(Ticket.customer_id == customer_id).first()

    # Projects
    projects = db.query(Project).filter(
        Project.customer_id == customer_id
    ).order_by(Project.created_at.desc()).all()

    # Network: IP addresses
    ip_addresses = db.query(IPv4Address).filter(
        IPv4Address.customer_id == customer_id
    ).all()

    # Get routers from subscriptions
    router_ids = list(set(s.router_id for s in subscriptions if s.router_id))
    routers = []
    if router_ids:
        routers = db.query(Router).filter(Router.id.in_(router_ids)).all()

    # Notes
    notes = db.query(CustomerNote).filter(
        CustomerNote.customer_id == customer_id
    ).order_by(CustomerNote.note_datetime.desc().nullslast()).limit(10).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"{customer.name} - 360 View"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Customers", "href": "/customers"},
        {"label": customer.name, "href": f"/customers/{customer_id}"},
        {"label": "360 View"},
    ])

    context["customer"] = customer
    context["pop"] = pop_info

    context["finance"] = {
        "mrr": float(customer.mrr or 0),
        "total_invoiced": float(invoice_stats.total_amount or 0) if invoice_stats else 0,
        "total_paid": float(invoice_stats.total_paid or 0) if invoice_stats else 0,
        "outstanding": float((invoice_stats.total_amount or 0) - (invoice_stats.total_paid or 0)) if invoice_stats else 0,
        "overdue_count": invoice_stats.overdue_count if invoice_stats else 0,
        "overdue_amount": float(invoice_stats.overdue_amount or 0) if invoice_stats else 0,
        "payment_count": payment_stats.total_count if payment_stats else 0,
        "last_payment": payment_stats.last_payment_date if payment_stats else None,
        "deposit_balance": float(customer.deposit_balance or 0),
        "days_until_blocking": customer.days_until_blocking,
    }
    context["recent_invoices"] = recent_invoices
    context["recent_payments"] = recent_payments

    context["services"] = {
        "total_subscriptions": len(subscriptions),
        "active_subscriptions": len(active_subs),
        "total_mrr": sum(float(s.price or 0) for s in active_subs),
    }
    context["subscriptions"] = subscriptions

    context["support"] = {
        "total_tickets": ticket_stats.total if ticket_stats else 0,
        "open_tickets": ticket_stats.open if ticket_stats else 0,
        "closed_tickets": ticket_stats.closed if ticket_stats else 0,
    }
    context["tickets"] = tickets

    context["projects"] = projects
    context["project_stats"] = {
        "total": len(projects),
        "active": sum(1 for p in projects if p.status == ProjectStatus.OPEN),
        "completed": sum(1 for p in projects if p.status == ProjectStatus.COMPLETED),
    }

    context["network"] = {
        "ip_count": len(ip_addresses),
        "router_count": len(routers),
    }
    context["ip_addresses"] = ip_addresses
    context["routers"] = routers

    context["notes"] = notes

    template = templates.get_template("modules/customers/templates/pages/customer_360.html")
    return HTMLResponse(template.render(context))


@router.get("/insights", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customer_insights(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Customer insights - segments, health, completeness, plan changes."""
    from sqlalchemy import or_, and_, distinct
    from datetime import timezone
    from app.models.billing_type import BillingType

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)

    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False
    ).scalar() or 0

    total_active = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    # ==================== SEGMENTS ====================
    # By status
    status_segments = db.query(
        Customer.status,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).filter(Customer.is_deleted == False).group_by(Customer.status).all()

    # By type
    type_segments = db.query(
        Customer.customer_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).filter(Customer.is_deleted == False).group_by(Customer.customer_type).all()

    # MRR tiers
    mrr_bucket = case(
        (or_(Customer.mrr.is_(None), Customer.mrr == 0), 'No MRR'),
        (Customer.mrr < 10000, 'Low (<10K)'),
        (Customer.mrr < 50000, 'Medium (10K-50K)'),
        (Customer.mrr < 200000, 'High (50K-200K)'),
        else_='Enterprise (200K+)'
    )

    mrr_segments = db.query(
        mrr_bucket.label("segment"),
        func.count(Customer.id).label("count"),
    ).filter(Customer.is_deleted == False).group_by(mrr_bucket).all()

    # Tenure segments
    tenure_bucket = case(
        (Customer.signup_date.is_(None), 'Unknown'),
        (func.date_part("day", func.current_date() - Customer.signup_date) <= 30, 'New (0-30 days)'),
        (func.date_part("day", func.current_date() - Customer.signup_date) <= 90, 'Growing (31-90 days)'),
        (func.date_part("day", func.current_date() - Customer.signup_date) <= 365, 'Established (91-365 days)'),
        (func.date_part("day", func.current_date() - Customer.signup_date) <= 730, 'Loyal (1-2 years)'),
        else_='Long-term (2+ years)'
    )

    tenure_segments = db.query(
        tenure_bucket.label("segment"),
        func.count(Customer.id).label("count"),
    ).filter(Customer.is_deleted == False).group_by(tenure_bucket).all()

    # ==================== HEALTH ====================
    # Payment behavior
    customers_with_overdue = db.query(distinct(Invoice.customer_id)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).count()

    # Support intensity (customers with 3+ tickets in last 30 days)
    tickets_subq = db.query(
        Ticket.customer_id,
        func.count(Ticket.id).label("ticket_count")
    ).filter(
        Ticket.customer_id.isnot(None),
        Ticket.created_at >= thirty_days_ago
    ).group_by(Ticket.customer_id).subquery()

    high_support_customers = db.query(func.count(tickets_subq.c.customer_id)).filter(
        tickets_subq.c.ticket_count >= 3
    ).scalar() or 0

    # Churn indicators
    recently_cancelled = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date >= thirty_days_ago
    ).scalar() or 0

    currently_suspended = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).scalar() or 0

    # Blocking risk
    blocking_soon = db.query(
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.days_until_blocking.isnot(None),
        Customer.days_until_blocking >= 0,
        Customer.days_until_blocking <= 7
    ).first()

    # ==================== COMPLETENESS ====================
    completeness_fields = {
        "email": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            Customer.email.isnot(None),
            Customer.email != ""
        ).scalar() or 0,
        "phone": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            Customer.phone.isnot(None),
            Customer.phone != ""
        ).scalar() or 0,
        "address": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            Customer.address.isnot(None),
            Customer.address != ""
        ).scalar() or 0,
        "city": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            Customer.city.isnot(None),
            Customer.city != ""
        ).scalar() or 0,
        "gps": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            and_(Customer.latitude.isnot(None), Customer.longitude.isnot(None))
        ).scalar() or 0,
        "pop": db.query(func.count(Customer.id)).filter(
            Customer.is_deleted == False,
            Customer.pop_id.isnot(None)
        ).scalar() or 0,
    }

    critical_score: float = 0.0
    overall_score: float = 0.0
    if total_customers > 0:
        critical_fields = ["email", "phone"]
        critical_score = round(
            sum(completeness_fields[f] for f in critical_fields) / (len(critical_fields) * total_customers) * 100, 1
        )
        overall_score = round(
            sum(completeness_fields.values()) / (len(completeness_fields) * total_customers) * 100, 1
        )

    # ==================== PLAN CHANGES ====================
    plan_changes_subq = db.query(
        Subscription.customer_id,
        func.count(distinct(Subscription.plan_name)).label("plan_count")
    ).filter(
        Subscription.start_date >= six_months_ago
    ).group_by(Subscription.customer_id).having(
        func.count(distinct(Subscription.plan_name)) > 1
    ).subquery()

    customers_with_plan_changes = db.query(
        func.count(plan_changes_subq.c.customer_id)
    ).scalar() or 0

    # Get recent plan transitions for display
    plan_transitions = db.query(
        Subscription.customer_id,
        Subscription.plan_name,
        Subscription.price,
        Subscription.start_date,
        Customer.name.label("customer_name"),
    ).join(Customer, Customer.id == Subscription.customer_id).filter(
        Subscription.start_date >= six_months_ago,
        Subscription.customer_id.in_(
            db.query(plan_changes_subq.c.customer_id)
        )
    ).order_by(Subscription.customer_id, Subscription.start_date).limit(100).all()

    # Analyze transitions
    transitions: list[dict[str, Any]] = []
    upgrades = 0
    downgrades = 0
    current_customer = None
    prev_plan = None
    prev_price = Decimal("0")

    for sub in plan_transitions:
        if sub.customer_id != current_customer:
            current_customer = sub.customer_id
            prev_plan = sub.plan_name
            prev_price = sub.price or Decimal("0")
        else:
            if sub.plan_name != prev_plan:
                current_price = sub.price or Decimal("0")
                price_diff = float(current_price - prev_price)
                if price_diff > 0:
                    upgrades += 1
                    change_type = "upgrade"
                elif price_diff < 0:
                    downgrades += 1
                    change_type = "downgrade"
                else:
                    change_type = "lateral"

                if len(transitions) < 10:
                    transitions.append({
                        "customer_id": sub.customer_id,
                        "customer_name": sub.customer_name,
                        "from_plan": prev_plan,
                        "to_plan": sub.plan_name,
                        "price_change": price_diff,
                        "change_type": change_type,
                        "date": sub.start_date,
                    })

                prev_plan = sub.plan_name
                prev_price = current_price

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Insights"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Customers", "href": "/customers"},
        {"label": "Insights"},
    ])

    context["totals"] = {
        "total_customers": total_customers,
        "active_customers": total_active,
    }

    context["segments"] = {
        "by_status": [
            {"segment": s.status.value if s.status else "unknown", "count": s.count, "mrr": float(s.total_mrr or 0)}
            for s in status_segments
        ],
        "by_type": [
            {"segment": t.customer_type.value if t.customer_type else "unknown", "count": t.count, "mrr": float(t.total_mrr or 0)}
            for t in type_segments
        ],
        "by_mrr": [
            {"segment": m.segment, "count": m.count}
            for m in mrr_segments
        ],
        "by_tenure": [
            {"segment": t.segment, "count": t.count}
            for t in tenure_segments
        ],
    }

    context["health"] = {
        "customers_with_overdue": customers_with_overdue,
        "overdue_rate": round(customers_with_overdue / total_active * 100, 1) if total_active > 0 else 0,
        "high_support_customers": high_support_customers,
        "recently_cancelled": recently_cancelled,
        "currently_suspended": currently_suspended,
        "at_risk_total": customers_with_overdue + currently_suspended,
        "blocking_soon": {
            "count": blocking_soon.count if blocking_soon else 0,
            "mrr": float(blocking_soon.mrr or 0) if blocking_soon else 0,
        },
    }

    context["completeness"] = {
        "critical_score": critical_score,
        "overall_score": overall_score,
        "fields": {
            field: {
                "count": count,
                "percent": round(count / total_customers * 100, 1) if total_customers > 0 else 0,
                "missing": total_customers - count,
            }
            for field, count in completeness_fields.items()
        },
    }

    context["plan_changes"] = {
        "customers_with_changes": customers_with_plan_changes,
        "upgrades": upgrades,
        "downgrades": downgrades,
        "ratio": round(upgrades / downgrades, 2) if downgrades > 0 else upgrades,
        "recent_transitions": transitions,
    }

    template = templates.get_template("modules/customers/templates/pages/insights.html")
    return HTMLResponse(template.render(context))


@router.get("/{customer_id}", response_class=HTMLResponse, dependencies=[RequireCustomersRead])
async def customer_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    customer_id: int,
):
    """Customer detail page."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False,
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = customer.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Customers", "href": "/customers"},
        {"label": customer.name},
    ])
    context["customer"] = customer

    template = templates.get_template("modules/customers/templates/pages/detail.html")
    return HTMLResponse(template.render(context))
